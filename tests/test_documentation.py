import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DocumentationTests(unittest.TestCase):
    def test_readme_covers_public_contract(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        for phrase in (
            "Manage multiple independent", "Quickstart", "Docker Compose",
            "systemd", "check", "once", "run", "health", "Docker socket",
            "Cloudflare", "Why not use X?", "Roadmap", "Apache-2.0",
        ):
            self.assertIn(phrase, text)

    def test_runbook_covers_operations(self):
        text = (ROOT / "RUNBOOK_TLS.md").read_text(encoding="utf-8")
        for phrase in ("Recovery", "Восстановление", "Token rotation", "Ротация токена", "status.json"):
            self.assertIn(phrase, text)

    def test_readme_links_to_each_supported_recipe(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        for variable in ("examples/nginx", "examples/haproxy", "examples/mailcow", "examples/proxmox", "examples/kubernetes", "examples/systemd"):
            self.assertIn(variable, text)


if __name__ == "__main__":
    unittest.main()
