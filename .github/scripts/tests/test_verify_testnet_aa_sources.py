import http.server
import json
import os
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / ".github" / "scripts" / "verify-testnet-aa-sources.sh"
ENTRY_POINT = "0x4337084D9E255Ff0702461CF8895CE9E3b5Ff108"
FACTORY = "0xe908bff16d2a2ee257873708dbec8029ee9cd2cc"
FACTORY_ARGS = (
    "0000000000000000000000004337084d9e255ff0702461cf8895ce9e3b5ff108"
)


def exact_contract(name, source_path, constructor_args=""):
    return {
        "is_verified": True,
        "is_fully_verified": True,
        "is_partially_verified": False,
        "verified_twin_address_hash": None,
        "name": name,
        "compiler_version": "v0.8.28+commit.7893614a",
        "optimization_enabled": True,
        "optimization_runs": 1_000_000,
        "evm_version": "cancun",
        "file_path": source_path,
        "constructor_args": constructor_args,
        "compiler_settings": {"viaIR": True},
    }


ENTRY_POINT_EXACT = exact_contract("EntryPoint", "contracts/core/EntryPoint.sol")
FACTORY_EXACT = exact_contract(
    "SimpleAccountFactory",
    "contracts/accounts/SimpleAccountFactory.sol",
    FACTORY_ARGS,
)
UNVERIFIED = {
    "creation_bytecode": "0x60006000",
    "deployed_bytecode": "0x6001",
    "creation_status": "success",
    "implementations": None,
    "proxy_type": None,
}


