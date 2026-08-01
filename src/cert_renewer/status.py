import json
import os
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class StatusStore:
    def __init__(self, state_dir: Path):
        self.state_dir = state_dir
        self.path = state_dir / "status.json"

    def write_raw(self, payload: dict[str, Any]) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".status.{secrets.token_hex(12)}.tmp")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        created = False
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(temporary, flags, 0o600)
            created = True
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, self.path)
        finally:
            if created:
                temporary.unlink(missing_ok=True)

    def healthy(self, max_age_seconds: int) -> bool:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            updated = datetime.fromisoformat(payload["updated_at"])
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=UTC)
            age = (datetime.now(UTC) - updated.astimezone(UTC)).total_seconds()
            return payload.get("success") is True and 0 <= age <= max_age_seconds
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            return False
