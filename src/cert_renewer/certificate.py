import configparser
import hashlib
import json
import os
import re
import secrets
import socket
import stat
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

from .model import CertificateConfig, ServiceConfig
from .process import ProcessRunner


class CertificateError(RuntimeError):
    pass


@dataclass(frozen=True)
class CertificateInfo:
    expires_at: datetime
    domains: frozenset[str]
    key_matches: bool


@dataclass(frozen=True)
class ReconcileResult:
    name: str
    changed: bool
    expires_at: datetime
    action: str


class Inspector(Protocol):
    def inspect(self, chain: Path, key: Path) -> CertificateInfo: ...


class OpenSSLInspector:
    def __init__(self, executable: str, runner: ProcessRunner):
        self.executable = executable
        self.runner = runner

    def inspect(self, chain: Path, key: Path) -> CertificateInfo:
        try:
            end = self.runner.run([self.executable, "x509", "-in", str(chain), "-noout", "-enddate"]).stdout.strip()
            expiry = datetime.strptime(end.removeprefix("notAfter="), "%b %d %H:%M:%S %Y %Z").replace(tzinfo=UTC)
            san = self.runner.run([self.executable, "x509", "-in", str(chain), "-noout", "-ext", "subjectAltName"]).stdout
            domains = frozenset(item.lower().rstrip(".") for item in re.findall(r"DNS:([^,\s]+)", san))
            cert_public = self.runner.run([self.executable, "x509", "-in", str(chain), "-pubkey", "-noout"]).stdout.strip()
            key_public = self.runner.run([self.executable, "pkey", "-in", str(key), "-pubout"]).stdout.strip()
        except Exception as exc:
            raise CertificateError(f"certificate validation failed: {exc}") from exc
        return CertificateInfo(expiry, domains, cert_public == key_public)


