# GitHub metadata for the v2.0.0 release

Apply these settings in the repository's About and social-preview pages when
publishing the release.

| Setting | Value |
| --- | --- |
| Description | Manage independent Let's Encrypt certificate lineages with Cloudflare DNS-01, atomic installation and health checks. |
| Homepage | https://vendora-bit.github.io/ |
| Topics | letsencrypt, acme, certbot, tls, ssl, cloudflare, dns-01, docker, systemd, self-hosted |
| Social preview | assets/social-preview.png |
| Release tag | v2.0.0 |
| Container | ghcr.io/vendora-bit/cert-renewer:2.0.0 and latest |

The release workflow publishes the GitHub Release and GHCR image after the tag
lands on GitHub. Mark the package public in GHCR after the first publish.

