import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cert_renewer.cli import ServiceLock, ServiceLockError
from cert_renewer.status import StatusStore


class CliTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())

    def test_second_process_cannot_acquire_lock(self):
        first = ServiceLock(self.root / "service.lock")
        second = ServiceLock(self.root / "service.lock")
        first.acquire()
        try:
            with self.assertRaises(ServiceLockError):
                second.acquire()
        finally:
            first.release()

    def test_health_rejects_failed_and_stale_status(self):
        store = StatusStore(self.root)
        store.write_raw({"updated_at": datetime.now(UTC).isoformat(), "success": False, "certificates": {}})
        self.assertFalse(store.healthy(max_age_seconds=60))
        store.write_raw({"updated_at": (datetime.now(UTC) - timedelta(hours=2)).isoformat(), "success": True, "certificates": {}})
        self.assertFalse(store.healthy(max_age_seconds=60))

    def test_health_accepts_recent_success(self):
        store = StatusStore(self.root)
        store.write_raw({"updated_at": datetime.now(UTC).isoformat(), "success": True, "certificates": {}})
        self.assertTrue(store.healthy(max_age_seconds=60))


if __name__ == "__main__":
    unittest.main()
