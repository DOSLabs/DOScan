#!/usr/bin/env bash

testnet_rpc_request() {
  local rpc_body="$1"
  local include_headers="${2:-0}"
  local curl_bin="${TESTNET_RPC_CURL_BIN:-curl}"
  local retry_delay="${TESTNET_RPC_RETRY_DELAY_SECONDS:-5}"
  local attempt response

  for attempt in 1 2 3; do
    if [ "${include_headers}" -eq 1 ]; then
      if response="$(
        "${curl_bin}" --fail --silent --show-error --http1.1 \
          --connect-timeout 10 --max-time 30 \
          -D - -H "Content-Type: application/json" --data "${rpc_body}" \
          https://test.doschain.com/
      )"; then
        printf '%s' "${response}"
        return 0
      fi
    elif response="$(
      "${curl_bin}" --fail --silent --show-error --http1.1 \
        --connect-timeout 10 --max-time 30 \
        -H "Content-Type: application/json" --data "${rpc_body}" \
        https://test.doschain.com/
    )"; then
      printf '%s' "${response}"
      return 0
    fi

    if [ "${attempt}" -eq 3 ]; then
      return 1
    fi
    sleep "${retry_delay}"
  done
}
