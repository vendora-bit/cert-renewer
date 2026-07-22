from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class ReloadAction:
    kind: Literal["none", "command", "docker-signal"]
    argv: tuple[str, ...] = ()
    container: str = ""
    signal: str = "HUP"
    socket_path: Path = Path("/var/run/docker.sock")


@dataclass(frozen=True)
class CertificateConfig:
    name: str
    domains: tuple[str, ...]
    token_file: Path
    propagation_seconds: int
    destination: Path
    reload: ReloadAction


@dataclass(frozen=True)
class ServiceConfig:
    email: str
    acme_server: str
    interval_seconds: int
    renewal_threshold_seconds: int
    retry_seconds: int
    state_dir: Path
    certbot_config_dir: Path
    certbot_work_dir: Path
    certbot_logs_dir: Path
    certbot_executable: str
    openssl_executable: str
    certificates: tuple[CertificateConfig, ...]
