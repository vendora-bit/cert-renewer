FROM certbot/dns-cloudflare:v5.7.0@sha256:3bd60102cdef55294a44ffbff10bb54dd086803aa57d3f854933b756d305fbb8

ENV PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY src/ /app/src/
COPY docker/entrypoint.sh /usr/local/bin/cert-renewer-entrypoint
RUN chmod 0755 /usr/local/bin/cert-renewer-entrypoint

HEALTHCHECK --interval=60s --timeout=10s --start-period=60s --retries=3 \
  CMD ["python", "-m", "cert_renewer", "health", "--config", "/config/config.toml"]

ENTRYPOINT ["/usr/local/bin/cert-renewer-entrypoint"]
CMD ["run", "--config", "/config/config.toml"]
