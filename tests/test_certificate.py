import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cert_renewer.certificate import CertificateError, CertificateInfo, CertificateManager
from cert_renewer.model import CertificateConfig, ReloadAction, ServiceConfig
from cert_renewer.process import ProcessResult


class FakeRunner:
    def __init__(self, lineage: Path):
        self.lineage = lineage
        self.calls: list[tuple[str, ...]] = []

    def run(self, argv, *, input_text=None):
        call = tuple(str(item) for item in argv)
        self.calls.append(call)
        if call[0] == "certbot":
            self.lineage.mkdir(parents=True, exist_ok=True)
            (self.lineage / "fullchain.pem").write_text("new-chain", encoding="utf-8")
            (self.lineage / "privkey.pem").write_text("new-key", encoding="utf-8")
        return ProcessResult(0, "", "")


class FakeInspector:
    def __init__(self, *infos: CertificateInfo):
        self.infos = list(infos)

    def inspect(self, chain: Path, key: Path) -> CertificateInfo:
        if len(self.infos) > 1:
            return self.infos.pop(0)
        return self.infos[0]


class CertificateManagerTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.config_dir = self.root / "letsencrypt"
        self.lineage = self.config_dir / "live" / "example"
        self.destination = self.root / "out"
        self.token = self.root / "token"
        self.token.write_text("super-secret-token", encoding="utf-8")
        self.reload_marker = self.root / "reloaded"
        self.cert = CertificateConfig(
            name="example", domains=("example.com", "*.example.com"),
            token_file=self.token, propagation_seconds=30,
            destination=self.destination,
            reload=ReloadAction(kind="command", argv=("reload-command",)),
        )
        self.service = ServiceConfig(
            email="ops@example.com", acme_server="https://acme.test/directory",
            interval_seconds=3600, renewal_threshold_seconds=86400,
            retry_seconds=60, state_dir=self.root / "state",
            certbot_config_dir=self.config_dir, certbot_work_dir=self.root / "work",
            certbot_logs_dir=self.root / "logs", certbot_executable="certbot",
            openssl_executable="openssl", certificates=(self.cert,),
        )

    def manager(self, expiry_days=90, domains=None, key_matches=True):
        info = CertificateInfo(
            expires_at=datetime.now(UTC) + timedelta(days=expiry_days),
            domains=frozenset(domains or self.cert.domains), key_matches=key_matches,
        )
        renewed = CertificateInfo(
            expires_at=datetime.now(UTC) + timedelta(days=90),
            domains=frozenset(domains or self.cert.domains), key_matches=key_matches,
        )
        runner = FakeRunner(self.lineage)
        inspector = FakeInspector(info, renewed) if expiry_days <= 1 else FakeInspector(info)
        return CertificateManager(self.service, runner=runner, inspector=inspector), runner

    def install_old_destination(self):
        self.destination.mkdir(parents=True)
        (self.destination / "fullchain.pem").write_text("old-chain")
        (self.destination / "privkey.pem").write_text("old-key")

    def test_issues_missing_certificate_with_all_domains(self):
        manager, runner = self.manager()
        result = manager.reconcile(self.cert)
        certbot = next(call for call in runner.calls if call[0] == "certbot")
        self.assertEqual(result.action, "issued")
        self.assertIn(("-d", "example.com"), tuple(zip(certbot, certbot[1:])))
        self.assertIn(("-d", "*.example.com"), tuple(zip(certbot, certbot[1:])))
        self.assertEqual((self.destination / "fullchain.pem").read_text(), "new-chain")

    def test_skips_healthy_certificate(self):
        self.lineage.mkdir(parents=True)
        (self.lineage / "fullchain.pem").write_text("old-chain")
        (self.lineage / "privkey.pem").write_text("old-key")
        self.install_old_destination()
        manager, runner = self.manager(expiry_days=90)
        result = manager.reconcile(self.cert)
        self.assertFalse(result.changed)
        self.assertFalse(any(call[0] == "certbot" for call in runner.calls))

    def test_renews_expiring_certificate(self):
        self.lineage.mkdir(parents=True)
        (self.lineage / "fullchain.pem").write_text("old-chain")
        (self.lineage / "privkey.pem").write_text("old-key")
        self.install_old_destination()
        manager, runner = self.manager(expiry_days=0)
        result = manager.reconcile(self.cert)
        self.assertEqual(result.action, "renewed")
        self.assertTrue(any(call[0] == "certbot" for call in runner.calls))

    def test_rejects_mismatched_key(self):
        manager, _ = self.manager(key_matches=False)
        with self.assertRaisesRegex(CertificateError, "private key"):
            manager.reconcile(self.cert)

    def test_rejects_missing_domain(self):
        manager, _ = self.manager(domains=("example.com",))
        with self.assertRaisesRegex(CertificateError, "missing domains"):
            manager.reconcile(self.cert)

    def test_reload_only_runs_after_changed_install(self):
        self.lineage.mkdir(parents=True)
        (self.lineage / "fullchain.pem").write_text("old-chain")
        (self.lineage / "privkey.pem").write_text("old-key")
        self.install_old_destination()
        manager, runner = self.manager(expiry_days=90)
        manager.reconcile(self.cert)
        self.assertNotIn(("reload-command",), runner.calls)
        manager, runner = self.manager(expiry_days=0)
        manager.reconcile(self.cert)
        self.assertIn(("reload-command",), runner.calls)


if __name__ == "__main__":
    unittest.main()
