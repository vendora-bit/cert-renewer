# Nginx: consume a shared certificate volume

1. Copy `config.toml.example` to `config.toml`, create
   `secrets/cloudflare-example` with mode `0600`, and replace the example
   domain.
2. Issue the first certificate before starting Nginx:

   ```bash
   docker compose run --rm cert-renewer once
   docker compose up -d nginx cert-renewer
   ```

3. Nginx reads `current/fullchain.pem` and `current/privkey.pem`, so it can
   never observe a half-installed pair.

This recipe intentionally does not mount a Docker socket. Reload Nginx through
your normal orchestration after a successful renewal, or deploy Nginx with a
reload mechanism that has only the permission it needs.

