#!/usr/bin/env bash
set -euo pipefail

retry_delay_seconds="${DOCKER_REMOVE_RETRY_DELAY_SECONDS:-2}"

if [ "$#" -eq 0 ]; then
  exit 0
fi

inspect_container_state() {
  local container_id="$1"
  local inspect_error

  if inspect_error="$(docker inspect "${container_id}" 2>&1)"; then
    return 0
  fi
  if ! docker info >/dev/null 2>&1; then
    echo "Docker daemon is unavailable during container removal" >&2
    return 2
  fi
  if inspect_error="$(docker inspect "${container_id}" 2>&1)"; then
    return 0
  fi
  if ! docker info >/dev/null 2>&1; then
    echo "Docker daemon is unavailable during container removal" >&2
    return 2
  fi

  case "${inspect_error}" in
    *"No such object:"* | *"No such container:"*) return 1 ;;
    *"removal of container"*"already in progress"*) return 3 ;;
    *)
      echo "Docker inspect could not determine container state: ${container_id}" >&2
      return 2
      ;;
  esac
}

for attempt in 1 2 3; do
  if ! docker info >/dev/null 2>&1; then
    echo "Docker daemon is unavailable during container removal" >&2
    exit 1
  fi

  remaining=()
  removal_pending=0
  for container_id in "$@"; do
    if inspect_container_state "${container_id}"; then
      remaining+=("${container_id}")
    else
      inspect_status=$?
      case "${inspect_status}" in
        1) ;;
        3) removal_pending=1 ;;
        *) exit 1 ;;
      esac
    fi
  done

  if [ "${#remaining[@]}" -eq 0 ] && [ "${removal_pending}" -eq 0 ]; then
    exit 0
  fi

  if [ "${#remaining[@]}" -gt 0 ]; then
    docker rm -f "${remaining[@]}" >/dev/null 2>&1 || true
  fi
  if [ "${attempt}" -lt 3 ]; then
    sleep "${retry_delay_seconds}"
  fi
done

if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon is unavailable during container removal" >&2
  exit 1
fi

for container_id in "$@"; do
  if inspect_container_state "${container_id}"; then
    echo "Docker container removal did not finish: ${container_id}" >&2
    exit 1
  else
    inspect_status=$?
    case "${inspect_status}" in
      1) ;;
      3)
        echo "Docker container removal did not finish: ${container_id}" >&2
        exit 1
        ;;
      *) exit 1 ;;
    esac
  fi
done
