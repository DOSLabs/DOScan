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
  --connect-timeout "${PUBLIC_HTTP_CONNECT_TIMEOUT_SECONDS:-10}" \
  --max-time "${PUBLIC_HTTP_MAX_TIME_SECONDS:-20}" \
  --retry "${PUBLIC_HTTP_RETRY_COUNT:-6}" \
  --retry-delay "${PUBLIC_HTTP_RETRY_DELAY_SECONDS:-5}" \
  --retry-max-time "${PUBLIC_HTTP_RETRY_MAX_TIME_SECONDS:-60}" \
  --retry-all-errors \
  "$1"
