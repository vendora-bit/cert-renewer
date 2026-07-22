import os
import re
import socket
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
            if remaining <= self.service.renewal_threshold_seconds:
                self._certbot(cert, force=True)
                action = "renewed"
        if not chain.is_file() or not key.is_file():
            raise CertificateError(f"certbot did not produce lineage {cert.name}")
        info = self.inspector.inspect(chain, key)
        self._validate(cert, info)
        changed = self._changed(cert.destination, chain, key)
        if changed:
            self._install(cert.destination, chain, key)
            self._reload(cert)
            if action == "unchanged":
                action = "installed"
        return ReconcileResult(cert.name, changed, info.expires_at, action)

    def _certbot(self, cert: CertificateConfig, *, force: bool) -> None:
        self.service.state_dir.mkdir(parents=True, exist_ok=True)
        credentials = self.service.state_dir / f"cloudflare-{cert.name}.ini"
        token = cert.token_file.read_text(encoding="utf-8").strip()
        if not token:
            raise CertificateError(f"empty Cloudflare token for {cert.name}")
        self._write_private(credentials, f"dns_cloudflare_api_token = {token}\n".encode())
        argv = [self.service.certbot_executable, "certonly", "--non-interactive", "--agree-tos", "--email", self.service.email, "--dns-cloudflare", "--dns-cloudflare-credentials", str(credentials), "--dns-cloudflare-propagation-seconds", str(cert.propagation_seconds), "--cert-name", cert.name, "--config-dir", str(self.service.certbot_config_dir), "--work-dir", str(self.service.certbot_work_dir), "--logs-dir", str(self.service.certbot_logs_dir), "--server", self.service.acme_server]
        if force:
            argv.append("--force-renewal")
        for domain in cert.domains:
            argv.extend(["-d", domain])
        try:
            self.runner.run(argv)
        except Exception as exc:
            raise CertificateError(str(exc).replace(token, "[REDACTED]")) from exc

    @staticmethod
    def _validate(cert: CertificateConfig, info: CertificateInfo) -> None:
        if not info.key_matches:
            raise CertificateError(f"private key does not match certificate {cert.name}")
        missing = set(cert.domains) - set(info.domains)
        if missing:
            raise CertificateError(f"certificate {cert.name} is missing domains: {', '.join(sorted(missing))}")
        if info.expires_at <= datetime.now(UTC):
            raise CertificateError(f"certificate {cert.name} is expired")

    @staticmethod
    def _changed(destination: Path, chain: Path, key: Path) -> bool:
        target_chain, target_key = destination / "fullchain.pem", destination / "privkey.pem"
        return not target_chain.is_file() or not target_key.is_file() or target_chain.read_bytes() != chain.read_bytes() or target_key.read_bytes() != key.read_bytes()

    def _install(self, destination: Path, chain: Path, key: Path) -> None:
        destination.mkdir(parents=True, exist_ok=True)
        for name in ("fullchain.pem", "privkey.pem"):
            target = destination / name
            if target.is_symlink():
                raise CertificateError(f"refusing symlink destination: {target}")
        self._atomic_write(destination / "fullchain.pem", chain.read_bytes(), 0o644)
        self._atomic_write(destination / "privkey.pem", key.read_bytes(), 0o600)

    @staticmethod
    def _atomic_write(target: Path, data: bytes, mode: int) -> None:
        temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(temporary, flags, mode)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, mode)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _write_private(target: Path, data: bytes) -> None:
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
