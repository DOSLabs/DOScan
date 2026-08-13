#!/bin/sh
set -eu

verification_directory="${1:-}"
if [ -z "${verification_directory}" ]; then
  echo "usage: verify-mainnet-aa-sources.sh <verification-artifact-directory>" >&2
  exit 2
fi

manifest_path="${verification_directory}/manifest.json"
api_base_url="${DOSCAN_MAINNET_AA_API_BASE_URL:-http://127.0.0.1:13080}"
api_base_url="${api_base_url%/}"
api_host_header="${DOSCAN_MAINNET_AA_API_HOST_HEADER:-doscan.io}"
curl_bin="${DOSCAN_MAINNET_AA_CURL_BIN:-curl}"
jq_bin="${DOSCAN_MAINNET_AA_JQ_BIN:-jq}"
date_bin="${DOSCAN_MAINNET_AA_DATE_BIN:-date}"
poll_attempts="${DOSCAN_MAINNET_AA_POLL_ATTEMPTS:-60}"
poll_interval_seconds="${DOSCAN_MAINNET_AA_POLL_INTERVAL_SECONDS:-5}"
max_seconds="${DOSCAN_MAINNET_AA_MAX_SECONDS:-300}"
connect_timeout_seconds="${DOSCAN_MAINNET_AA_CONNECT_TIMEOUT_SECONDS:-10}"
request_timeout_seconds="${DOSCAN_MAINNET_AA_REQUEST_TIMEOUT_SECONDS:-20}"
curl_retry_delay_seconds="${DOSCAN_MAINNET_AA_CURL_RETRY_DELAY_SECONDS:-1}"
curl_retry_max_seconds="${DOSCAN_MAINNET_AA_CURL_RETRY_MAX_SECONDS:-30}"

status_file="$(mktemp)"
submit_file="$(mktemp)"
trap 'rm -f "${status_file}" "${submit_file}"' EXIT HUP INT TERM

case "${poll_attempts}:${poll_interval_seconds}:${max_seconds}:${connect_timeout_seconds}:${request_timeout_seconds}:${curl_retry_delay_seconds}:${curl_retry_max_seconds}" in
  *[!0-9:]* | :* | *: | *::* )
    echo "Mainnet Account Abstraction polling settings must be non-negative integers" >&2
    exit 2
    ;;
esac
if [ "${poll_attempts}" -lt 1 ] || [ "${max_seconds}" -lt 1 ] || \
   [ "${connect_timeout_seconds}" -lt 1 ] || [ "${request_timeout_seconds}" -lt 1 ] || \
   [ "${curl_retry_max_seconds}" -lt 1 ]; then
  echo "Mainnet Account Abstraction attempts, deadline, and request timeouts must be positive" >&2
  exit 2
fi

