#!/usr/bin/env bash
# Generează certificat self-signed pentru test HTTPS local / staging.
# Producție: folosește Let's Encrypt (certbot) și montează același fullchain.pem / privkey.pem.

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SSL="$ROOT/docker/nginx/ssl"
mkdir -p "$SSL"

if [[ -f "$SSL/fullchain.pem" && -f "$SSL/privkey.pem" ]]; then
  echo "Există deja certificate în $SSL — nu suprascriu."
  exit 0
fi

openssl req -x509 -nodes -newkey rsa:2048 -days 825 \
  -keyout "$SSL/privkey.pem" \
  -out "$SSL/fullchain.pem" \
  -subj "/CN=localhost/O=Mulberry/C=RO"

echo "Creat: $SSL/fullchain.pem și privkey.pem (self-signed)."
