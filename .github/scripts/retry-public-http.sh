#!/bin/sh

set -eu

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <url>" >&2
  exit 2
fi

exec curl \
  --fail \
  --silent \
  --show-error \
  --retry "${PUBLIC_HTTP_RETRY_COUNT:-6}" \
  --retry-delay "${PUBLIC_HTTP_RETRY_DELAY_SECONDS:-5}" \
  --retry-all-errors \
  "$1"
