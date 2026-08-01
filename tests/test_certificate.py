import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from pathlib import Path
from unittest.mock import patch

from cert_renewer.certificate import (
    CertificateError,
    CertificateInfo,
    CertificateManager,
)
from cert_renewer.model import CertificateConfig, ReloadAction, ServiceConfig
from cert_renewer.process import ProcessResult


class FakeRunner:
    def __init__(self, lineage: Path, *, fail_reload: bool = False):
        self.lineage = lineage
        self.fail_reload = fail_reload
        self.calls: list[tuple[str, ...]] = []

    def run(self, argv, *, input_text=None):
        call = tuple(str(item) for item in argv)
        self.calls.append(call)
        if call[0] == "certbot":
            self.lineage.mkdir(parents=True, exist_ok=True)
            (self.lineage / "fullchain.pem").write_text("new-chain", encoding="utf-8")
            (self.lineage / "privkey.pem").write_text("new-key", encoding="utf-8")
        if call[0] == "reload-command" and self.fail_reload:
            raise RuntimeError("reload failed")
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

    def manager(self, expiry_days=90, domains=None, key_matches=True, *, fail_reload=False, renewed_domains=None, renewal_server=None):
        info = CertificateInfo(
            expires_at=datetime.now(UTC) + timedelta(days=expiry_days),
            domains=frozenset(domains or self.cert.domains), key_matches=key_matches,
        )
        renewed = CertificateInfo(
            expires_at=datetime.now(UTC) + timedelta(days=90),
            domains=frozenset(renewed_domains or domains or self.cert.domains), key_matches=key_matches,
        )
        runner = FakeRunner(self.lineage, fail_reload=fail_reload)
        if renewal_server is not None:
            renewal = self.config_dir / "renewal"
            renewal.mkdir(parents=True, exist_ok=True)
            (renewal / "example.conf").write_text(f"[renewalparams]\nserver = {renewal_server}\n")
        needs_second_inspection = expiry_days <= 1 or set(info.domains) != set(self.cert.domains) or renewal_server not in (None, self.service.acme_server)
        inspector = FakeInspector(info, renewed) if needs_second_inspection else FakeInspector(info)
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
        self.assertIn(("-d", "example.com"), tuple(pairwise(certbot)))
        self.assertIn(("-d", "*.example.com"), tuple(pairwise(certbot)))
        self.assertEqual((self.destination / "current" / "fullchain.pem").read_text(), "new-chain")
        self.assertTrue((self.destination / "fullchain.pem").is_symlink())
        self.assertFalse(any(self.service.state_dir.glob(".cloudflare-*.ini")))

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

    def test_reissues_immediately_when_domain_set_changes(self):
        self.lineage.mkdir(parents=True)
        (self.lineage / "fullchain.pem").write_text("old-chain")
        (self.lineage / "privkey.pem").write_text("old-key")
        self.install_old_destination()
        manager, runner = self.manager(domains=("example.com",), renewed_domains=self.cert.domains)
        result = manager.reconcile(self.cert)
        self.assertEqual(result.action, "reissued-domains-changed")
        self.assertTrue(any(call[0] == "certbot" for call in runner.calls))

    def test_reissues_immediately_when_acme_server_changes(self):
        self.lineage.mkdir(parents=True)
        (self.lineage / "fullchain.pem").write_text("old-chain")
        (self.lineage / "privkey.pem").write_text("old-key")
        self.install_old_destination()
        manager, runner = self.manager(renewal_server="https://old-acme.test/directory")
        result = manager.reconcile(self.cert)
        self.assertEqual(result.action, "reissued-parameters-changed")
        self.assertTrue(any(call[0] == "certbot" for call in runner.calls))

    def test_rejects_mismatched_key(self):
        manager, _ = self.manager(key_matches=False)
        with self.assertRaisesRegex(CertificateError, "private key"):
            manager.reconcile(self.cert)

    def test_rejects_missing_domain(self):
        manager, _ = self.manager(domains=("example.com",))
        with self.assertRaisesRegex(CertificateError, "missing domains"):
            manager.reconcile(self.cert)

    def test_rejects_multiline_token_file(self):
        self.token.write_text("secret\ninjected = value\n")
        manager, _ = self.manager()
        with self.assertRaisesRegex(CertificateError, "one nonempty line"):
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

    def test_failed_reload_is_retried_without_reinstalling(self):
        manager, runner = self.manager(fail_reload=True)
        with self.assertRaisesRegex(RuntimeError, "reload failed"):
            manager.reconcile(self.cert)
        state_path = self.service.state_dir / "deployments" / "example.json"
        self.assertIn('"reload_pending":true', state_path.read_text())

        manager, runner = self.manager()
        result = manager.reconcile(self.cert)
        self.assertFalse(result.changed)
        self.assertEqual(result.action, "reload-retried")
        self.assertIn(("reload-command",), runner.calls)
        self.assertIn('"reload_pending":false', state_path.read_text())

    def test_rejects_unmanaged_symlink_before_reading_destination(self):
        self.destination.mkdir(parents=True)
        outside = self.root / "outside"
        outside.write_text("old-chain")
        (self.destination / "fullchain.pem").symlink_to(outside)
        (self.destination / "privkey.pem").write_text("old-key")
        self.lineage.mkdir(parents=True)
        (self.lineage / "fullchain.pem").write_text("old-chain")
        (self.lineage / "privkey.pem").write_text("old-key")
        manager, _ = self.manager()
        with self.assertRaisesRegex(CertificateError, "non-regular certificate target"):
            manager.reconcile(self.cert)

    def test_repairs_partial_compatibility_link_migration(self):
        manager, _ = self.manager()
        manager.reconcile(self.cert)
        (self.destination / "fullchain.pem").unlink()
        (self.destination / "fullchain.pem").write_text("interrupted-legacy-file")

        manager, _ = self.manager()
        result = manager.reconcile(self.cert)
        self.assertTrue(result.changed)
        self.assertTrue((self.destination / "fullchain.pem").is_symlink())
        self.assertEqual((self.destination / "fullchain.pem").read_text(), "new-chain")

    def test_atomic_write_does_not_delete_colliding_file(self):
        target = self.root / "value"
        collision = target.with_name(".value.collision.tmp")
        collision.write_text("belongs-to-another-process")
        with (
            patch("cert_renewer.certificate.secrets.token_hex", return_value="collision"),
            self.assertRaises(FileExistsError),
        ):
            CertificateManager._atomic_write(target, b"new", 0o600)
        self.assertEqual(collision.read_text(), "belongs-to-another-process")


if __name__ == "__main__":
    unittest.main()