class VerifyTestnetAaSourcesTests(unittest.TestCase):
    def test_already_exact_contracts_are_not_submitted(self):
        result, state = self._run_verifier(
            {ENTRY_POINT.lower(): [ENTRY_POINT_EXACT], FACTORY.lower(): [FACTORY_EXACT]}
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual([], state["posts"])
        self.assertEqual(1, state["gets"][ENTRY_POINT.lower()])
        self.assertEqual(1, state["gets"][FACTORY.lower()])

    def test_submits_standard_input_and_polls_through_transient_failure(self):
        result, state = self._run_verifier(
            {
                ENTRY_POINT.lower(): [ENTRY_POINT_EXACT],
                FACTORY.lower(): [UNVERIFIED, (503, {"message": "busy"}), FACTORY_EXACT],
            }
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(1, len(state["posts"]))
        post = state["posts"][0]
        self.assertIn(FACTORY.lower(), post["path"].lower())
        self.assertIn('name="compiler_version"', post["body"])
        self.assertIn("v0.8.28+commit.7893614a", post["body"])
        self.assertIn('name="contract_name"', post["body"])
        self.assertIn(
            "contracts/accounts/SimpleAccountFactory.sol:SimpleAccountFactory",
            post["body"],
        )
        self.assertIn('name="autodetect_constructor_args"', post["body"])
        self.assertIn("false", post["body"])
        self.assertIn(FACTORY_ARGS, post["body"])
        self.assertIn('name="files[0]"', post["body"])
        self.assertGreaterEqual(state["gets"][FACTORY.lower()], 3)

    def test_rejects_verified_contract_with_inexact_metadata(self):
        mutations = {
            "partial": {
                **ENTRY_POINT_EXACT,
                "is_fully_verified": False,
                "is_partially_verified": True,
            },
            "compiler": {
                **ENTRY_POINT_EXACT,
                "compiler_version": "v0.8.27+commit.40a35a09",
            },
            "evm": {**ENTRY_POINT_EXACT, "evm_version": "paris"},
            "optimizer": {**ENTRY_POINT_EXACT, "optimization_runs": 200},
            "source": {**ENTRY_POINT_EXACT, "file_path": "EntryPoint.sol"},
            "name": {**ENTRY_POINT_EXACT, "name": "WrongEntryPoint"},
            "via_ir": {**ENTRY_POINT_EXACT, "compiler_settings": {"viaIR": False}},
            "twin": {**ENTRY_POINT_EXACT, "verified_twin_address_hash": FACTORY},
        }

        for name, response in mutations.items():
            with self.subTest(name=name):
                result, state = self._run_verifier(
                    {
                        ENTRY_POINT.lower(): [response],
                        FACTORY.lower(): [FACTORY_EXACT],
                    }
                )
                self.assertNotEqual(0, result.returncode)
                self.assertIn("metadata", result.stderr.lower())
                self.assertEqual([], state["posts"])

    def test_rejects_wrong_factory_constructor_arguments(self):
        response = {**FACTORY_EXACT, "constructor_args": "00"}
        result, state = self._run_verifier(
            {ENTRY_POINT.lower(): [ENTRY_POINT_EXACT], FACTORY.lower(): [response]}
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("metadata", result.stderr.lower())
        self.assertEqual([], state["posts"])

    def test_rejects_malformed_verified_response(self):
        response = dict(ENTRY_POINT_EXACT)
        del response["file_path"]
        result, state = self._run_verifier(
            {ENTRY_POINT.lower(): [response], FACTORY.lower(): [FACTORY_EXACT]}
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("metadata", result.stderr.lower())
        self.assertEqual([], state["posts"])

    def test_unverified_contract_times_out_with_bounded_attempts(self):
        result, state = self._run_verifier(
            {ENTRY_POINT.lower(): [UNVERIFIED], FACTORY.lower(): [FACTORY_EXACT]},
            attempts=3,
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("timed out", result.stderr.lower())
        self.assertEqual(1, len(state["posts"]))
        self.assertEqual(3, state["gets"][ENTRY_POINT.lower()])

    def test_rejected_submission_fails_with_bounded_retries(self):
        result, state = self._run_verifier(
            {ENTRY_POINT.lower(): [UNVERIFIED], FACTORY.lower(): [FACTORY_EXACT]},
            post_response=(500, {"message": "rejected"}),
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("submission failed", result.stderr.lower())
        self.assertEqual(3, len(state["posts"]))

    def test_does_not_accept_already_verified_submission_without_exact_metadata(self):
        result, state = self._run_verifier(
            {ENTRY_POINT.lower(): [UNVERIFIED], FACTORY.lower(): [FACTORY_EXACT]},
            post_response=(200, {"message": "Already verified"}),
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("unexpected response", result.stderr.lower())
        self.assertEqual(1, len(state["posts"]))

    def test_rejects_noncanonical_manifest_before_http(self):
        def mutate(manifest):
            manifest["contracts"][0]["address"] = FACTORY

        result, state = self._run_verifier(
            {ENTRY_POINT.lower(): [ENTRY_POINT_EXACT], FACTORY.lower(): [FACTORY_EXACT]},
            manifest_mutate=mutate,
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("manifest is invalid", result.stderr.lower())
        self.assertEqual(0, sum(state["gets"].values()))
        self.assertEqual([], state["posts"])

    def _run_verifier(
        self, responses, attempts=5, post_response=None, manifest_mutate=None
    ):
        class ResponseHandler(http.server.BaseHTTPRequestHandler):
            state = {
                "gets": {address: 0 for address in responses},
                "posts": [],
            }

            def do_GET(self):
                address = self.path.split("/smart-contracts/", 1)[-1].split("?", 1)[0].lower()
                queue = responses[address]
                index = self.state["gets"][address]
                self.state["gets"][address] += 1
                response = queue[min(index, len(queue) - 1)]
                status, body = response if isinstance(response, tuple) else (200, response)
                self._send(status, body)

            def do_POST(self):
                length = int(self.headers.get("content-length", "0"))
                body = self.rfile.read(length).decode("utf-8", errors="replace")
                self.state["posts"].append(
                    {
                        "path": self.path,
                        "body": body,
                        "content_type": self.headers.get("content-type", ""),
                    }
                )
                status, response = post_response or (
                    200,
                    {"message": "Smart-contract verification started"},
                )
                self._send(status, response)

            def _send(self, status, body):
                payload = json.dumps(body).encode("utf-8")
                self.send_response(status)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, _format, *_args):
                return

        api_host = self._wsl_gateway() if os.name == "nt" else "127.0.0.1"
        server = http.server.ThreadingHTTPServer((api_host, 0), ResponseHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                verification_directory = Path(directory)
                self._write_artifacts(verification_directory, manifest_mutate)
                environment = os.environ.copy()
                overrides = {
                    "DOSCAN_AA_API_BASE_URL": f"http://{api_host}:{server.server_port}",
                    "DOSCAN_AA_API_HOST_HEADER": "test.doscan.io",
                    "DOSCAN_AA_POLL_ATTEMPTS": str(attempts),
                    "DOSCAN_AA_POLL_INTERVAL_SECONDS": "0",
                    "DOSCAN_AA_MAX_SECONDS": "30",
                    "DOSCAN_AA_CURL_RETRY_DELAY_SECONDS": "0",
                    "DOSCAN_AA_CURL_RETRY_MAX_SECONDS": "3",
                }
                environment.update(overrides)
                if os.name == "nt":
                    script_path = self._wsl_path(SCRIPT_PATH)
                    artifact_path = self._wsl_path(verification_directory)
                    command = ["wsl.exe", "env"]
                    command.extend(f"{key}={value}" for key, value in overrides.items())
                    command.extend(["/bin/sh", script_path, artifact_path])
                else:
                    command = [
                        "bash",
                        SCRIPT_PATH.as_posix(),
                        verification_directory.as_posix(),
                    ]
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    check=False,
                    env=environment,
                    timeout=20,
                )
                return result, ResponseHandler.state
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    @staticmethod
    def _wsl_path(path):
        result = subprocess.run(
            ["wsl.exe", "wslpath", "-a", str(path.resolve()).replace("\\", "/")],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    @staticmethod
    def _wsl_gateway():
        result = subprocess.run(
            ["wsl.exe", "ip", "route", "show", "default"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.split()[2]

    @staticmethod
    def _write_artifacts(directory, manifest_mutate=None):
        manifest = {
            "version": 1,
            "compilerVersion": "v0.8.28+commit.7893614a",
            "evmVersion": "cancun",
            "optimizer": {"enabled": True, "runs": 1_000_000},
            "viaIR": True,
            "contracts": [
                {
                    "key": "entry-point",
                    "address": ENTRY_POINT,
                    "contractName": "EntryPoint",
                    "sourcePath": "contracts/core/EntryPoint.sol",
                    "standardInputFile": "entry-point.standard-input.json",
                    "constructorArgs": "",
                },
                {
                    "key": "simple-account-factory",
                    "address": FACTORY,
                    "contractName": "SimpleAccountFactory",
                    "sourcePath": "contracts/accounts/SimpleAccountFactory.sol",
                    "standardInputFile": "simple-account-factory.standard-input.json",
                    "constructorArgs": FACTORY_ARGS,
                },
            ],
        }
        if manifest_mutate:
            manifest_mutate(manifest)
        (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        for contract in manifest["contracts"]:
            (directory / contract["standardInputFile"]).write_text(
                json.dumps({"language": "Solidity", "sources": {}, "settings": {}}),
                encoding="utf-8",
            )


if __name__ == "__main__":
    unittest.main()
