import argparse
import fcntl
import json
import shutil
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

from .certificate import CertificateManager
from .config import ConfigError, load_config
from .reconciler import Reconciler
from .status import StatusStore


class ServiceLockError(RuntimeError):
    pass


class ServiceLock:
    def __init__(self, path: Path):
        self.path = path
        self.handle: TextIO | None = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+")
        self.handle = handle
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            handle.close()
            self.handle = None
            raise ServiceLockError("another cert-renewer process is running") from exc

    def release(self) -> None:
        if self.handle is not None:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            self.handle.close()
            self.handle = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.release()


def log(level: str, event: str, **fields) -> None:
    payload = {"timestamp": datetime.now(UTC).isoformat(), "level": level, "event": event, **fields}
    print(json.dumps(payload, sort_keys=True), file=sys.stderr, flush=True)


def check_environment(config) -> list[str]:
    errors: list[str] = []
    for executable in (config.certbot_executable, config.openssl_executable):
        if shutil.which(executable) is None:
            errors.append(f"executable not found: {executable}")
    for cert in config.certificates:
        try:
            if cert.token_file.is_symlink() or not cert.token_file.is_file():
                errors.append(f"token file must be a regular non-symlink file: {cert.token_file}")
                continue
            mode = cert.token_file.stat().st_mode & 0o777
            if mode & 0o077:
                errors.append(f"token file permissions must be 0600 or stricter: {cert.token_file}")
            raw_token = cert.token_file.read_text(encoding="utf-8")
            lines = raw_token.splitlines()
            if len(lines) != 1 or not lines[0] or lines[0] != lines[0].strip():
                errors.append(f"token file must contain one nonempty line: {cert.token_file}")
        except OSError as exc:
            errors.append(f"token file unavailable: {cert.token_file}: {exc}")
    return errors


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="cert-renewer")
    result.add_argument("command", choices=("check", "once", "run", "health"))
    result.add_argument("--config", type=Path, default=Path("/etc/cert-renewer/config.toml"))
    return result


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        config = load_config(args.config)
        status = StatusStore(config.state_dir)
        if args.command == "health":
            return 0 if status.healthy(config.interval_seconds * 2 + config.retry_seconds) else 1
        errors = check_environment(config)
        if errors:
            for message in errors:
                log("error", "configuration_check_failed", error=message)
            return 2
        if args.command == "check":
            log("info", "configuration_valid", certificates=len(config.certificates))
            return 0
        with ServiceLock(config.state_dir / "service.lock"):
            reconciler = Reconciler(config, CertificateManager(config), status)
            if args.command == "once":
                return 0 if reconciler.run_cycle().success else 1
            delay = config.retry_seconds
            while True:
                cycle = reconciler.run_cycle()
                if cycle.success:
                    delay = config.retry_seconds
                    time.sleep(config.interval_seconds)
                else:
                    time.sleep(delay)
                    delay = min(config.interval_seconds, delay * 2, config.retry_seconds * 8)
    except (ConfigError, ServiceLockError, OSError) as exc:
        log("error", "startup_failed", error=str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
