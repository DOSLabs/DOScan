import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / ".github" / "scripts" / "extract-aa-verification-inputs.mjs"


class ExtractAaVerificationInputsTests(unittest.TestCase):
    def test_extracts_exact_hardhat_inputs_and_manifest(self):
        result, output = self._run_extractor()

        self.assertEqual(0, result.returncode, result.stderr)
        manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(1, manifest["version"])
        self.assertEqual("v0.8.28+commit.7893614a", manifest["compilerVersion"])
        self.assertEqual("cancun", manifest["evmVersion"])
        self.assertTrue(manifest["optimizer"]["enabled"])
        self.assertEqual(1_000_000, manifest["optimizer"]["runs"])
        self.assertTrue(manifest["viaIR"])

        contracts = {contract["key"]: contract for contract in manifest["contracts"]}
        entry_point = contracts["entry-point"]
        factory = contracts["simple-account-factory"]
        self.assertEqual(
            "0x4337084D9E255Ff0702461CF8895CE9E3b5Ff108",
            entry_point["address"],
        )
        self.assertEqual("EntryPoint", entry_point["contractName"])
        self.assertEqual("contracts/core/EntryPoint.sol", entry_point["sourcePath"])
        self.assertEqual("", entry_point["constructorArgs"])
        self.assertEqual(
            "0xe908bff16d2a2ee257873708dbec8029ee9cd2cc",
            factory["address"],
        )
        self.assertEqual("SimpleAccountFactory", factory["contractName"])
        self.assertEqual(
            "contracts/accounts/SimpleAccountFactory.sol", factory["sourcePath"]
        )
        self.assertEqual(
            "0000000000000000000000004337084d9e255ff0702461cf8895ce9e3b5ff108",
            factory["constructorArgs"],
        )

        for contract in contracts.values():
            standard_input_path = output / contract["standardInputFile"]
            self.assertTrue(standard_input_path.is_file())
            standard_input = json.loads(standard_input_path.read_text(encoding="utf-8"))
            self.assertEqual("Solidity", standard_input["language"])
            self.assertEqual("cancun", standard_input["settings"]["evmVersion"])
            self.assertEqual(
                {"enabled": True, "runs": 1_000_000},
                standard_input["settings"]["optimizer"],
            )
            self.assertTrue(standard_input["settings"]["viaIR"])

    def test_rejects_noncanonical_compiler_and_settings(self):
        mutations = {
            "compiler": lambda build: build.update(
                {"solcLongVersion": "0.8.27+commit.40a35a09"}
            ),
            "evm": lambda build: build["input"]["settings"].update(
                {"evmVersion": "paris"}
            ),
            "optimizer": lambda build: build["input"]["settings"].update(
                {"optimizer": {"enabled": True, "runs": 200}}
            ),
            "via_ir": lambda build: build["input"]["settings"].update(
                {"viaIR": False}
            ),
        }

        for name, mutate in mutations.items():
            with self.subTest(name=name):
                result, _output = self._run_extractor(mutate)
                self.assertNotEqual(0, result.returncode)

    def test_rejects_build_info_without_target_contract(self):
        def mutate(build):
            del build["output"]["contracts"]["contracts/core/EntryPoint.sol"][
                "EntryPoint"
            ]

        result, _output = self._run_extractor(mutate)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("EntryPoint", result.stderr)

    def _run_extractor(self, mutate=None):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        root = Path(temporary_directory.name)
        checkout = root / "account-abstraction"
        output = root / "output"
        build_info_path = checkout / "artifacts" / "build-info" / "build.json"
        build_info_path.parent.mkdir(parents=True)

        source_paths = (
            "contracts/core/EntryPoint.sol",
            "contracts/accounts/SimpleAccountFactory.sol",
        )
        build = {
            "solcVersion": "0.8.28",
            "solcLongVersion": "0.8.28+commit.7893614a",
            "input": {
                "language": "Solidity",
                "sources": {
                    path: {"content": f"contract {Path(path).stem} {{}}"}
                    for path in source_paths
                },
                "settings": {
                    "evmVersion": "cancun",
                    "optimizer": {"enabled": True, "runs": 1_000_000},
                    "viaIR": True,
                    "outputSelection": {"*": {"*": ["abi", "evm.bytecode"]}},
                },
            },
            "output": {
                "contracts": {
                    "contracts/core/EntryPoint.sol": {"EntryPoint": {"abi": []}},
                    "contracts/accounts/SimpleAccountFactory.sol": {
                        "SimpleAccountFactory": {"abi": []}
                    },
                }
            },
        }
        if mutate:
            mutate(build)
        build_info_path.write_text(json.dumps(build), encoding="utf-8")

        for source_path, contract_name in (
            ("contracts/core/EntryPoint.sol", "EntryPoint"),
            (
                "contracts/accounts/SimpleAccountFactory.sol",
                "SimpleAccountFactory",
            ),
        ):
            artifact_directory = checkout / "artifacts" / source_path
            artifact_directory.mkdir(parents=True, exist_ok=True)
            debug_file = artifact_directory / f"{contract_name}.dbg.json"
            relative_build_info = Path("../../../build-info/build.json")
            debug_file.write_text(
                json.dumps({"buildInfo": relative_build_info.as_posix()}),
                encoding="utf-8",
            )

        result = subprocess.run(
            ["node", str(SCRIPT_PATH), str(checkout), str(output)],
            capture_output=True,
            text=True,
            check=False,
        )
        return result, output


if __name__ == "__main__":
    unittest.main()
