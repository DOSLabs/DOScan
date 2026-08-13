#!/bin/sh
set -eu

verification_directory="${1:-}"
if [ -z "${verification_directory}" ]; then
  echo "usage: verify-testnet-aa-sources.sh <verification-artifact-directory>" >&2
  exit 2
fi

manifest_path="${verification_directory}/manifest.json"
api_base_url="${DOSCAN_AA_API_BASE_URL:-http://127.0.0.1:13080}"
api_base_url="${api_base_url%/}"
api_host_header="${DOSCAN_AA_API_HOST_HEADER:-test.doscan.io}"
curl_bin="${DOSCAN_AA_CURL_BIN:-curl}"
jq_bin="${DOSCAN_AA_JQ_BIN:-jq}"
poll_attempts="${DOSCAN_AA_POLL_ATTEMPTS:-60}"
poll_interval_seconds="${DOSCAN_AA_POLL_INTERVAL_SECONDS:-5}"
max_seconds="${DOSCAN_AA_MAX_SECONDS:-300}"
connect_timeout_seconds="${DOSCAN_AA_CONNECT_TIMEOUT_SECONDS:-10}"
request_timeout_seconds="${DOSCAN_AA_REQUEST_TIMEOUT_SECONDS:-20}"
curl_retry_delay_seconds="${DOSCAN_AA_CURL_RETRY_DELAY_SECONDS:-1}"
curl_retry_max_seconds="${DOSCAN_AA_CURL_RETRY_MAX_SECONDS:-30}"

status_file="$(mktemp)"
submit_file="$(mktemp)"
trap 'rm -f "${status_file}" "${submit_file}"' EXIT HUP INT TERM

case "${poll_attempts}:${poll_interval_seconds}:${max_seconds}" in
  *[!0-9:]* | :* | *: | *::* )
    echo "Account Abstraction polling settings must be non-negative integers" >&2
    exit 2
    ;;
esac
if [ "${poll_attempts}" -lt 1 ] || [ "${max_seconds}" -lt 1 ]; then
  echo "Account Abstraction polling attempts and deadline must be positive" >&2
  exit 2
fi

if ! "${jq_bin}" -e '
  .version == 1 and
  .compilerVersion == "v0.8.28+commit.7893614a" and
  .evmVersion == "cancun" and
  .optimizer.enabled == true and
  .optimizer.runs == 1000000 and
  .viaIR == true and
  (.contracts | type == "array" and length == 2) and
  .contracts[0] == {
    "key": "entry-point",
    "address": "0x4337084D9E255Ff0702461CF8895CE9E3b5Ff108",
    "contractName": "EntryPoint",
    "sourcePath": "contracts/core/EntryPoint.sol",
    "standardInputFile": "entry-point.standard-input.json",
    "licenseType": "gnu_gpl_v3",
    "spdxLicense": "GPL-3.0",
    "constructorArgs": ""
  } and
  .contracts[1] == {
    "key": "simple-account-factory",
    "address": "0xe908bff16d2a2ee257873708dbec8029ee9cd2cc",
    "contractName": "SimpleAccountFactory",
    "sourcePath": "contracts/accounts/SimpleAccountFactory.sol",
    "standardInputFile": "simple-account-factory.standard-input.json",
    "licenseType": "mit",
    "spdxLicense": "MIT",
    "constructorArgs": "0000000000000000000000004337084d9e255ff0702461cf8895ce9e3b5ff108"
  }
' "${manifest_path}" >/dev/null; then
  echo "Account Abstraction verification manifest is invalid" >&2
  exit 2
fi

get_contract_status() {
  contract_address="$1"
  : >"${status_file}"
  "${curl_bin}" \
    --connect-timeout "${connect_timeout_seconds}" \
    --max-time "${request_timeout_seconds}" \
    --fail --silent --show-error \
    --header "Host: ${api_host_header}" \
    --header "Cache-Control: no-cache" \
    --output "${status_file}" \
    "${api_base_url}/api/v2/smart-contracts/${contract_address}"
}

