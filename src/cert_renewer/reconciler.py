import json
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from .model import ServiceConfig
from .status import StatusStore


@dataclass(frozen=True)
class CertificateOutcome:
    name: str
    outcome: str
    action: str
    changed: bool
    expires_at: str | None
    error: str | None


@dataclass(frozen=True)
class CycleResult:
    success: bool
    certificates: tuple[CertificateOutcome, ...]


class Reconciler:
    def __init__(self, config: ServiceConfig, manager, status: StatusStore,
                 logger: Callable[[dict], None] | None = None):
        self.config = config
        self.manager = manager
        self.status = status
        self.logger = logger or self._default_logger
        self.secrets = tuple(
            cert.token_file.read_text(encoding="utf-8").strip()
            for cert in config.certificates if cert.token_file.is_file()
        )

    @staticmethod
    def _default_logger(event: dict) -> None:
        print(json.dumps(event, sort_keys=True), file=sys.stderr, flush=True)

    def _sanitize(self, message: str) -> str:
        clean = message
        for secret in self.secrets:
            if secret:
                clean = clean.replace(secret, "[REDACTED]")
        return clean[-1000:]

    def run_cycle(self) -> CycleResult:
        outcomes: list[CertificateOutcome] = []
        for cert in self.config.certificates:
            started = time.monotonic()
            try:
                result = self.manager.reconcile(cert)
                outcome = CertificateOutcome(cert.name, "success", result.action,
                                             result.changed, result.expires_at.isoformat(), None)
            except Exception as exc:  # noqa: BLE001 - isolate failures by certificate
                outcome = CertificateOutcome(cert.name, "failed", "failed", False,
                                             None, self._sanitize(str(exc)))
            outcomes.append(outcome)
            self.logger({"timestamp": datetime.now(UTC).isoformat(), "event": "certificate_reconciled",
                         "certificate": cert.name, "outcome": outcome.outcome,
                         "action": outcome.action,
                         "duration_ms": round((time.monotonic() - started) * 1000)})
        cycle = CycleResult(all(item.outcome == "success" for item in outcomes), tuple(outcomes))
        self.status.write_raw({
            "updated_at": datetime.now(UTC).isoformat(),
            "success": cycle.success,
            "certificates": {item.name: {
                "outcome": item.outcome, "action": item.action, "changed": item.changed,
                "expires_at": item.expires_at, "error": item.error,
            } for item in outcomes},
        })
        return cycle
