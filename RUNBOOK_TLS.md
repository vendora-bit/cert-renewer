# TLS Renewal Runbook

## Inspection

```bash
python3 -m cert_renewer check --config /etc/cert-renewer/config.toml
python3 -m cert_renewer once --config /etc/cert-renewer/config.toml
jq . /var/lib/cert-renewer/status.json
openssl x509 -in /etc/nginx/certs/example/fullchain.pem -noout -dates -subject
```

For Docker use `docker compose -f docker/compose.yaml logs cert-renewer` and
`docker inspect --format '{{json .State.Health}}' cert-renewer-cert-renewer-1`.

## Recovery

If renewal fails, read the affected entry in `status.json`, verify system time,
Cloudflare token permissions, zone scope, DNS propagation, and Certbot logs.
Run `check`, then `once`. A failure in one lineage does not block others. Never
delete `/etc/letsencrypt`; restore it from backup or let Certbot reuse lineages.

If Nginx still serves an old certificate, compare the installed file, verify the
configured destination, inspect `state/deployments/<name>.json` for
`reload_pending`, run `nginx -t`, and execute the configured reload command.
The daemon retries a pending reload automatically. Point strict consumers at
`destination/current/fullchain.pem` and `destination/current/privkey.pem`; the
top-level compatibility links resolve to that same atomic revision.

## Token rotation

Create a new least-privilege Cloudflare token, write it to a temporary mode-0600
file, atomically replace the configured token file, run `check`, then test with
staging ACME. Revoke the old token only after a successful cycle. Token contents
must never be pasted into config or logs.

## Проверка

Проверьте `status.json`, журнал сервиса, срок сертификата, системное время,
доступность Cloudflare API и права файла токена. Команда `check` ничего не
выпускает; `once` выполняет безопасный одиночный цикл.

## Восстановление

Не удаляйте `/etc/letsencrypt`. Исправьте причину ошибки конкретного lineage и
повторите `once`; остальные сертификаты продолжают обслуживаться. Если Nginx
показывает старый сертификат, сравните target-файлы, выполните `nginx -t` и reload.
Также проверьте `deployments/<name>.json`: состояние `reload_pending` будет
автоматически повторено. Для строгой атомарности используйте файлы через
`destination/current/`.

## Ротация токена

Создайте новый токен Cloudflare с минимальными правами, сохраните с mode `0600`,
атомарно замените старый файл, выполните `check` и тест через staging ACME. После
успешного цикла отзовите прежний токен.
