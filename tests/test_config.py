import tempfile
import unittest
from pathlib import Path

from cert_renewer.config import ConfigError, load_config


BASE = """
email = "ops@example.com"
state_dir = "/var/lib/cert-renewer"

[[certificates]]
name = "example"
domains = ["example.com", "*.example.com"]
token_file = "/run/secrets/example"
destination = "/etc/nginx/certs/example"

[certificates.reload]
kind = "command"
argv = ["systemctl", "reload", "nginx"]
"""


class ConfigTests(unittest.TestCase):
    def write(self, text: str) -> Path:
        directory = Path(tempfile.mkdtemp())
        path = directory / "config.toml"
        path.write_text(text, encoding="utf-8")
        return path

    def test_loads_two_independent_certificates(self):
        second = """
[[certificates]]
name = "other"
domains = ["other.kz"]
token_file = "/run/secrets/other"
destination = "/etc/nginx/certs/other"
[certificates.reload]
kind = "none"
"""
        config = load_config(self.write(BASE + second))
        self.assertEqual([item.name for item in config.certificates], ["example", "other"])
        self.assertEqual(config.certificates[0].domains, ("example.com", "*.example.com"))

    def test_normalizes_domains(self):
        config = load_config(self.write(BASE.replace("example.com\", \"*.example.com", "Example.COM.\", \"*.Example.COM.")))
        self.assertEqual(config.certificates[0].domains, ("example.com", "*.example.com"))

    def test_rejects_duplicate_names(self):
        with self.assertRaisesRegex(ConfigError, "duplicate certificate name"):
            load_config(self.write(BASE + BASE[BASE.index("[[certificates]]"):]))

    def test_rejects_duplicate_domains(self):
        duplicate = BASE.replace('["example.com", "*.example.com"]', '["example.com", "Example.COM."]')
        with self.assertRaisesRegex(ConfigError, "duplicate domain"):
            load_config(self.write(duplicate))

    def test_rejects_relative_paths(self):
        with self.assertRaisesRegex(ConfigError, "absolute"):
            load_config(self.write(BASE.replace('/run/secrets/example', 'secret.txt')))

    def test_rejects_unknown_keys(self):
        with self.assertRaisesRegex(ConfigError, "unknown"):
            load_config(self.write(BASE + "\nunexpected = true\n"))

    def test_command_reload_requires_argv(self):
        invalid = BASE.replace('argv = ["systemctl", "reload", "nginx"]', 'argv = []')
        with self.assertRaisesRegex(ConfigError, "argv"):
            load_config(self.write(invalid))


if __name__ == "__main__":
    unittest.main()
