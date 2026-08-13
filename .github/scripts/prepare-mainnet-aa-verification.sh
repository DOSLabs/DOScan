#!/bin/sh
set -eu

if [ "$#" -ne 9 ]; then
  echo "usage: prepare-mainnet-aa-verification.sh <aa-repository> <aa-ref> <kernel-repository> <kernel-ref> <solady-ref> <ecdsa-kernel-ref> <ecdsa-solady-ref> <output-directory> <rpc-url>" >&2
  exit 2
fi

aa_repository="$1"
aa_ref="$2"
kernel_repository="$3"
kernel_ref="$4"
solady_ref="$5"
ecdsa_kernel_ref="$6"
ecdsa_solady_ref="$7"
excessively_safe_call_ref="81cd99ce3e69117d665d7601c330ea03b97acce0"
output_directory="$8"
rpc_url="$9"
workspace="${GITHUB_WORKSPACE:-$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)}"
checkout_root="$(mktemp -d "${RUNNER_TEMP:-/tmp}/doscan-mainnet-aa.XXXXXX")"
aa_checkout="${checkout_root}/account-abstraction"
kernel_checkout="${checkout_root}/kernel"
ecdsa_kernel_checkout="${checkout_root}/kernel-ecdsa"
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
require_sha "${ecdsa_kernel_ref}" "ECDSA Kernel ref"
require_sha "${ecdsa_solady_ref}" "ECDSA Solady ref"

checkout_exact() {
  repository="$1"
  ref="$2"
  destination="$3"
  git init -q "${destination}"
  git -C "${destination}" config core.autocrlf false
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
checkout_exact "${kernel_repository}" "${ecdsa_kernel_ref}" "${ecdsa_kernel_checkout}"
git -C "${kernel_checkout}" submodule update --init --depth 1 \
  lib/solady lib/ExcessivelySafeCall
[ "$(git -C "${kernel_checkout}/lib/solady" rev-parse HEAD)" = "${solady_ref}" ]
[ "$(git -C "${kernel_checkout}/lib/ExcessivelySafeCall" rev-parse HEAD)" = "${excessively_safe_call_ref}" ]
git -C "${ecdsa_kernel_checkout}" submodule update --init --depth 1 lib/solady
[ "$(git -C "${ecdsa_kernel_checkout}/lib/solady" rev-parse HEAD)" = "${ecdsa_solady_ref}" ]

npm install --global yarn@1.22.22
yarn --cwd "${aa_checkout}" install --frozen-lockfile --non-interactive
(
  cd "${aa_checkout}"
  PATH="${aa_checkout}/node_modules/.bin:${PATH}"
  export PATH
  ./scripts/hh-wrapper compile
)
npm ci --prefix "${workspace}/.github/scripts/mainnet-aa-solc" --ignore-scripts

node "${workspace}/.github/scripts/extract-mainnet-aa-verification-inputs.mjs" \
  "${aa_checkout}" "${kernel_checkout}" "${ecdsa_kernel_checkout}" "${output_directory}"

for compiler_package in solc-0.8.23 solc-0.8.24 solc-0.8.25 solc-0.8.28; do
  test -s "${workspace}/.github/scripts/mainnet-aa-solc/node_modules/${compiler_package}/solc.js"
done

compile_plan="${output_directory}/.compile-plan.tsv"
node -e '
  const fs = require("fs");
  const manifest = JSON.parse(fs.readFileSync(process.argv[1], "utf8"));
  if (!Array.isArray(manifest.contracts) || manifest.contracts.length !== 5) process.exit(2);
  for (const contract of manifest.contracts) {
    const fields = [contract.compilerPackage, contract.standardInputFile, contract.compilerOutputFile];
    if (fields.some((field) => typeof field !== "string" || field.includes("\t") || field.includes("\n"))) process.exit(2);
    console.log(fields.join("\t"));
  }
' "${output_directory}/manifest.json" >"${compile_plan}"

compiled_count=0
while IFS="$(printf '\t')" read -r compiler_package standard_input_file compiler_output_file; do
  case "${compiler_package}" in
    solc-0.8.23 | solc-0.8.24 | solc-0.8.25 | solc-0.8.28) ;;
    *)
      echo "Unexpected Mainnet compiler package: ${compiler_package}" >&2
      exit 2
      ;;
  esac
  compiler_js="${workspace}/.github/scripts/mainnet-aa-solc/node_modules/${compiler_package}/solc.js"
  raw_compiler_output="${output_directory}/.${compiler_output_file}.raw"
  node "${compiler_js}" --standard-json \
    <"${output_directory}/${standard_input_file}" \
    >"${raw_compiler_output}"
  node -e '
    const fs = require("fs");
    const raw = fs.readFileSync(process.argv[1], "utf8");
    const jsonStart = raw.indexOf("{");
    if (jsonStart < 0) process.exit(2);
    const prefixLines = raw.slice(0, jsonStart).split(/\r?\n/).filter((line) => line.trim() !== "");
    if (prefixLines.some((line) => !line.startsWith(">>> "))) process.exit(2);
    const parsed = JSON.parse(raw.slice(jsonStart));
    fs.writeFileSync(process.argv[2], JSON.stringify(parsed) + "\n");
  ' "${raw_compiler_output}" "${output_directory}/${compiler_output_file}"
  rm -f "${raw_compiler_output}"
  test -s "${output_directory}/${standard_input_file}"
  test -s "${output_directory}/${compiler_output_file}"
  compiled_count="$((compiled_count + 1))"
done <"${compile_plan}"
rm -f "${compile_plan}"
[ "${compiled_count}" -eq 5 ]

test -s "${output_directory}/entry-point.compiler-output.json"
test -s "${output_directory}/kernel.compiler-output.json"
test -s "${output_directory}/kernel-factory.compiler-output.json"
test -s "${output_directory}/ecdsa-validator.compiler-output.json"
test -s "${output_directory}/factory-staker.compiler-output.json"
test -s "${output_directory}/manifest.json"
node "${workspace}/.github/scripts/verify-mainnet-aa-bytecode.mjs" \
  "${output_directory}" "${rpc_url}"
