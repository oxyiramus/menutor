#!/bin/sh
set -eu

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
    rm -f "$PROXY_TEST_CERT_DIR/cert.pem" "$PROXY_TEST_CERT_DIR/key.pem"
    rmdir "$PROXY_TEST_CERT_DIR"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj /CN=edge \
    -addext subjectAltName=DNS:edge -keyout "$PROXY_TEST_CERT_DIR/key.pem" \
    -out "$PROXY_TEST_CERT_DIR/cert.pem" 2>/dev/null
compose up --build -d edge
compose run --rm --no-deps client
