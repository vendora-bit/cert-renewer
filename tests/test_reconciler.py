import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cert_renewer.certificate import ReconcileResult
from cert_renewer.config import load_config
from cert_renewer.reconciler import Reconciler
from cert_renewer.status import StatusStore


CONFIG = """
email = "ops@example.com"
state_dir = "{state}"
[[certificates]]
name = "first"
domains = ["first.example.com"]
token_file = "{token1}"
destination = "{out1}"
[[certificates]]
name = "second"
domains = ["second.example.com"]
token_file = "{token2}"
destination = "{out2}"
"""


class FakeManager:
    def __init__(self):
        self.calls = []

    def reconcile(self, cert):
        self.calls.append(cert.name)
        if cert.name == "first":
            raise RuntimeError("first failed with super-secret")
        return ReconcileResult(cert.name, True, datetime.now(UTC) + timedelta(days=90), "issued")


class ReconcilerTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        for name in ("token1", "token2"):
            (self.root / name).write_text("super-secret")
        text = CONFIG.format(state=self.root / "state", token1=self.root / "token1", token2=self.root / "token2", out1=self.root / "out1", out2=self.root / "out2")
        path = self.root / "config.toml"
        path.write_text(text)
        self.config = load_config(path)

    def test_failure_does_not_block_next_certificate(self):
        manager = FakeManager()
        result = Reconciler(self.config, manager, StatusStore(self.config.state_dir)).run_cycle()
        self.assertEqual(manager.calls, ["first", "second"])
        self.assertFalse(result.success)
        self.assertEqual([item.outcome for item in result.certificates], ["failed", "success"])

    def test_status_redacts_token_values(self):
        Reconciler(self.config, FakeManager(), StatusStore(self.config.state_dir)).run_cycle()
        raw = (self.config.state_dir / "status.json").read_text()
        self.assertNotIn("super-secret", raw)
        parsed = json.loads(raw)
        self.assertEqual(set(parsed["certificates"]), {"first", "second"})


if __name__ == "__main__":
    unittest.main()
