#!/usr/bin/env bash
set -euo pipefail

retry_delay_seconds="${DOCKER_REMOVE_RETRY_DELAY_SECONDS:-2}"

if [ "$#" -eq 0 ]; then
  exit 0
fi

for attempt in 1 2 3; do
  if ! docker info >/dev/null 2>&1; then
    echo "Docker daemon is unavailable during container removal" >&2
    exit 1
  fi

  remaining=()
  for container_id in "$@"; do
    if docker inspect "${container_id}" >/dev/null 2>&1; then
      remaining+=("${container_id}")
    fi
  done

  if [ "${#remaining[@]}" -eq 0 ]; then
    exit 0
  fi

  docker rm -f "${remaining[@]}" >/dev/null 2>&1 || true
  if [ "${attempt}" -lt 3 ]; then
    sleep "${retry_delay_seconds}"
  fi
done

if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon is unavailable during container removal" >&2
  exit 1
fi

for container_id in "$@"; do
  if docker inspect "${container_id}" >/dev/null 2>&1; then
    echo "Docker container removal did not finish: ${container_id}" >&2
    exit 1
  fi
done
