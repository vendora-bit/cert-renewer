import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import tomllib

from .model import CertificateConfig, ReloadAction, ServiceConfig


class ConfigError(ValueError):
    pass


ROOT_KEYS = {"email", "acme_server", "interval_seconds", "renewal_threshold_seconds", "retry_seconds", "state_dir", "certbot_config_dir", "certbot_work_dir", "certbot_logs_dir", "certbot_executable", "openssl_executable", "certificates"}
CERT_KEYS = {"name", "domains", "token_file", "propagation_seconds", "destination", "reload"}
RELOAD_KEYS = {"kind", "argv", "container", "signal", "socket_path"}
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
DOMAIN_RE = re.compile(r"^(?:\*\.)?(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
SIGNAL_RE = re.compile(r"^(?:SIG)?(?:[A-Z][A-Z0-9]*|[1-9][0-9]?)$")


def _unknown(data: dict[str, Any], allowed: set[str], context: str) -> None:
    extra = sorted(set(data) - allowed)
    if extra:
        raise ConfigError(f"unknown {context} key: {extra[0]}")


def _absolute(value: Any, field: str) -> Path:
    if not isinstance(value, str) or not Path(value).is_absolute():
        raise ConfigError(f"{field} must be an absolute path")
    return Path(os.path.normpath(value))


def _positive(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ConfigError(f"{field} must be a positive integer")
    return value


def _bounded(value: Any, field: str, minimum: int, maximum: int) -> int:
    result = _positive(value, field)
    if not minimum <= result <= maximum:
        raise ConfigError(f"{field} must be between {minimum} and {maximum}")
    return result


def _overlaps(left: Path, right: Path) -> bool:
    return left == right or left.is_relative_to(right) or right.is_relative_to(left)


def _reload(raw: Any, name: str) -> ReloadAction:
    if raw is None:
        return ReloadAction(kind="none")
    if not isinstance(raw, dict):
        raise ConfigError(f"reload for {name} must be a table")
    _unknown(raw, RELOAD_KEYS, "reload")
    kind = raw.get("kind", "none")
    if kind not in {"none", "command", "docker-signal"}:
        raise ConfigError(f"invalid reload kind for {name}")
    argv_raw = raw.get("argv", [])
    if not isinstance(argv_raw, list) or any(not isinstance(item, str) or not item for item in argv_raw):
        raise ConfigError(f"reload argv for {name} must contain strings")
    if kind == "command" and not argv_raw:
        raise ConfigError(f"reload argv for {name} is required")
    container = raw.get("container", "")
    if kind == "docker-signal" and (not isinstance(container, str) or not container):
        raise ConfigError(f"reload container for {name} is required")
    signal = raw.get("signal", "HUP")
    if not isinstance(signal, str) or not SIGNAL_RE.fullmatch(signal.upper()):
        raise ConfigError(f"invalid Docker signal for {name}")
    socket_path = _absolute(raw.get("socket_path", "/var/run/docker.sock"), "reload socket_path")
    return ReloadAction(kind=kind, argv=tuple(argv_raw), container=container, signal=signal.upper(), socket_path=socket_path)


def load_config(path: Path) -> ServiceConfig:
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"cannot read configuration: {exc}") from exc
    _unknown(raw, ROOT_KEYS, "root")
    email = raw.get("email")
    if not isinstance(email, str) or "@" not in email or email.startswith("@") or email.endswith("@"):
        raise ConfigError("email must be valid")
    entries = raw.get("certificates")
    if not isinstance(entries, list) or not entries:
        raise ConfigError("at least one certificate is required")
    acme_server = raw.get("acme_server", "https://acme-v02.api.letsencrypt.org/directory")
    if not isinstance(acme_server, str):
        raise ConfigError("acme_server must be an HTTPS URL")
    parsed_acme = urlsplit(acme_server)
    if parsed_acme.scheme != "https" or not parsed_acme.netloc or parsed_acme.username or parsed_acme.fragment:
        raise ConfigError("acme_server must be an HTTPS URL without credentials or fragment")
    state_dir = _absolute(raw.get("state_dir", "/var/lib/cert-renewer"), "state_dir")
    certbot_config_dir = _absolute(raw.get("certbot_config_dir", "/etc/letsencrypt"), "certbot_config_dir")
    certbot_work_dir = _absolute(raw.get("certbot_work_dir", "/var/lib/letsencrypt"), "certbot_work_dir")
    certbot_logs_dir = _absolute(raw.get("certbot_logs_dir", "/var/log/letsencrypt"), "certbot_logs_dir")
    certificates: list[CertificateConfig] = []
    names: set[str] = set()
    for index, item in enumerate(entries):
        if not isinstance(item, dict):
            raise ConfigError(f"certificate {index} must be a table")
        _unknown(item, CERT_KEYS, "certificate")
        name = item.get("name")
        if not isinstance(name, str) or not NAME_RE.fullmatch(name):
            raise ConfigError(f"invalid certificate name at index {index}")
        if name in names:
            raise ConfigError(f"duplicate certificate name: {name}")
        names.add(name)
        domains_raw = item.get("domains")
        if not isinstance(domains_raw, list) or not domains_raw:
            raise ConfigError(f"domains for {name} must be a nonempty array")
        domains: list[str] = []
        seen: set[str] = set()
        for value in domains_raw:
            if not isinstance(value, str):
                raise ConfigError(f"domain for {name} must be a string")
            domain = value.strip().lower().rstrip(".")
            if not DOMAIN_RE.fullmatch(domain):
                raise ConfigError(f"invalid domain for {name}: {domain}")
            if domain in seen:
                raise ConfigError(f"duplicate domain for {name}: {domain}")
            seen.add(domain)
            domains.append(domain)
        certificates.append(CertificateConfig(name=name, domains=tuple(domains), token_file=_absolute(item.get("token_file"), f"token_file for {name}"), propagation_seconds=_bounded(item.get("propagation_seconds", 90), "propagation_seconds", 10, 3600), destination=_absolute(item.get("destination"), f"destination for {name}"), reload=_reload(item.get("reload"), name)))

    managed_dirs = (state_dir, certbot_config_dir, certbot_work_dir, certbot_logs_dir)
    for index, cert in enumerate(certificates):
        for other in certificates[:index]:
            if _overlaps(cert.destination, other.destination):
                raise ConfigError(f"overlapping certificate destinations: {other.name} and {cert.name}")
        for managed in managed_dirs:
            if _overlaps(cert.destination, managed):
                raise ConfigError(f"destination for {cert.name} overlaps managed directory: {managed}")
        if cert.token_file.is_relative_to(cert.destination):
            raise ConfigError(f"token_file for {cert.name} must not be inside destination")

    certbot_executable = raw.get("certbot_executable", "certbot")
    openssl_executable = raw.get("openssl_executable", "openssl")
    if not isinstance(certbot_executable, str) or not certbot_executable:
        raise ConfigError("certbot_executable must be a nonempty string")
    if not isinstance(openssl_executable, str) or not openssl_executable:
        raise ConfigError("openssl_executable must be a nonempty string")
    return ServiceConfig(
        email=email,
        acme_server=acme_server,
        interval_seconds=_bounded(raw.get("interval_seconds", 43200), "interval_seconds", 60, 604800),
        renewal_threshold_seconds=_bounded(raw.get("renewal_threshold_seconds", 2592000), "renewal_threshold_seconds", 3600, 5184000),
        retry_seconds=_bounded(raw.get("retry_seconds", 300), "retry_seconds", 5, 86400),
        state_dir=state_dir,
        certbot_config_dir=certbot_config_dir,
        certbot_work_dir=certbot_work_dir,
        certbot_logs_dir=certbot_logs_dir,
        certbot_executable=certbot_executable,
        openssl_executable=openssl_executable,
        certificates=tuple(certificates),
    )
