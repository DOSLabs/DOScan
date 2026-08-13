import hashlib
import json
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / ".github" / "scripts" / "verify-mainnet-aa-bytecode.mjs"
ADDRESS = "0xd6CEDDe84be40893d153Be9d467CD6aD37875b28"
EXPECTED_GETTER = "0x0000000071727De22E5E9d8BAf0edAc6f37da032"
COMPILED_CODE = "0x600160026003"
LIVE_CODE = "0x600160ff6003"


def code_hash(code):
    return hashlib.sha256(code.lower().encode("utf-8")).hexdigest()


class RpcServer:
    def __init__(self, code=LIVE_CODE, getter=EXPECTED_GETTER, failures=0):
        self.code = code
        self.getter = getter
        self.failures = failures
        self.requests = []
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length))
                owner.requests.append(payload)
                if owner.failures > 0:
                    owner.failures -= 1
                    self.send_response(503)
                    self.end_headers()
                    return
                if payload["method"] == "eth_getCode":
                    result = owner.code
                elif payload["method"] == "eth_call":
                    result = "0x" + "0" * 24 + owner.getter[2:].lower()
                else:
                    result = None
                body = json.dumps({"jsonrpc": "2.0", "id": payload["id"], "result": result}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, _format, *_args):
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return f"http://127.0.0.1:{self.server.server_port}"

    def __exit__(self, *_args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()


class VerifyMainnetAaBytecodeTests(unittest.TestCase):
    def write_artifacts(self, directory, *, live_code=LIVE_CODE, output_mutator=None):
        target = {
            "key": "kernel",
            "address": ADDRESS,
            "contractName": "Kernel",
            "sourcePath": "src/Kernel.sol",
            "compilerOutputFile": "kernel.compiler-output.json",
            "expectedCodeSha256": code_hash(live_code),
            "rpcChecks": [{"signature": "entrypoint()", "expectedAddress": EXPECTED_GETTER}],
        }
        manifest = {"version": 2, "chainId": 7979, "contracts": [target]}
        output = {
            "contracts": {
                "src/Kernel.sol": {
                    "Kernel": {
                        "evm": {
                            "deployedBytecode": {
                                "object": COMPILED_CODE[2:],
                                "immutableReferences": {"1": [{"start": 3, "length": 1}]},
                                "linkReferences": {},
                            },
                            "methodIdentifiers": {"entrypoint()": "b0d691fe"},
                        }
                    }
                }
            },
            "errors": [],
        }
        if output_mutator:
            output_mutator(output)
        Path(directory, "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        Path(directory, target["compilerOutputFile"]).write_text(json.dumps(output), encoding="utf-8")

    def run_verifier(self, directory, rpc_url):
        return subprocess.run(
            ["node", str(SCRIPT), str(directory), rpc_url],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )

    def test_accepts_exact_code_and_immutable_getters(self):
        with tempfile.TemporaryDirectory() as directory:
            self.write_artifacts(directory)
            server = RpcServer()
            with server as rpc_url:
                result = self.run_verifier(directory, rpc_url)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(["eth_getCode", "eth_call"], [request["method"] for request in server.requests])

    def test_rejects_live_code_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            self.write_artifacts(directory, live_code=LIVE_CODE)
            with RpcServer(code="0x600160aa6003") as rpc_url:
                result = self.run_verifier(directory, rpc_url)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("hash", result.stderr.lower())

    def test_rejects_non_immutable_byte_mismatch(self):
        mismatched = "0x610160ff6003"
        with tempfile.TemporaryDirectory() as directory:
            self.write_artifacts(directory, live_code=mismatched)
            with RpcServer(code=mismatched) as rpc_url:
                result = self.run_verifier(directory, rpc_url)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("outside immutable", result.stderr.lower())

    def test_rejects_wrong_immutable_getter(self):
        with tempfile.TemporaryDirectory() as directory:
            self.write_artifacts(directory)
            with RpcServer(getter="0x1111111111111111111111111111111111111111") as rpc_url:
                result = self.run_verifier(directory, rpc_url)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("entrypoint()", result.stderr)

    def test_rejects_unresolved_library_link(self):
        def mutate(output):
            deployed = output["contracts"]["src/Kernel.sol"]["Kernel"]["evm"]["deployedBytecode"]
            deployed["object"] = "6001__$1234567890123456789012345678901234$__6003"

        with tempfile.TemporaryDirectory() as directory:
            self.write_artifacts(directory, output_mutator=mutate)
            with RpcServer() as rpc_url:
                result = self.run_verifier(directory, rpc_url)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("unresolved", result.stderr.lower())

    def test_rejects_compiler_error_or_missing_contract(self):
        mutations = [
            lambda output: output["errors"].append({"severity": "error", "formattedMessage": "compile failed"}),
            lambda output: output.update({"contracts": {}}),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as directory:
                self.write_artifacts(directory, output_mutator=mutate)
                with RpcServer() as rpc_url:
                    result = self.run_verifier(directory, rpc_url)
                self.assertNotEqual(0, result.returncode)

    def test_retries_transient_rpc_failure_with_a_finite_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            self.write_artifacts(directory)
            server = RpcServer(failures=2)
            with server as rpc_url:
                result = self.run_verifier(directory, rpc_url)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(4, len(server.requests))

            server = RpcServer(failures=99)
            with server as rpc_url:
                result = self.run_verifier(directory, rpc_url)
            self.assertNotEqual(0, result.returncode)
            self.assertEqual(3, len(server.requests))


if __name__ == "__main__":
    unittest.main()
