import http.server
import json
import os
import subprocess
import tempfile
import threading
import unittest
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / ".github" / "scripts" / "verify-mainnet-aa-sources.sh"

TARGETS = [
    {
        "key": "entry-point",
        "address": "0x0000000071727De22E5E9d8BAf0edAc6f37da032",
        "contractName": "EntryPoint",
        "sourcePath": "contracts/core/EntryPoint.sol",
        "standardInputFile": "entry-point.standard-input.json",
        "compilerOutputFile": "entry-point.compiler-output.json",
        "compilerPackage": "solc-0.8.23",
        "compilerVersion": "v0.8.23+commit.f704f362",
        "evmVersion": "paris",
        "optimizer": {"enabled": True, "runs": 1_000_000},
        "viaIR": True,
        "metadata": {"bytecodeHash": "ipfs"},
        "licenseType": "gnu_gpl_v3",
        "spdxLicense": "GPL-3.0",
        "constructorArgs": "",
        "expectedCodeSha256": "4dcad467095cd9af58006b270475ac7591c6946bca08552f6789727097b51eae",
        "rpcChecks": [],
        "verificationMatch": "full",
    },
    {
        "key": "kernel",
        "address": "0xd6CEDDe84be40893d153Be9d467CD6aD37875b28",
        "contractName": "Kernel",
        "sourcePath": "src/Kernel.sol",
        "standardInputFile": "kernel.standard-input.json",
        "compilerOutputFile": "kernel.compiler-output.json",
        "compilerPackage": "solc-0.8.28",
        "compilerVersion": "v0.8.28+commit.7893614a",
        "evmVersion": "prague",
        "optimizer": {"enabled": True, "runs": 200},
        "viaIR": True,
        "metadata": {"appendCBOR": False, "bytecodeHash": "none"},
        "licenseType": "mit",
        "spdxLicense": "MIT",
        "constructorArgs": "0000000000000000000000000000000071727de22e5e9d8baf0edac6f37da032",
        "expectedCodeSha256": "d13e7ff2bc90271659100c83f49ee6250555bbf26ed35c2315f243c6849a2127",
        "rpcChecks": [{"signature": "entrypoint()", "expectedAddress": "0x0000000071727De22E5E9d8BAf0edAc6f37da032"}],
        "verificationMatch": "partial",
    },
    {
        "key": "kernel-factory",
        "address": "0x2577507b78c2008Ff367261CB6285d44ba5eF2E9",
        "contractName": "KernelFactory",
        "sourcePath": "dependencies/kernel-v3.3/src/factory/KernelFactory.sol",
        "standardInputFile": "kernel-factory.standard-input.json",
        "compilerOutputFile": "kernel-factory.compiler-output.json",
        "compilerPackage": "solc-0.8.28",
        "compilerVersion": "v0.8.28+commit.7893614a",
        "evmVersion": "prague",
        "optimizer": {"enabled": True, "runs": 200},
        "viaIR": True,
        "metadata": {"appendCBOR": False, "bytecodeHash": "none"},
        "licenseType": "mit",
        "spdxLicense": "MIT",
        "constructorArgs": "000000000000000000000000d6cedde84be40893d153be9d467cd6ad37875b28",
        "expectedCodeSha256": "56443d7d18bfd62d5d69b04fc8207e439bf904166335dd7159e0eeef1cba2367",
        "rpcChecks": [{"signature": "implementation()", "expectedAddress": "0xd6CEDDe84be40893d153Be9d467CD6aD37875b28"}],
        "verificationMatch": "partial",
    },
    {
        "key": "ecdsa-validator",
        "address": "0x845ADb2C711129d4f3966735eD98a9F09fC4cE57",
        "contractName": "ECDSAValidator",
        "sourcePath": "src/validator/ECDSAValidator.sol",
        "standardInputFile": "ecdsa-validator.standard-input.json",
        "compilerOutputFile": "ecdsa-validator.compiler-output.json",
        "compilerPackage": "solc-0.8.25",
        "compilerVersion": "v0.8.25+commit.b61c2a91",
        "evmVersion": "paris",
        "optimizer": {"enabled": True, "runs": 200},
        "viaIR": True,
        "metadata": {"appendCBOR": False, "bytecodeHash": "none"},
        "licenseType": "mit",
        "spdxLicense": "MIT",
        "constructorArgs": "",
        "expectedCodeSha256": "be711f07f49e57bf56c512b6f32f7c77d9ec1881c4051ed33a45cfad8c7a8b8e",
        "rpcChecks": [],
        "verificationMatch": "partial",
    },
    {
        "key": "factory-staker",
        "address": "0xd703aaE79538628d27099B8c4f621bE4CCd142d5",
        "contractName": "FactoryStaker",
        "sourcePath": "src/factory/FactoryStaker.sol",
        "standardInputFile": "factory-staker.standard-input.json",
        "compilerOutputFile": "factory-staker.compiler-output.json",
        "compilerPackage": "solc-0.8.24",
        "compilerVersion": "v0.8.24+commit.e11b9ed9",
        "evmVersion": "paris",
        "optimizer": {"enabled": True, "runs": 200},
        "viaIR": False,
        "metadata": {"appendCBOR": False, "bytecodeHash": "none"},
        "licenseType": "mit",
        "spdxLicense": "MIT",
        "constructorArgs": "",
        "expectedCodeSha256": "f91091bf1260892a4d0b834494489fea55be2f2f968ad6b1abc1410531f2a2a1",
        "rpcChecks": [],
        "verificationMatch": "partial",
    },
]

