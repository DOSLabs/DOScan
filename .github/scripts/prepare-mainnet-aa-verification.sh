#!/bin/sh
set -eu

if [ "$#" -ne 7 ]; then
  echo "usage: prepare-mainnet-aa-verification.sh <aa-repository> <aa-ref> <kernel-repository> <kernel-ref> <solady-ref> <output-directory> <rpc-url>" >&2
  exit 2
fi

aa_repository="$1"
aa_ref="$2"
kernel_repository="$3"
kernel_ref="$4"
solady_ref="$5"
output_directory="$6"
rpc_url="$7"
workspace="${GITHUB_WORKSPACE:-$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)}"
checkout_root="$(mktemp -d "${RUNNER_TEMP:-/tmp}/doscan-mainnet-aa.XXXXXX")"
aa_checkout="${checkout_root}/account-abstraction"
kernel_checkout="${checkout_root}/kernel"
cleanup() {
  rm -rf "${checkout_root}"
}
trap cleanup EXIT HUP INT TERM

require_sha() {
  value="$1"
  label="$2"
  if ! printf '%s' "${value}" | grep -Eq '^[0-9a-f]{40}$'; then
    echo "${label} must be a full lowercase Git SHA" >&2
    exit 2
  fi
}
require_sha "${aa_ref}" "Account Abstraction ref"
require_sha "${kernel_ref}" "Kernel ref"
require_sha "${solady_ref}" "Solady ref"

checkout_exact() {
  repository="$1"
  ref="$2"
  destination="$3"
  git init -q "${destination}"
  git -C "${destination}" remote add origin "${repository}"
  git -C "${destination}" fetch --depth 1 origin "${ref}"
  git -C "${destination}" checkout --detach -q FETCH_HEAD
  [ "$(git -C "${destination}" rev-parse HEAD)" = "${ref}" ]
}

if [ -e "${output_directory}" ] && [ -n "$(find "${output_directory}" -mindepth 1 -maxdepth 1 -print -quit)" ]; then
  echo "Mainnet Account Abstraction output directory must be empty" >&2
  exit 2
fi
mkdir -p "${output_directory}"

checkout_exact "${aa_repository}" "${aa_ref}" "${aa_checkout}"
checkout_exact "${kernel_repository}" "${kernel_ref}" "${kernel_checkout}"
git -C "${kernel_checkout}" submodule update --init --depth 1 lib/solady
[ "$(git -C "${kernel_checkout}/lib/solady" rev-parse HEAD)" = "${solady_ref}" ]

npm install --global yarn@1.22.22
yarn --cwd "${aa_checkout}" install --frozen-lockfile --non-interactive
yarn --cwd "${aa_checkout}" compile
npm ci --prefix "${workspace}/.github/scripts/mainnet-aa-solc" --ignore-scripts

node "${workspace}/.github/scripts/extract-mainnet-aa-verification-inputs.mjs" \
  "${aa_checkout}" "${kernel_checkout}" "${output_directory}"

for compiler_package in solc-0.8.23 solc-0.8.24 solc-0.8.25 solc-0.8.28; do
  test -s "${workspace}/.github/scripts/mainnet-aa-solc/node_modules/${compiler_package}/solc.js"
done

contract_count="$(jq -er '.contracts | length' "${output_directory}/manifest.json")"
[ "${contract_count}" -eq 5 ]
contract_index=0
while [ "${contract_index}" -lt "${contract_count}" ]; do
  compiler_package="$(jq -er ".contracts[${contract_index}].compilerPackage" "${output_directory}/manifest.json")"
  standard_input_file="$(jq -er ".contracts[${contract_index}].standardInputFile" "${output_directory}/manifest.json")"
  compiler_output_file="$(jq -er ".contracts[${contract_index}].compilerOutputFile" "${output_directory}/manifest.json")"
  case "${compiler_package}" in
    solc-0.8.23 | solc-0.8.24 | solc-0.8.25 | solc-0.8.28) ;;
    *)
      echo "Unexpected Mainnet compiler package: ${compiler_package}" >&2
      exit 2
      ;;
  esac
  compiler_js="${workspace}/.github/scripts/mainnet-aa-solc/node_modules/${compiler_package}/solc.js"
  node "${compiler_js}" --standard-json \
    <"${output_directory}/${standard_input_file}" \
    >"${output_directory}/${compiler_output_file}"
  test -s "${output_directory}/${standard_input_file}"
  test -s "${output_directory}/${compiler_output_file}"
  contract_index="$((contract_index + 1))"
done

test -s "${output_directory}/entry-point.compiler-output.json"
test -s "${output_directory}/kernel.compiler-output.json"
test -s "${output_directory}/kernel-factory.compiler-output.json"
test -s "${output_directory}/ecdsa-validator.compiler-output.json"
test -s "${output_directory}/factory-staker.compiler-output.json"
test -s "${output_directory}/manifest.json"
node "${workspace}/.github/scripts/verify-mainnet-aa-bytecode.mjs" \
  "${output_directory}" "${rpc_url}"
