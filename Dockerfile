FROM certbot/dns-cloudflare:latest

RUN apk add --no-cache bash curl

COPY renew-cert.sh /usr/local/bin/renew-cert.sh
COPY install-cert.sh /usr/local/bin/install-cert.sh

RUN chmod +x /usr/local/bin/renew-cert.sh /usr/local/bin/install-cert.sh

ENTRYPOINT ["/usr/local/bin/renew-cert.sh"]
