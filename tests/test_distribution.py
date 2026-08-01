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
        self.assertIn("USER 65532:65532", dockerfile)

    def test_default_compose_has_no_docker_socket(self):
        compose = self.text("docker/compose.yaml")
        self.assertNotIn("/var/run/docker.sock", compose)
        self.assertIn("config.toml", compose)
        self.assertIn("read_only: true", compose)
        self.assertIn("no-new-privileges:true", compose)
        self.assertIn("cap_drop:", compose)

    def test_socket_mount_is_only_in_optional_override(self):
        override = self.text("docker/compose.socket.yaml")
        self.assertIn("/var/run/docker.sock", override)

    def test_systemd_unit_restarts_on_failure(self):
        unit = self.text("systemd/cert-renewer.service")
        self.assertIn("Restart=on-failure", unit)
        self.assertIn("python3 -m cert_renewer run", unit)
        self.assertIn("NoNewPrivileges=true", unit)
        self.assertIn("User=cert-renewer", unit)
        self.assertIn("ProtectSystem=strict", unit)
        self.assertIn("CapabilityBoundingSet=", unit)

    def test_installer_preserves_existing_config(self):
        installer = self.text("systemd/install.sh")
        self.assertIn('if [ ! -e "$CONFIG_PATH" ]', installer)
        self.assertIn("--enable", installer)

    def test_repository_has_license_and_security_scanning(self):
        self.assertIn("Apache License", self.text("LICENSE"))
        workflow = self.text(".github/workflows/ci.yml")
        for check in ("ruff check", "mypy", "bandit", "shellcheck", "trivy-action", "systemd-analyze verify"):
            self.assertIn(check, workflow)
        self.assertIn("tests/e2e/compose.yaml", workflow)

    def test_docker_context_excludes_local_secrets(self):
        dockerignore = self.text(".dockerignore")
        self.assertIn("docker/secrets", dockerignore)
        self.assertIn("docker/config.toml", dockerignore)

    def test_entrypoint_defaults_to_documented_container_config(self):
        entrypoint = self.text("docker/entrypoint.sh")
        self.assertIn("/config/config.toml", entrypoint)
        self.assertIn('" --config "', entrypoint)
        self.assertIn('" --config="', entrypoint)


if __name__ == "__main__":
    unittest.main()
