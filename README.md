# Cert Renewer v2

A small always-on service that issues and renews multiple independent Let's
Encrypt certificates through Cloudflare DNS-01. It supports wildcard domains,
atomic certificate installation, Docker Compose, and systemd.

## English

### Configuration

Copy `examples/config.toml`. One daemon can contain any number of certificate
lineages:

```toml
email = "ops@example.com"
state_dir = "/var/lib/cert-renewer"
interval_seconds = 43200
renewal_threshold_seconds = 2592000

[[certificates]]
name = "example.com"
domains = ["example.com", "*.example.com"]
token_file = "/run/secrets/cloudflare-example"
destination = "/certificates/example.com"
propagation_seconds = 90

[certificates.reload]
kind = "none"

[[certificates]]
name = "example.kz"
domains = ["example.kz", "www.example.kz"]
token_file = "/run/secrets/cloudflare-kz"
destination = "/certificates/example.kz"

[certificates.reload]
kind = "command"
argv = ["systemctl", "reload", "nginx"]
```

Each token file contains only a Cloudflare API token with `Zone:DNS:Edit` and
`Zone:Zone:Read` for the required zone. Set mode `0600`. Tokens are never placed
in TOML, command arguments, status files, or logs.

Commands:

```bash
python3 -m cert_renewer check --config /etc/cert-renewer/config.toml
python3 -m cert_renewer once --config /etc/cert-renewer/config.toml
python3 -m cert_renewer run --config /etc/cert-renewer/config.toml
python3 -m cert_renewer health --config /etc/cert-renewer/config.toml
```

`check` is read-only. `once` performs one cycle. `run` stays alive and retries.
`health` validates the freshness and outcome of `status.json`.

### Docker Compose

```bash
cp docker/config.example.toml docker/config.toml
mkdir -p docker/secrets
install -m 0600 /path/to/token docker/secrets/cloudflare-example
docker compose -f docker/compose.yaml up -d --build
docker compose -f docker/compose.yaml logs -f cert-renewer
```

The default Docker Compose file does not mount the Docker socket. Use shared
certificate volumes and let the reverse proxy reload externally. If the
`docker-signal` reload action is required, explicitly add
`-f docker/compose.socket.yaml`. Docker socket access is effectively host-root
access; use the override only on a trusted single-purpose host.

### systemd

```bash
sudo ./systemd/install.sh
sudoedit /etc/cert-renewer/config.toml
sudo PYTHONPATH=/opt/cert-renewer/src python3 -m cert_renewer check --config /etc/cert-renewer/config.toml
sudo ./systemd/install.sh --enable
systemctl status cert-renewer
```

The installer preserves an existing configuration.

### Staging ACME test

Before production issuance, set:

```toml
acme_server = "https://acme-staging-v02.api.letsencrypt.org/directory"
```

Run `once`, inspect the resulting lineage, then remove the override and run
`once` again for a trusted production certificate. See `RUNBOOK_TLS.md` for
recovery and token rotation.

### Migration from v1

Stop the old container but preserve `/etc/letsencrypt`. Convert variables as
follows: `CERTBOT_CERT_NAME` becomes `certificates.name`;
`CERTBOT_PRIMARY_DOMAIN` and `CERTBOT_EXTRA_DOMAINS` become the
`certificates.domains` array; `CLOUDFLARE_API_TOKEN_FILE` becomes
`certificates.token_file`; `CERTBOT_RENEW_INTERVAL_SECONDS` becomes root
`interval_seconds`; `CERTBOT_PROPAGATION_SECONDS` becomes
`certificates.propagation_seconds`; `NGINX_CERT_TARGET_DIR` becomes
`certificates.destination`; `NGINX_CONTAINER_NAME` and `DOCKER_SOCKET_PATH`
become fields of `certificates.reload`. Add one `[[certificates]]` table for
every former container, run `check`, test with staging ACME, then run `once`.

## Русский

Cert Renewer — постоянно работающий сервис для нескольких независимых
сертификатов Let's Encrypt через Cloudflare DNS-01. Обычные и wildcard-домены
задаются массивом `[[certificates]]` в TOML. Ошибка одного сертификата не
останавливает остальные.

Для Docker скопируйте `docker/config.example.toml` в `docker/config.toml`,
положите токены с правами `0600` в `docker/secrets` и запустите:

```bash
docker compose -f docker/compose.yaml up -d --build
```

Для systemd выполните `sudo ./systemd/install.sh`, настройте
`/etc/cert-renewer/config.toml`, проверьте командой `check`, затем включите
`sudo ./systemd/install.sh --enable`.

Режимы: `check` проверяет окружение без выпуска; `once` выполняет один цикл;
`run` работает постоянно; `health` проверяет свежесть `status.json`.

Docker socket по умолчанию не подключён. Опциональный override нужен только для
`docker-signal` и даёт контейнеру высокий уровень доступа к Docker daemon.
Перед production используйте staging ACME URL из раздела выше. Восстановление,
ротация токена и диагностика описаны в `RUNBOOK_TLS.md`.
