# Socket-free Docker Compose

This is the default production pattern: cert-renewer owns ACME state and writes
to a named certificate volume. A proxy can consume that volume read-only. The
Docker socket is not mounted.

```bash
cp config.toml.example config.toml
sudo install -d -o 65532 -g 65532 -m 0750 secrets
printf '%s' "$CLOUDFLARE_DNS_API_TOKEN" | sudo tee secrets/cloudflare-example >/dev/null
sudo chown 65532:65532 secrets/cloudflare-example
sudo chmod 0400 secrets/cloudflare-example
docker compose run --rm cert-renewer check
docker compose up -d
```

Run `docker compose run --rm cert-renewer once` to issue immediately. Use an
external, narrowly scoped deployment or reload hook for a proxy; do not grant
the certificate service Docker socket access merely to signal another container.
