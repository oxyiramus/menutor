#!/bin/sh
set -eu
umask 077

cd "$(dirname "$0")"
PROXY_TEST_CERT_DIR=$(mktemp -d "${PWD}/.certs.XXXXXX")
export PROXY_TEST_CERT_DIR
project="menutor-proxy-test-$$"

compose() {
    docker compose -p "$project" -f compose.yml "$@"
}

cleanup() {
    status=$?
    if [ "$status" -ne 0 ]; then
        compose logs backend frontend edge || true
    fi
    compose down --remove-orphans || true
    rm -f "$PROXY_TEST_CERT_DIR/"*.pem "$PROXY_TEST_CERT_DIR/"*.conf
    rmdir "$PROXY_TEST_CERT_DIR"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj /CN=127.0.0.1 \
    -addext subjectAltName=IP:127.0.0.1 -keyout "$PROXY_TEST_CERT_DIR/key.pem" \
    -out "$PROXY_TEST_CERT_DIR/cert.pem" 2>/dev/null
proxy_key=$(openssl rand -hex 32)
printf 'proxy_set_header X-Menutor-Proxy-Key "%s";\n' "$proxy_key" > "$PROXY_TEST_CERT_DIR/proxy-key.conf"
printf '"172.29.103.1:%s" 1;\n' "$proxy_key" > "$PROXY_TEST_CERT_DIR/proxy-trust.conf"
sed -e 's/listen 80;/listen 127.0.0.1:18081;/' \
    -e 's/listen 443 ssl;/listen 127.0.0.1:18443 ssl;/' \
    -e 's/127.0.0.1:8080/127.0.0.1:18080/' \
    -e 's|/etc/letsencrypt/live/menutor.example.com/fullchain.pem|/certs/cert.pem|' \
    -e 's|/etc/letsencrypt/live/menutor.example.com/privkey.pem|/certs/key.pem|' \
    ../../.docker/prod/host-nginx.conf.example > "$PROXY_TEST_CERT_DIR/edge.conf"
compose up --build -d edge
compose run --rm --no-deps host-client
compose run --rm --no-deps client
python3 check_rate_limit.py "$project"