if ! "${jq_bin}" -e '
  .version == 2 and .chainId == 7979 and
  .contracts == [
    {
      "key":"entry-point","address":"0x0000000071727De22E5E9d8BAf0edAc6f37da032","contractName":"EntryPoint",
      "sourcePath":"contracts/core/EntryPoint.sol","standardInputFile":"entry-point.standard-input.json",
      "compilerOutputFile":"entry-point.compiler-output.json","compilerPackage":"solc-0.8.23",
      "compilerVersion":"v0.8.23+commit.f704f362","evmVersion":"paris","optimizer":{"enabled":true,"runs":1000000},
      "viaIR":true,"metadata":{"bytecodeHash":"ipfs"},"licenseType":"gnu_gpl_v3","spdxLicense":"GPL-3.0",
      "constructorArgs":"","expectedCodeSha256":"4dcad467095cd9af58006b270475ac7591c6946bca08552f6789727097b51eae","rpcChecks":[],"verificationMatch":"full"
    },
    {
      "key":"kernel","address":"0xd6CEDDe84be40893d153Be9d467CD6aD37875b28","contractName":"Kernel",
      "sourcePath":"src/Kernel.sol","standardInputFile":"kernel.standard-input.json","compilerOutputFile":"kernel.compiler-output.json",
      "compilerPackage":"solc-0.8.28","compilerVersion":"v0.8.28+commit.7893614a","evmVersion":"prague",
      "optimizer":{"enabled":true,"runs":200},"viaIR":true,"metadata":{"appendCBOR":false,"bytecodeHash":"none"},
      "licenseType":"mit","spdxLicense":"MIT","constructorArgs":"0000000000000000000000000000000071727de22e5e9d8baf0edac6f37da032",
      "expectedCodeSha256":"d13e7ff2bc90271659100c83f49ee6250555bbf26ed35c2315f243c6849a2127",
      "rpcChecks":[{"signature":"entrypoint()","expectedAddress":"0x0000000071727De22E5E9d8BAf0edAc6f37da032"}],"verificationMatch":"partial"
    },
    {
      "key":"kernel-factory","address":"0x2577507b78c2008Ff367261CB6285d44ba5eF2E9","contractName":"KernelFactory",
      "sourcePath":"dependencies/kernel-v3.3/src/factory/KernelFactory.sol","standardInputFile":"kernel-factory.standard-input.json",
      "compilerOutputFile":"kernel-factory.compiler-output.json","compilerPackage":"solc-0.8.28",
      "compilerVersion":"v0.8.28+commit.7893614a","evmVersion":"prague","optimizer":{"enabled":true,"runs":200},
      "viaIR":true,"metadata":{"appendCBOR":false,"bytecodeHash":"none"},"licenseType":"mit","spdxLicense":"MIT",
      "constructorArgs":"000000000000000000000000d6cedde84be40893d153be9d467cd6ad37875b28",
      "expectedCodeSha256":"56443d7d18bfd62d5d69b04fc8207e439bf904166335dd7159e0eeef1cba2367",
      "rpcChecks":[{"signature":"implementation()","expectedAddress":"0xd6CEDDe84be40893d153Be9d467CD6aD37875b28"}],"verificationMatch":"partial"
    },
    {
      "key":"ecdsa-validator","address":"0x845ADb2C711129d4f3966735eD98a9F09fC4cE57","contractName":"ECDSAValidator",
      "sourcePath":"src/validator/ECDSAValidator.sol","standardInputFile":"ecdsa-validator.standard-input.json",
      "compilerOutputFile":"ecdsa-validator.compiler-output.json","compilerPackage":"solc-0.8.25",
      "compilerVersion":"v0.8.25+commit.b61c2a91","evmVersion":"paris","optimizer":{"enabled":true,"runs":200},
      "viaIR":true,"metadata":{"appendCBOR":false,"bytecodeHash":"none"},"licenseType":"mit","spdxLicense":"MIT",
      "constructorArgs":"","expectedCodeSha256":"be711f07f49e57bf56c512b6f32f7c77d9ec1881c4051ed33a45cfad8c7a8b8e","rpcChecks":[],"verificationMatch":"partial"
    },
    {
      "key":"factory-staker","address":"0xd703aaE79538628d27099B8c4f621bE4CCd142d5","contractName":"FactoryStaker",
      "sourcePath":"src/factory/FactoryStaker.sol","standardInputFile":"factory-staker.standard-input.json",
      "compilerOutputFile":"factory-staker.compiler-output.json","compilerPackage":"solc-0.8.24",
      "compilerVersion":"v0.8.24+commit.e11b9ed9","evmVersion":"paris","optimizer":{"enabled":true,"runs":200},
      "viaIR":false,"metadata":{"appendCBOR":false,"bytecodeHash":"none"},"licenseType":"mit","spdxLicense":"MIT",
      "constructorArgs":"","expectedCodeSha256":"f91091bf1260892a4d0b834494489fea55be2f2f968ad6b1abc1410531f2a2a1","rpcChecks":[],"verificationMatch":"partial"
    }
  ]
' "${manifest_path}" >/dev/null; then
  echo "Mainnet Account Abstraction verification manifest is invalid" >&2
  exit 2
fi

