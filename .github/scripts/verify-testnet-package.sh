#!/usr/bin/env bash
set -euo pipefail

archive="${1:?Usage: verify-testnet-package.sh <archive>}"

test -s "${archive}"
tar -tzf "${archive}" | grep -Fx "docker-compose/bens/config.json" >/dev/null