class CertificateManager:
    def __init__(self, service: ServiceConfig, *, runner=None, inspector=None):
        self.service = service
        self.runner = runner or ProcessRunner()
        self.inspector = inspector or OpenSSLInspector(service.openssl_executable, self.runner)

    def reconcile(self, cert: CertificateConfig) -> ReconcileResult:
        lineage = self.service.certbot_config_dir / "live" / cert.name
        chain = lineage / "fullchain.pem"
        key = lineage / "privkey.pem"
        existed = chain.is_file() and key.is_file()
        action = "unchanged"
        if not existed:
            self._certbot(cert, force=False)
            action = "issued"
        else:
            current = self.inspector.inspect(chain, key)
            remaining = (current.expires_at - datetime.now(UTC)).total_seconds()
            if set(current.domains) != set(cert.domains):
                self._certbot(cert, force=True)
                action = "reissued-domains-changed"
            elif not self._lineage_server_matches(cert):
                self._certbot(cert, force=True)
                action = "reissued-parameters-changed"
            elif remaining <= self.service.renewal_threshold_seconds:
                self._certbot(cert, force=True)
                action = "renewed"
        if not chain.is_file() or not key.is_file():
            raise CertificateError(f"certbot did not produce lineage {cert.name}")
        info = self.inspector.inspect(chain, key)
        self._validate(cert, info)
        chain_data, key_data = chain.read_bytes(), key.read_bytes()
        digest = self._content_digest(chain_data, key_data)
        installed_digest, managed = self._installed_digest(cert.destination)
        changed = installed_digest != digest
        if changed:
            self._install(cert.destination, chain_data, key_data, digest)
            if action == "unchanged":
                action = "installed"
        state = self._load_deployment_state(cert)
        if not state and not changed and not managed:
            state = {"installed_digest": digest, "applied_digest": digest, "reload_pending": False}
            self._write_deployment_state(cert, state)
        elif changed or state.get("installed_digest") != digest:
            state = {"installed_digest": digest, "applied_digest": state.get("applied_digest"), "reload_pending": True}
            self._write_deployment_state(cert, state)
        if state.get("reload_pending") or state.get("applied_digest") != digest:
            try:
                self._reload(cert)
            except Exception:
                state["reload_pending"] = True
                self._write_deployment_state(cert, state)
                raise
            state = {"installed_digest": digest, "applied_digest": digest, "reload_pending": False}
            self._write_deployment_state(cert, state)
            if not changed and action == "unchanged":
                action = "reload-retried"
        return ReconcileResult(cert.name, changed, info.expires_at, action)

    def _certbot(self, cert: CertificateConfig, *, force: bool) -> None:
        self.service.state_dir.mkdir(parents=True, exist_ok=True)
        raw_token = cert.token_file.read_text(encoding="utf-8")
        lines = raw_token.splitlines()
        if len(lines) != 1 or not lines[0] or lines[0] != lines[0].strip():
            raise CertificateError(f"Cloudflare token for {cert.name} must contain one nonempty line")
        token = lines[0]
        descriptor, raw_credentials = tempfile.mkstemp(prefix=f"cert-renewer-{cert.name}-", suffix=".ini")
        credentials = Path(raw_credentials)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(f"dns_cloudflare_api_token = {token}\n".encode())
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(credentials, 0o600)
            argv = [self.service.certbot_executable, "certonly", "--non-interactive", "--agree-tos", "--email", self.service.email, "--dns-cloudflare", "--dns-cloudflare-credentials", str(credentials), "--dns-cloudflare-propagation-seconds", str(cert.propagation_seconds), "--cert-name", cert.name, "--config-dir", str(self.service.certbot_config_dir), "--work-dir", str(self.service.certbot_work_dir), "--logs-dir", str(self.service.certbot_logs_dir), "--server", self.service.acme_server]
            if force:
                argv.append("--force-renewal")
            for domain in cert.domains:
                argv.extend(["-d", domain])
            try:
                self.runner.run(argv)
            except Exception as exc:
                raise CertificateError(str(exc).replace(token, "[REDACTED]")) from exc
        finally:
            credentials.unlink(missing_ok=True)

    def _lineage_server_matches(self, cert: CertificateConfig) -> bool:
        renewal = self.service.certbot_config_dir / "renewal" / f"{cert.name}.conf"
        if not renewal.exists():
            return True
        parser = configparser.RawConfigParser()
        try:
            with renewal.open(encoding="utf-8") as handle:
                parser.read_file(handle)
            return parser.get("renewalparams", "server") == self.service.acme_server
        except (OSError, configparser.Error, KeyError):
            return False

    @staticmethod
    def _validate(cert: CertificateConfig, info: CertificateInfo) -> None:
        if not info.key_matches:
            raise CertificateError(f"private key does not match certificate {cert.name}")
        missing = set(cert.domains) - set(info.domains)
        if missing:
            raise CertificateError(f"certificate {cert.name} is missing domains: {', '.join(sorted(missing))}")
        unexpected = set(info.domains) - set(cert.domains)
        if unexpected:
            raise CertificateError(f"certificate {cert.name} has unexpected domains: {', '.join(sorted(unexpected))}")
        if info.expires_at <= datetime.now(UTC):
            raise CertificateError(f"certificate {cert.name} is expired")

    @staticmethod
    def _content_digest(chain: bytes, key: bytes) -> str:
        digest = hashlib.sha256()
        for value in (chain, key):
            digest.update(len(value).to_bytes(8, "big"))
            digest.update(value)
        return digest.hexdigest()

    @staticmethod
    def _ensure_safe_directory(path: Path) -> None:
        current = Path(path.anchor)
        for part in path.parts[1:]:
            current /= part
            try:
                mode = current.lstat().st_mode
            except FileNotFoundError:
                continue
            if stat.S_ISLNK(mode):
                parent_mode = current.parent.stat().st_mode
                trusted_system_link = current.lstat().st_uid == 0 and not parent_mode & 0o022
                if not trusted_system_link:
                    raise CertificateError(f"refusing symlink path component: {current}")

    def _installed_digest(self, destination: Path) -> tuple[str | None, bool]:
        self._ensure_safe_directory(destination)
        current = destination / "current"
        target_chain, target_key = destination / "fullchain.pem", destination / "privkey.pem"
        if current.is_symlink():
            link = os.readlink(current)
            match = re.fullmatch(r"revisions/([0-9a-f]{64})", link)
            if not match:
                raise CertificateError(f"refusing unmanaged current symlink: {current}")
            compatibility_needs_repair = False
            for target, expected in ((target_chain, "current/fullchain.pem"), (target_key, "current/privkey.pem")):
                if target.is_symlink():
                    if os.readlink(target) != expected:
                        raise CertificateError(f"refusing unmanaged certificate target: {target}")
                elif not target.exists() or target.is_file():
                    compatibility_needs_repair = True
                else:
                    raise CertificateError(f"refusing unmanaged certificate target: {target}")
            revision = destination / link
            for source in (revision / "fullchain.pem", revision / "privkey.pem"):
                try:
                    mode = source.lstat().st_mode
                except OSError as exc:
                    raise CertificateError(f"invalid certificate revision: {source}: {exc}") from exc
                if not stat.S_ISREG(mode):
                    raise CertificateError(f"invalid certificate revision file: {source}")
            actual = self._content_digest((revision / "fullchain.pem").read_bytes(), (revision / "privkey.pem").read_bytes())
            if actual != match.group(1):
                raise CertificateError(f"certificate revision digest mismatch: {revision}")
            return (None if compatibility_needs_repair else actual), True
        if current.exists():
            raise CertificateError(f"refusing unmanaged current target: {current}")
        values: list[bytes] = []
        for target in (target_chain, target_key):
            try:
                mode = target.lstat().st_mode
            except FileNotFoundError:
                return None, False
            if not stat.S_ISREG(mode):
                raise CertificateError(f"refusing non-regular certificate target: {target}")
            values.append(target.read_bytes())
        return self._content_digest(*values), False

    def _install(self, destination: Path, chain: bytes, key: bytes, digest: str) -> None:
        self._ensure_safe_directory(destination)
        destination.mkdir(parents=True, exist_ok=True)
        revisions = destination / "revisions"
        if revisions.exists() and (revisions.is_symlink() or not revisions.is_dir()):
            raise CertificateError(f"refusing unsafe revisions directory: {revisions}")
        revisions.mkdir(mode=0o700, exist_ok=True)
        revision = revisions / digest
        temporary: Path | None = None
        if not revision.exists():
            try:
                temporary = Path(tempfile.mkdtemp(prefix=f".{digest}.", dir=revisions))
                os.chmod(temporary, 0o700)
                self._atomic_write(temporary / "fullchain.pem", chain, 0o644)
                self._atomic_write(temporary / "privkey.pem", key, 0o600)
                self._fsync_directory(temporary)
                os.replace(temporary, revision)
                self._fsync_directory(revisions)
            finally:
                if temporary is not None and temporary.exists():
                    for name in ("fullchain.pem", "privkey.pem"):
                        (temporary / name).unlink(missing_ok=True)
                    temporary.rmdir()
        else:
            if revision.is_symlink() or not revision.is_dir():
                raise CertificateError(f"refusing unsafe certificate revision: {revision}")
            try:
                existing_chain = revision.joinpath("fullchain.pem")
                existing_key = revision.joinpath("privkey.pem")
                if not stat.S_ISREG(existing_chain.lstat().st_mode) or not stat.S_ISREG(existing_key.lstat().st_mode):
                    raise CertificateError(f"refusing unsafe certificate revision files: {revision}")
                existing_digest = self._content_digest(existing_chain.read_bytes(), existing_key.read_bytes())
            except OSError as exc:
                raise CertificateError(f"cannot validate certificate revision {revision}: {exc}") from exc
            if existing_digest != digest:
                raise CertificateError(f"certificate revision digest mismatch: {revision}")
        current_tmp = destination / f".current.{secrets.token_hex(12)}.tmp"
        try:
            os.symlink(f"revisions/{digest}", current_tmp)
            os.replace(current_tmp, destination / "current")
        finally:
            current_tmp.unlink(missing_ok=True)
        for name in ("fullchain.pem", "privkey.pem"):
            link_tmp = destination / f".{name}.{secrets.token_hex(12)}.link"
            try:
                os.symlink(f"current/{name}", link_tmp)
                os.replace(link_tmp, destination / name)
            finally:
                link_tmp.unlink(missing_ok=True)
        self._fsync_directory(destination)

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _deployment_state_path(self, cert: CertificateConfig) -> Path:
        return self.service.state_dir / "deployments" / f"{cert.name}.json"

    def _load_deployment_state(self, cert: CertificateConfig) -> dict:
        path = self._deployment_state_path(cert)
        try:
            if path.is_symlink() or (path.exists() and not path.is_file()):
                raise CertificateError(f"unsafe deployment state for {cert.name}")
            value = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError, TypeError) as exc:
            raise CertificateError(f"cannot read deployment state for {cert.name}: {exc}") from exc
        if not isinstance(value, dict):
            raise CertificateError(f"invalid deployment state for {cert.name}")
        return value

    def _write_deployment_state(self, cert: CertificateConfig, state: dict) -> None:
        self._write_private(
            self._deployment_state_path(cert),
            (json.dumps(state, sort_keys=True, separators=(",", ":")) + "\n").encode(),
        )

    @staticmethod
    def _atomic_write(target: Path, data: bytes, mode: int) -> None:
        temporary = target.with_name(f".{target.name}.{secrets.token_hex(12)}.tmp")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        created = False
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(temporary, flags, mode)
            created = True
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, mode)
            os.replace(temporary, target)
        finally:
            if created:
                temporary.unlink(missing_ok=True)

    @staticmethod
    def _write_private(target: Path, data: bytes) -> None:
        CertificateManager._ensure_safe_directory(target.parent)
        target.parent.mkdir(parents=True, exist_ok=True)
        CertificateManager._atomic_write(target, data, 0o600)

    def _reload(self, cert: CertificateConfig) -> None:
        action = cert.reload
        if action.kind == "none":
            return
        if action.kind == "command":
            self.runner.run(action.argv)
            return
        request = f"POST /containers/{quote(action.container, safe='')}/kill?signal={quote(action.signal, safe='')} HTTP/1.1\r\nHost: docker\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            client.settimeout(10)
            client.connect(str(action.socket_path))
            client.sendall(request.encode("ascii"))
            response = client.recv(256)
        finally:
            client.close()
        if b" 204 " not in response:
            raise CertificateError(f"Docker reload failed for {cert.name}")