contract_index=0
while [ "${contract_index}" -lt 5 ]; do
  standard_input_file="$("${jq_bin}" -er ".contracts[${contract_index}].standardInputFile" "${manifest_path}")"
  case "${standard_input_file}" in
    *[!a-z0-9.-]* | .* | *..* | */*)
      echo "Invalid Mainnet Account Abstraction input filename: ${standard_input_file}" >&2
      exit 2
      ;;
  esac
  if [ ! -s "${verification_directory}/${standard_input_file}" ]; then
    echo "Missing Mainnet Account Abstraction standard input: ${standard_input_file}" >&2
    exit 2
  fi
  contract_index="$((contract_index + 1))"
done

remaining_budget() {
  deadline="$1"
  now="$("${date_bin}" +%s)"
  remaining="$((deadline - now))"
  if [ "${remaining}" -lt 1 ]; then
    return 1
  fi
  printf '%s\n' "${remaining}"
}

clamp_timeout() {
  configured="$1"
  remaining="$2"
  if [ "${configured}" -lt "${remaining}" ]; then
    printf '%s\n' "${configured}"
  else
    printf '%s\n' "${remaining}"
  fi
}

get_contract_status() {
  contract_address="$1"
  deadline="$2"
  remaining="$(remaining_budget "${deadline}")" || return 1
  bounded_connect_timeout="$(clamp_timeout "${connect_timeout_seconds}" "${remaining}")"
  bounded_request_timeout="$(clamp_timeout "${request_timeout_seconds}" "${remaining}")"
  : >"${status_file}"
  "${curl_bin}" --connect-timeout "${bounded_connect_timeout}" --max-time "${bounded_request_timeout}" \
    --fail --silent --show-error --header "Host: ${api_host_header}" --header "Cache-Control: no-cache" \
    --output "${status_file}" "${api_base_url}/api/v2/smart-contracts/${contract_address}"
}

classify_contract_status() {
  contract_index="$1"
  expected_name="$("${jq_bin}" -er ".contracts[${contract_index}].contractName" "${manifest_path}")"

  if "${jq_bin}" -e '.is_verified == false or ((has("is_verified") | not) and (.creation_bytecode | type == "string") and (.deployed_bytecode | type == "string"))' "${status_file}" >/dev/null; then
    return 1
  fi
  if ! "${jq_bin}" -e 'type == "object" and has("is_verified") and (.is_verified | type == "boolean")' "${status_file}" >/dev/null; then
    echo "Blockscout returned malformed Mainnet verification metadata for ${expected_name}" >&2
    return 2
  fi

  if "${jq_bin}" -e --argjson target "$("${jq_bin}" -c ".contracts[${contract_index}]" "${manifest_path}")" '
    def normalize_hex: tostring | ascii_downcase | sub("^0x"; "");
    def normalize_compiler: tostring | if startswith("v") then . else "v" + . end;
    .is_verified == true and
    (if $target.verificationMatch == "full" then .is_fully_verified == true and .is_partially_verified == false
     else .is_fully_verified == false and .is_partially_verified == true end) and
    .verified_twin_address_hash == null and .name == $target.contractName and .file_path == $target.sourcePath and
    (.compiler_version | normalize_compiler) == ($target.compilerVersion | normalize_compiler) and
    .optimization_enabled == true and .optimization_runs == $target.optimizer.runs and
    .evm_version == $target.evmVersion and .license_type == $target.licenseType and
    ((.constructor_args // "") | normalize_hex) == ($target.constructorArgs | normalize_hex) and
    (if $target.viaIR then .compiler_settings.viaIR == true else (.compiler_settings.viaIR // false) == false end) and
    (if $target.key == "entry-point" then (.compiler_settings.metadata.bytecodeHash // "ipfs") == "ipfs"
     else .compiler_settings.metadata.appendCBOR == false and .compiler_settings.metadata.bytecodeHash == "none" end)
  ' "${status_file}" >/dev/null; then
    return 0
  fi

  echo "Blockscout Mainnet verification metadata mismatch for ${expected_name}" >&2
  return 2
}

submit_contract() {
  contract_index="$1"
  deadline="$2"
  contract_address="$("${jq_bin}" -er ".contracts[${contract_index}].address" "${manifest_path}")"
  contract_name="$("${jq_bin}" -er ".contracts[${contract_index}].contractName" "${manifest_path}")"
  source_path="$("${jq_bin}" -er ".contracts[${contract_index}].sourcePath" "${manifest_path}")"
  compiler_version="$("${jq_bin}" -er ".contracts[${contract_index}].compilerVersion" "${manifest_path}")"
  license_type="$("${jq_bin}" -er ".contracts[${contract_index}].licenseType" "${manifest_path}")"
  constructor_args="$("${jq_bin}" -er ".contracts[${contract_index}].constructorArgs" "${manifest_path}")"
  standard_input_file="$("${jq_bin}" -er ".contracts[${contract_index}].standardInputFile" "${manifest_path}")"
  remaining="$(remaining_budget "${deadline}")" || return 1
  bounded_connect_timeout="$(clamp_timeout "${connect_timeout_seconds}" "${remaining}")"
  bounded_request_timeout="$(clamp_timeout "${request_timeout_seconds}" "${remaining}")"
  bounded_retry_timeout="$(clamp_timeout "${curl_retry_max_seconds}" "${remaining}")"
  : >"${submit_file}"
  if ! "${curl_bin}" --connect-timeout "${bounded_connect_timeout}" --max-time "${bounded_request_timeout}" \
    --retry 2 --retry-all-errors --retry-delay "${curl_retry_delay_seconds}" --retry-max-time "${bounded_retry_timeout}" \
    --fail --silent --show-error --header "Host: ${api_host_header}" --output "${submit_file}" \
    --form "compiler_version=${compiler_version}" --form "contract_name=${source_path}:${contract_name}" \
    --form "autodetect_constructor_args=false" --form "constructor_args=${constructor_args}" \
    --form "license_type=${license_type}" --form "files[0]=@${verification_directory}/${standard_input_file};type=application/json" \
    "${api_base_url}/api/v2/smart-contracts/${contract_address}/verification/via/standard-input"; then
    echo "Blockscout Mainnet verification submission failed for ${contract_name}" >&2
    return 1
  fi
  if "${jq_bin}" -e '.message == "Smart-contract verification started" or .message == "Already verified"' "${submit_file}" >/dev/null; then
    return 0
  fi
  echo "Blockscout Mainnet verification submission returned an unexpected response for ${contract_name}" >&2
  cat "${submit_file}" >&2
  return 1
}

verify_contract() {
  contract_index="$1"
  deadline="$2"
  contract_address="$("${jq_bin}" -er ".contracts[${contract_index}].address" "${manifest_path}")"
  contract_name="$("${jq_bin}" -er ".contracts[${contract_index}].contractName" "${manifest_path}")"
  submitted=0
  attempt=1
  while [ "${attempt}" -le "${poll_attempts}" ]; do
    now="$("${date_bin}" +%s)"
    if [ "${now}" -ge "${deadline}" ]; then
      echo "Blockscout Mainnet source verification timed out for ${contract_name}" >&2
      return 1
    fi
    status_code=3
    if get_contract_status "${contract_address}" "${deadline}"; then
      if classify_contract_status "${contract_index}"; then
        echo "Blockscout exact Mainnet source verification confirmed for ${contract_name}"
        return 0
      else
        status_code="$?"
      fi
      if [ "${status_code}" -eq 2 ]; then
        return 1
      fi
      if [ "${status_code}" -eq 1 ] && [ "${submitted}" -eq 0 ]; then
        submit_contract "${contract_index}" "${deadline}"
        submitted=1
      fi
    fi
    now="$("${date_bin}" +%s)"
    if [ "${attempt}" -ge "${poll_attempts}" ] || [ "${now}" -ge "${deadline}" ]; then
      echo "Blockscout Mainnet source verification timed out for ${contract_name}" >&2
      return 1
    fi
    remaining="$((deadline - now))"
    bounded_poll_interval="$(clamp_timeout "${poll_interval_seconds}" "${remaining}")"
    sleep "${bounded_poll_interval}"
    attempt="$((attempt + 1))"
  done
}

verification_deadline="$(( $("${date_bin}" +%s) + max_seconds ))"
contract_index=0
while [ "${contract_index}" -lt 5 ]; do
  verify_contract "${contract_index}" "${verification_deadline}"
  contract_index="$((contract_index + 1))"
done