UNVERIFIED = {"creation_bytecode": "0x6000", "deployed_bytecode": "0x6001"}


def exact_contract(target):
    return {
        "is_verified": True,
        "is_fully_verified": target["verificationMatch"] == "full",
        "is_partially_verified": target["verificationMatch"] == "partial",
        "verified_twin_address_hash": None,
        "name": target["contractName"],
        "compiler_version": target["compilerVersion"],
        "optimization_enabled": True,
        "optimization_runs": target["optimizer"]["runs"],
        "evm_version": target["evmVersion"],
        "file_path": target["sourcePath"],
        "license_type": target["licenseType"],
        "constructor_args": target["constructorArgs"],
        "compiler_settings": {"viaIR": target["viaIR"], "metadata": target["metadata"]},
    }


class VerifyMainnetAaSourcesTests(unittest.TestCase):
    def exact_responses(self):
        return {target["address"].lower(): [exact_contract(target)] for target in TARGETS}

    def test_five_exact_contracts_are_not_submitted(self):
        result, state = self.run_verifier(self.exact_responses())
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual([], state["posts"])
        self.assertEqual(5, sum(state["gets"].values()))

    def test_submits_each_unverified_contract_with_its_own_profile(self):
        responses = {
            target["address"].lower(): [UNVERIFIED, exact_contract(target)] for target in TARGETS
        }
        result, state = self.run_verifier(responses)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(5, len(state["posts"]))
        for target, post in zip(TARGETS, state["posts"]):
            self.assertIn(target["compilerVersion"], post["body"])
            self.assertIn(f'{target["sourcePath"]}:{target["contractName"]}', post["body"])
            self.assertIn(target["licenseType"], post["body"])
        self.assertIn("src/factory/FactoryStaker.sol:FactoryStaker", state["posts"][-1]["body"])
        self.assertNotIn("MetaFactory", state["posts"][-1]["body"])

    def test_already_verified_race_requires_exact_get(self):
        responses = self.exact_responses()
        first = TARGETS[0]
        responses[first["address"].lower()] = [UNVERIFIED, exact_contract(first)]
        result, state = self.run_verifier(
            responses, post_response=(200, {"message": "Already verified"})
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(2, state["gets"][first["address"].lower()])

        responses[first["address"].lower()] = [UNVERIFIED]
        result, _ = self.run_verifier(
            responses, attempts=2, post_response=(200, {"message": "Already verified"})
        )
        self.assertNotEqual(0, result.returncode)

    def test_rejects_wrong_metadata_for_each_profile_field(self):
        mutations = [
            (0, "compiler_version", "v0.8.22+commit.4fc1097e"),
            (1, "optimization_runs", 1_000_000),
            (2, "evm_version", "paris"),
            (3, "license_type", "gnu_gpl_v3"),
            (4, "file_path", "MetaFactory.sol"),
        ]
        for index, field, value in mutations:
            with self.subTest(index=index, field=field):
                responses = self.exact_responses()
                target = TARGETS[index]
                response = exact_contract(target)
                response[field] = value
                responses[target["address"].lower()] = [response]
                result, state = self.run_verifier(responses)
                self.assertNotEqual(0, result.returncode)
                self.assertIn("metadata", result.stderr.lower())
                self.assertEqual([], state["posts"])

        settings_mutations = [
            (0, {"viaIR": False, "metadata": {"bytecodeHash": "ipfs"}}),
            (1, {"viaIR": True, "metadata": {"appendCBOR": True, "bytecodeHash": "none"}}),
            (4, {"viaIR": True, "metadata": {"appendCBOR": False, "bytecodeHash": "none"}}),
        ]
        for index, compiler_settings in settings_mutations:
            with self.subTest(index=index, compiler_settings=compiler_settings):
                responses = self.exact_responses()
                target = TARGETS[index]
                response = exact_contract(target)
                response["compiler_settings"] = compiler_settings
                responses[target["address"].lower()] = [response]
                result, state = self.run_verifier(responses)
                self.assertNotEqual(0, result.returncode)
                self.assertIn("metadata", result.stderr.lower())
                self.assertEqual([], state["posts"])

    def test_rejects_unexpected_match_or_twin_verification(self):
        for mutation in [
            {"is_fully_verified": False, "is_partially_verified": True},
            {"verified_twin_address_hash": TARGETS[1]["address"]},
        ]:
            responses = self.exact_responses()
            response = exact_contract(TARGETS[0])
            response.update(mutation)
            responses[TARGETS[0]["address"].lower()] = [response]
            result, _ = self.run_verifier(responses)
            self.assertNotEqual(0, result.returncode)

    def test_one_global_deadline_covers_all_five_contracts(self):
        responses = self.exact_responses()
        responses[TARGETS[0]["address"].lower()] = [UNVERIFIED, exact_contract(TARGETS[0])]
        responses[TARGETS[1]["address"].lower()] = [UNVERIFIED]
        result, state = self.run_verifier(
            responses, max_seconds=5, clock_values=[100, 101, 102, 103, 105]
        )
        self.assertNotEqual(0, result.returncode)
        self.assertIn("timed out", result.stderr.lower())
        self.assertEqual(0, state["gets"][TARGETS[1]["address"].lower()])

    def test_rejects_noncanonical_manifest_before_http(self):
        mutations = [
            lambda manifest: manifest.update({"chainId": 3939}),
            lambda manifest: manifest["contracts"][0].update({"address": TARGETS[1]["address"]}),
            lambda manifest: manifest["contracts"].reverse(),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                result, state = self.run_verifier(self.exact_responses(), manifest_mutate=mutation)
                self.assertNotEqual(0, result.returncode)
                self.assertIn("manifest is invalid", result.stderr.lower())
                self.assertEqual(0, sum(state["gets"].values()))

    def test_rejects_missing_or_renamed_standard_input(self):
        for mode in ["missing", "renamed"]:
            result, state = self.run_verifier(self.exact_responses(), input_mode=mode)
            self.assertNotEqual(0, result.returncode)
            self.assertEqual(0, sum(state["gets"].values()))

    def run_verifier(
        self,
        responses,
        attempts=5,
        post_response=None,
        manifest_mutate=None,
        input_mode=None,
        clock_values=None,
        max_seconds=30,
    ):
        class Handler(http.server.BaseHTTPRequestHandler):
            state = {"gets": {address: 0 for address in responses}, "posts": []}

            def do_GET(self):
                address = self.path.split("/smart-contracts/", 1)[-1].split("?", 1)[0].lower()
                queue = responses[address]
                index = self.state["gets"][address]
                self.state["gets"][address] += 1
                response = queue[min(index, len(queue) - 1)]
                status, body = response if isinstance(response, tuple) else (200, response)
                self.send_json(status, body)

            def do_POST(self):
                length = int(self.headers.get("content-length", "0"))
                body = self.rfile.read(length).decode("utf-8", errors="replace")
                self.state["posts"].append({"path": self.path, "body": body})
                status, response = post_response or (200, {"message": "Smart-contract verification started"})
                self.send_json(status, response)

            def send_json(self, status, body):
                payload = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, _format, *_args):
                return

        api_host = self.wsl_gateway() if os.name == "nt" else "127.0.0.1"
        server = http.server.ThreadingHTTPServer((api_host, 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                artifact_directory = Path(directory)
                self.write_artifacts(artifact_directory, manifest_mutate, input_mode)
                overrides = {
                    "DOSCAN_MAINNET_AA_API_BASE_URL": f"http://{api_host}:{server.server_port}",
                    "DOSCAN_MAINNET_AA_API_HOST_HEADER": "doscan.io",
                    "DOSCAN_MAINNET_AA_POLL_ATTEMPTS": str(attempts),
                    "DOSCAN_MAINNET_AA_POLL_INTERVAL_SECONDS": "0",
                    "DOSCAN_MAINNET_AA_MAX_SECONDS": str(max_seconds),
                    "DOSCAN_MAINNET_AA_CURL_RETRY_DELAY_SECONDS": "0",
                    "DOSCAN_MAINNET_AA_CURL_RETRY_MAX_SECONDS": "3",
                }
                if clock_values is not None:
                    clock = artifact_directory / "fake-date.sh"
                    counter = artifact_directory / "fake-date-counter"
                    clock.write_text(
                        "#!/bin/sh\n"
                        'index="$(cat "${DOSCAN_FAKE_DATE_COUNTER}" 2>/dev/null || printf 0)"\n'
                        "position=0\nvalue=\nold_ifs=${IFS}\nIFS=,\n"
                        "set -- ${DOSCAN_FAKE_DATE_VALUES}\nIFS=${old_ifs}\n"
                        'for candidate in "$@"; do value="${candidate}"; '
                        'if [ "${position}" -eq "${index}" ]; then break; fi; '
                        "position=$((position + 1)); done\n"
                        'printf "%s" "$((index + 1))" > "${DOSCAN_FAKE_DATE_COUNTER}"\n'
                        'printf "%s\\n" "${value}"\n',
                        encoding="utf-8",
                        newline="\n",
                    )
                    clock.chmod(0o755)
                    overrides["DOSCAN_MAINNET_AA_DATE_BIN"] = self.wsl_path(clock) if os.name == "nt" else clock.as_posix()
                    overrides["DOSCAN_FAKE_DATE_COUNTER"] = self.wsl_path(counter) if os.name == "nt" else counter.as_posix()
                    overrides["DOSCAN_FAKE_DATE_VALUES"] = ",".join(map(str, clock_values))
                environment = os.environ.copy()
                environment.update(overrides)
                if os.name == "nt":
                    command = ["wsl.exe", "env", *[f"{key}={value}" for key, value in overrides.items()], "/bin/sh", self.wsl_path(SCRIPT_PATH), self.wsl_path(artifact_directory)]
                else:
                    command = ["/bin/sh", SCRIPT_PATH.as_posix(), artifact_directory.as_posix()]
                result = subprocess.run(command, capture_output=True, text=True, env=environment, timeout=20, check=False)
                return result, Handler.state
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    @staticmethod
    def write_artifacts(directory, manifest_mutate=None, input_mode=None):
        manifest = {"version": 2, "chainId": 7979, "contracts": deepcopy(TARGETS)}
        if manifest_mutate:
            manifest_mutate(manifest)
        if input_mode == "renamed":
            manifest["contracts"][0]["standardInputFile"] = "renamed.standard-input.json"
        (directory / "manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        for index, target in enumerate(manifest["contracts"]):
            filename = target["standardInputFile"]
            if index == 0 and input_mode == "missing":
                continue
            (directory / filename).write_text(json.dumps({"language": "Solidity"}), encoding="utf-8")

    @staticmethod
    def wsl_path(path):
        result = subprocess.run(["wsl.exe", "wslpath", "-a", str(path.resolve()).replace("\\", "/")], capture_output=True, text=True, check=True)
        return result.stdout.strip()

    @staticmethod
    def wsl_gateway():
        result = subprocess.run(["wsl.exe", "ip", "route", "show", "default"], capture_output=True, text=True, check=True)
        return result.stdout.split()[2]


if __name__ == "__main__":
    unittest.main()
