# Runbook: TLS Renewal

## Проверка

```bash
docker compose logs -f cert-renewer
openssl x509 -in nginx/certs/tls.crt -noout -dates -subject
```

## Симптомы

- сертификат не продлевается
- `nginx` отдает старый cert

## Что делать

1. Проверить Cloudflare API token.
2. Проверить DNS challenge propagation.
3. Проверить `cert-renewer` health.
4. При необходимости вручную перезапустить `cert-renewer`.
