# Changelog

All notable changes are documented here. This project follows
[Semantic Versioning](https://semver.org/).

## [2.0.0] - 2026-08-01

### Added

- Independent certificate lineages with JSON status, health checks and retryable reloads.
- Cloudflare DNS-01, Docker, Compose and hardened systemd deployments.
- Atomic certificate/key revisions, local Pebble end-to-end coverage and security checks.
- Production recipes for Nginx, HAProxy, Mailcow, Proxmox, Kubernetes, Compose and systemd.

### Security

- The default container runs without the Docker socket, as an unprivileged user.
- Token files are validated, never logged and removed from Certbot's temporary credentials path.

[2.0.0]: https://github.com/vendora-bit/cert-renewer/releases/tag/v2.0.0

