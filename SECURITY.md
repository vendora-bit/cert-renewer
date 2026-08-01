# Security policy

## Supported versions

Security fixes are applied to the latest released major version.

| Version | Supported |
| --- | --- |
| 2.x | Yes |
| Earlier versions | No |

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability or include tokens,
private keys, certificate material, hostnames that reveal sensitive topology,
or Docker socket paths in an issue.

Use GitHub's private vulnerability reporting for this repository. If it is not
enabled yet, contact the maintainers through the organization profile with a
minimal reproduction and an encrypted contact method. We will acknowledge a
report within seven days and coordinate a fix before public disclosure.

## Security model

The standard Docker deployment does not mount `/var/run/docker.sock`. The
container runs as UID/GID 65532 with a read-only root filesystem, dropped
capabilities and `no-new-privileges`. Treat the optional socket override as
host-root equivalent access. Keep Cloudflare API tokens least-privileged and
readable only by the service account.

