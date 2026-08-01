ARG PEBBLE_IMAGE=ghcr.io/letsencrypt/pebble:2.10.1@sha256:ddf230642b1a584f519f32e347de1b05a6e4c1f6c35c1863b33effeab5f78199
FROM ${PEBBLE_IMAGE} AS pebble

FROM cert-renewer:e2e-base
USER 0
COPY --from=pebble /test/certs/pebble.minica.pem /test/pebble.minica.pem
COPY --chown=65532:65532 tests/e2e/config.toml /test/config.toml
COPY --chown=65532:65532 tests/e2e/certbot-wrapper.sh /test/certbot-wrapper.sh
COPY --chown=65532:65532 tests/e2e/run.sh /test/run.sh
RUN printf '%s\n' test-token > /test/cloudflare-token \
    && chown 65532:65532 /test/cloudflare-token \
    && chmod 0400 /test/cloudflare-token \
    && chmod 0555 /test/certbot-wrapper.sh /test/run.sh
USER 65532:65532
ENTRYPOINT ["/test/run.sh"]
