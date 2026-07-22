import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DocumentationTests(unittest.TestCase):
    def test_readme_covers_public_contract(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        for phrase in (
            "Cert Renewer v2", "Русский", "English", "[[certificates]]",
            "Docker Compose", "systemd", "check", "once", "run", "health",
            "Docker socket", "staging", "Cloudflare",
        ):
            self.assertIn(phrase, text)

    def test_runbook_covers_operations(self):
        text = (ROOT / "RUNBOOK_TLS.md").read_text(encoding="utf-8")
        for phrase in ("Recovery", "Восстановление", "Token rotation", "Ротация токена", "status.json"):
            self.assertIn(phrase, text)

    def test_migration_maps_v1_variables(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        for variable in ("CERTBOT_CERT_NAME", "CERTBOT_PRIMARY_DOMAIN", "CERTBOT_EXTRA_DOMAINS", "CLOUDFLARE_API_TOKEN_FILE"):
            self.assertIn(variable, text)


if __name__ == "__main__":
    unittest.main()