classify_contract_status() {
  expected_name="$1"
  expected_source_path="$2"
  expected_license_type="$3"
  expected_constructor_args="$4"

  if "${jq_bin}" -e '
    .is_verified == false or
    (
      (has("is_verified") | not) and
      (.creation_bytecode | type == "string" and startswith("0x") and length > 2) and
      (.deployed_bytecode | type == "string" and startswith("0x") and length > 2)
    )
  ' "${status_file}" >/dev/null; then
    return 1
  fi

  if ! "${jq_bin}" -e 'type == "object" and has("is_verified") and (.is_verified | type == "boolean")' \
    "${status_file}" >/dev/null; then
    echo "Blockscout returned malformed verification metadata for ${expected_name}" >&2
    return 2
  fi

  if "${jq_bin}" -e \
    --arg expected_name "${expected_name}" \
    --arg expected_source_path "${expected_source_path}" \
    --arg expected_license_type "${expected_license_type}" \
    --arg expected_constructor_args "${expected_constructor_args}" '
      def normalize_hex: tostring | ascii_downcase | sub("^0x"; "");
      .is_verified == true and
      .is_fully_verified == true and
      .is_partially_verified == false and
      .verified_twin_address_hash == null and
      .name == $expected_name and
      .compiler_version == "v0.8.28+commit.7893614a" and
      .optimization_enabled == true and
      .optimization_runs == 1000000 and
      .evm_version == "cancun" and
      .file_path == $expected_source_path and
      .license_type == $expected_license_type and
      .compiler_settings.viaIR == true and
      ((.constructor_args // "") | normalize_hex) == ($expected_constructor_args | normalize_hex)
    ' "${status_file}" >/dev/null; then
    return 0
  fi

  echo "Blockscout verification metadata mismatch for ${expected_name}" >&2
  "${jq_bin}" -c '{
    is_verified,
    is_fully_verified,
    is_partially_verified,
    verified_twin_address_hash,
    name,
    compiler_version,
    optimization_enabled,
    optimization_runs,
    evm_version,
    file_path,
    license_type,
    viaIR: .compiler_settings.viaIR,
    constructor_args
  }' "${status_file}" >&2 || true
  return 2
}

submit_contract() {
  contract_address="$1"
  contract_name="$2"
  source_path="$3"
  license_type="$4"
  constructor_args="$5"
  standard_input_path="$6"

  : >"${submit_file}"
  if ! "${curl_bin}" \
    --connect-timeout "${connect_timeout_seconds}" \
    --max-time "${request_timeout_seconds}" \
    --retry 2 \
    --retry-all-errors \
    --retry-delay "${curl_retry_delay_seconds}" \
    --retry-max-time "${curl_retry_max_seconds}" \
    --fail --silent --show-error \
    --header "Host: ${api_host_header}" \
    --output "${submit_file}" \
    --form "compiler_version=v0.8.28+commit.7893614a" \
    --form "contract_name=${source_path}:${contract_name}" \
    --form "autodetect_constructor_args=false" \
    --form "constructor_args=${constructor_args}" \
    --form "license_type=${license_type}" \
    --form "files[0]=@${standard_input_path};type=application/json" \
    "${api_base_url}/api/v2/smart-contracts/${contract_address}/verification/via/standard-input"; then
    echo "Blockscout verification submission failed for ${contract_name}" >&2
    return 1
  fi

  if ! "${jq_bin}" -e '.message == "Smart-contract verification started"' \
    "${submit_file}" >/dev/null; then
    echo "Blockscout verification submission returned an unexpected response for ${contract_name}" >&2
    cat "${submit_file}" >&2
    return 1
  fi
}

verify_contract() {
  contract_address="$1"
  contract_name="$2"
  source_path="$3"
  license_type="$4"
  constructor_args="$5"
  standard_input_path="$6"
  submitted=0
  attempt=1
  deadline="$(( $(date +%s) + max_seconds ))"

  while [ "${attempt}" -le "${poll_attempts}" ]; do
    status_code=3
    if get_contract_status "${contract_address}"; then
      if classify_contract_status \
        "${contract_name}" \
        "${source_path}" \
        "${license_type}" \
        "${constructor_args}"; then
        echo "Blockscout exact source verification confirmed for ${contract_name}"
        return 0
      else
        status_code="$?"
      fi

      if [ "${status_code}" -eq 2 ]; then
        return 1
      fi

      if [ "${status_code}" -eq 1 ] && [ "${submitted}" -eq 0 ]; then
        submit_contract \
          "${contract_address}" \
          "${contract_name}" \
          "${source_path}" \
          "${license_type}" \
          "${constructor_args}" \
          "${standard_input_path}"
        submitted=1
      fi
    fi

    now="$(date +%s)"
    if [ "${attempt}" -ge "${poll_attempts}" ] || [ "${now}" -ge "${deadline}" ]; then
      echo "Blockscout source verification timed out for ${contract_name}" >&2
      return 1
    fi

    sleep "${poll_interval_seconds}"
    attempt="$((attempt + 1))"
  done
}

contract_count="$("${jq_bin}" -r '.contracts | length' "${manifest_path}")"
contract_index=0
while [ "${contract_index}" -lt "${contract_count}" ]; do
  contract_address="$("${jq_bin}" -er ".contracts[${contract_index}].address" "${manifest_path}")"
  contract_name="$("${jq_bin}" -er ".contracts[${contract_index}].contractName" "${manifest_path}")"
  source_path="$("${jq_bin}" -er ".contracts[${contract_index}].sourcePath" "${manifest_path}")"
  license_type="$("${jq_bin}" -er ".contracts[${contract_index}].licenseType" "${manifest_path}")"
  constructor_args="$("${jq_bin}" -er ".contracts[${contract_index}].constructorArgs" "${manifest_path}")"
  standard_input_file="$("${jq_bin}" -er ".contracts[${contract_index}].standardInputFile" "${manifest_path}")"

  if ! printf '%s' "${contract_address}" | grep -Eq '^0x[0-9a-fA-F]{40}$'; then
    echo "Invalid Account Abstraction contract address: ${contract_address}" >&2
    exit 2
  fi
  case "${standard_input_file}" in
    *[!a-z0-9.-]* | .* | *..* | */*)
      echo "Invalid Account Abstraction standard input filename: ${standard_input_file}" >&2
      exit 2
      ;;
  esac
  standard_input_path="${verification_directory}/${standard_input_file}"
  if [ ! -s "${standard_input_path}" ]; then
    echo "Missing Account Abstraction standard input: ${standard_input_path}" >&2
    exit 2
  fi

  verify_contract \
    "${contract_address}" \
    "${contract_name}" \
    "${source_path}" \
    "${license_type}" \
    "${constructor_args}" \
    "${standard_input_path}"
  contract_index="$((contract_index + 1))"
done
