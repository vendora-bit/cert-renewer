import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DistributionTests(unittest.TestCase):
    def text(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_dockerfile_is_pinned_and_has_healthcheck(self):
        dockerfile = self.text("Dockerfile")
        self.assertNotIn("dns-cloudflare:latest", dockerfile)
        self.assertIn("HEALTHCHECK", dockerfile)
        self.assertIn('["python", "-m", "cert_renewer"', dockerfile)

    def test_default_compose_has_no_docker_socket(self):
        compose = self.text("docker/compose.yaml")
        self.assertNotIn("/var/run/docker.sock", compose)
        self.assertIn("config.toml", compose)

    def test_socket_mount_is_only_in_optional_override(self):
        override = self.text("docker/compose.socket.yaml")
        self.assertIn("/var/run/docker.sock", override)

    def test_systemd_unit_restarts_on_failure(self):
        unit = self.text("systemd/cert-renewer.service")
        self.assertIn("Restart=on-failure", unit)
        self.assertIn("python3 -m cert_renewer run", unit)
        self.assertIn("NoNewPrivileges=true", unit)

    def test_installer_preserves_existing_config(self):
        installer = self.text("systemd/install.sh")
        self.assertIn('if [ ! -e "$CONFIG_PATH" ]', installer)
        self.assertIn("--enable", installer)


if __name__ == "__main__":
    unittest.main()
