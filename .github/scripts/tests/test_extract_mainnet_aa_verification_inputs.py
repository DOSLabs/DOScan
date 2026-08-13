import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / ".github" / "scripts" / "extract-mainnet-aa-verification-inputs.mjs"


class ExtractMainnetAaVerificationInputsTests(unittest.TestCase):
    def test_extracts_five_contract_specific_inputs_and_manifest(self):
        result, output = self._run_extractor()

        self.assertEqual(0, result.returncode, result.stderr)
        manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(2, manifest["version"])
        self.assertEqual(7979, manifest["chainId"])

        contracts = {contract["key"]: contract for contract in manifest["contracts"]}
        self.assertEqual(
            [
                "entry-point",
                "kernel",
                "kernel-factory",
                "ecdsa-validator",
                "factory-staker",
            ],
            [contract["key"] for contract in manifest["contracts"]],
        )
        self.assertEqual(
            "dependencies/kernel-v3.3/src/factory/KernelFactory.sol",
            contracts["kernel-factory"]["sourcePath"],
        )
        self.assertEqual(
            "FactoryStaker", contracts["factory-staker"]["contractName"]
        )
        self.assertEqual(
            "v0.8.23+commit.f704f362",
            contracts["entry-point"]["compilerVersion"],
        )
        self.assertEqual(
            "v0.8.25+commit.b61c2a91",
            contracts["ecdsa-validator"]["compilerVersion"],
        )
        self.assertEqual("full", contracts["entry-point"]["verificationMatch"])
        self.assertEqual("partial", contracts["ecdsa-validator"]["verificationMatch"])
        self.assertEqual(
            "d13e7ff2bc90271659100c83f49ee6250555bbf26ed35c2315f243c6849a2127",
            contracts["kernel"]["expectedCodeSha256"],
        )
        self.assertEqual(
            [{
                "signature": "entrypoint()",
                "expectedAddress": "0x0000000071727De22E5E9d8BAf0edAc6f37da032",
            }],
            contracts["kernel"]["rpcChecks"],
        )

        entry_point_input = self._read_input(output, contracts["entry-point"])
        self.assertEqual("paris", entry_point_input["settings"]["evmVersion"])
        self.assertEqual(
            {"enabled": True, "runs": 1_000_000},
            entry_point_input["settings"]["optimizer"],
        )
        self.assertTrue(entry_point_input["settings"]["viaIR"])
        self.assertEqual(
            "ipfs",
            entry_point_input["settings"].get("metadata", {}).get(
                "bytecodeHash", "ipfs"
            ),
        )

        kernel_input = self._read_input(output, contracts["kernel"])
        self.assertEqual("prague", kernel_input["settings"]["evmVersion"])
        self.assertEqual(
            {"appendCBOR": False, "bytecodeHash": "none"},
            kernel_input["settings"]["metadata"],
        )
        self.assertTrue(kernel_input["settings"]["viaIR"])
        self.assertIn("src/interfaces/I.sol", kernel_input["sources"])
        self.assertIn("lib/solady/src/utils/EIP712.sol", kernel_input["sources"])
        self.assertIn(
            "lib/ExcessivelySafeCall/src/ExcessivelySafeCall.sol",
            kernel_input["sources"],
        )

        factory_input = self._read_input(output, contracts["kernel-factory"])
        self.assertIn(
            "dependencies/kernel-v3.3/src/factory/KernelFactory.sol",
            factory_input["sources"],
        )
        self.assertIn(
            "dependencies/solady-0.1.26/src/utils/LibClone.sol",
            factory_input["sources"],
        )

        ecdsa_input = self._read_input(output, contracts["ecdsa-validator"])
        self.assertIn(
            "// pinned ECDSA deployment source",
            ecdsa_input["sources"]["src/validator/ECDSAValidator.sol"]["content"],
        )
        factory_staker_input = self._read_input(
            output, contracts["factory-staker"]
        )
        self.assertIn(
            "// pinned FactoryStaker deployment dependency",
            factory_staker_input["sources"]["src/factory/KernelFactory.sol"][
                "content"
            ],
        )

        factory_staker_input = self._read_input(
            output, contracts["factory-staker"]
        )
        self.assertNotIn("viaIR", factory_staker_input["settings"])
        self.assertIn(
            "src/factory/KernelFactory.sol", factory_staker_input["sources"]
        )
        self.assertIn(
            "lib/solady/src/auth/Ownable.sol", factory_staker_input["sources"]
        )

        entry_point_selection = entry_point_input["settings"]["outputSelection"]["*"]["*"]
        self.assertIn("evm.deployedBytecode", entry_point_selection)
        self.assertIn("evm.methodIdentifiers", entry_point_selection)

        for key, contract in contracts.items():
            if key == "entry-point":
                continue
            standard_input = self._read_input(output, contract)
            selection = standard_input["settings"]["outputSelection"]["*"]["*"]
            self.assertEqual(
                [
                    "abi",
                    "evm.deployedBytecode.object",
                    "evm.deployedBytecode.immutableReferences",
                    "evm.deployedBytecode.linkReferences",
                    "evm.methodIdentifiers",
                ],
                selection,
            )

    def test_rejects_missing_kernel_import_without_manifest(self):
        def mutate(_aa_checkout, kernel_checkout):
            (kernel_checkout / "src" / "interfaces" / "I.sol").unlink()

        result, output = self._run_extractor(mutate)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("I.sol", result.stderr)
        self.assertFalse((output / "manifest.json").exists())

    def test_rejects_noncanonical_entrypoint_build_settings(self):
        def mutate(aa_checkout, _kernel_checkout):
            build_path = aa_checkout / "artifacts" / "build-info" / "build.json"
            build = json.loads(build_path.read_text(encoding="utf-8"))
            build["input"]["settings"]["optimizer"]["runs"] = 200
            build_path.write_text(json.dumps(build), encoding="utf-8")

        result, output = self._run_extractor(mutate)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("optimizer", result.stderr.lower())
        self.assertFalse((output / "manifest.json").exists())

    def test_rejects_noncanonical_entrypoint_provenance_fields(self):
        mutations = [
            (
                "compiler",
                lambda build: build.update(
                    {"solcLongVersion": "0.8.22+commit.4fc1097e"}
                ),
            ),
            (
                "evm version",
                lambda build: build["input"]["settings"].update(
                    {"evmVersion": "shanghai"}
                ),
            ),
            (
                "spdx",
                lambda build: build["input"]["sources"][
                    "contracts/core/EntryPoint.sol"
                ].update(
                    {"content": "// SPDX-License-Identifier: MIT\ncontract EntryPoint {}"}
                ),
            ),
            (
                "missing",
                lambda build: build["input"]["sources"][
                    "contracts/core/EntryPoint.sol"
                ].update(
                    {"content": "// SPDX-License-Identifier: GPL-3.0\ncontract WrongEntryPoint {}"}
                ),
            ),
        ]
        for expected_error, mutate_build in mutations:
            with self.subTest(expected_error=expected_error):
                def mutate(aa_checkout, _kernel_checkout):
                    build_path = aa_checkout / "artifacts" / "build-info" / "build.json"
                    build = json.loads(build_path.read_text(encoding="utf-8"))
                    mutate_build(build)
                    build_path.write_text(json.dumps(build), encoding="utf-8")

                result, output = self._run_extractor(mutate)
                self.assertNotEqual(0, result.returncode)
                self.assertIn(expected_error, result.stderr.lower())
                self.assertFalse((output / "manifest.json").exists())

    def test_rejects_import_outside_pinned_source_root(self):
        def mutate(_aa_checkout, kernel_checkout):
            kernel = kernel_checkout / "src" / "Kernel.sol"
            kernel.write_text(
                kernel.read_text(encoding="utf-8")
                + '\nimport "../../../outside.sol";\n',
                encoding="utf-8",
            )

        result, output = self._run_extractor(mutate)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("escapes source-unit root", result.stderr)
        self.assertFalse((output / "manifest.json").exists())

    def _run_extractor(self, mutate=None):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        root = Path(temporary_directory.name)
        aa_checkout = root / "account-abstraction"
        kernel_checkout = root / "kernel"
        ecdsa_kernel_checkout = root / "kernel-ecdsa"
        output = root / "output"
        self._write_entrypoint_build(aa_checkout)
        self._write_kernel_checkout(kernel_checkout)
        self._write_kernel_checkout(ecdsa_kernel_checkout)
        ecdsa_path = ecdsa_kernel_checkout / "src" / "validator" / "ECDSAValidator.sol"
        ecdsa_path.write_text(
            ecdsa_path.read_text(encoding="utf-8")
            + "\n// pinned ECDSA deployment source\n",
            encoding="utf-8",
        )
        legacy_factory_path = (
            ecdsa_kernel_checkout / "src" / "factory" / "KernelFactory.sol"
        )
        legacy_factory_path.write_text(
            legacy_factory_path.read_text(encoding="utf-8")
            + "\n// pinned FactoryStaker deployment dependency\n",
            encoding="utf-8",
        )
        if mutate:
            mutate(aa_checkout, kernel_checkout)

        result = subprocess.run(
            [
                "node",
                str(SCRIPT_PATH),
                str(aa_checkout),
                str(kernel_checkout),
                str(ecdsa_kernel_checkout),
                str(output),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        return result, output

    @staticmethod
    def _read_input(output, contract):
        return json.loads(
            (output / contract["standardInputFile"]).read_text(encoding="utf-8")
        )

    @staticmethod
    def _write_entrypoint_build(checkout):
        build_path = checkout / "artifacts" / "build-info" / "build.json"
        build_path.parent.mkdir(parents=True)
        source_path = "contracts/core/EntryPoint.sol"
        build = {
            "solcLongVersion": "0.8.23+commit.f704f362",
            "input": {
                "language": "Solidity",
                "sources": {
                    source_path: {
                        "content": "// SPDX-License-Identifier: GPL-3.0\ncontract EntryPoint {}"
                    }
                },
                "settings": {
                    "evmVersion": "paris",
                    "optimizer": {"enabled": True, "runs": 1_000_000},
                    "viaIR": True,
                    "outputSelection": {
                        "*": {
                            "*": [
                                "abi",
                                "evm.bytecode",
                                "evm.deployedBytecode",
                                "evm.methodIdentifiers",
                                "metadata",
                            ],
                            "": ["ast"],
                        }
                    },
                },
            },
            "output": {
                "contracts": {source_path: {"EntryPoint": {"abi": []}}}
            },
        }
        build_path.write_text(json.dumps(build), encoding="utf-8")
        debug_path = (
            checkout
            / "artifacts"
            / "contracts"
            / "core"
            / "EntryPoint.sol"
            / "EntryPoint.dbg.json"
        )
        debug_path.parent.mkdir(parents=True)
        debug_path.write_text(
            json.dumps({"buildInfo": "../../../build-info/build.json"}),
            encoding="utf-8",
        )

    @staticmethod
    def _write_kernel_checkout(checkout):
        files = {
            "src/Kernel.sol": (
                "// SPDX-License-Identifier: MIT\n"
                "pragma solidity ^0.8.0;\n"
                'import {I} from "./interfaces/I.sol";\n'
                'import {EIP712} from "solady/utils/EIP712.sol";\n'
                'import {ExcessivelySafeCall} from "ExcessivelySafeCall/ExcessivelySafeCall.sol";\n'
                "contract Kernel {}\n"
            ),
            "src/interfaces/I.sol": (
                "// SPDX-License-Identifier: MIT\n"
                "pragma solidity ^0.8.0;\n"
                "interface I {}\n"
            ),
            "src/factory/KernelFactory.sol": (
                "// SPDX-License-Identifier: MIT\n"
                "pragma solidity ^0.8.0;\n"
                'import {LibClone} from "solady/utils/LibClone.sol";\n'
                "contract KernelFactory {}\n"
            ),
            "src/validator/ECDSAValidator.sol": (
                "// SPDX-License-Identifier: MIT\n"
                "pragma solidity ^0.8.0;\n"
                'import {I} from "../interfaces/I.sol";\n'
                'import {ECDSA} from "solady/utils/ECDSA.sol";\n'
                "contract ECDSAValidator {}\n"
            ),
            "src/factory/FactoryStaker.sol": (
                "// SPDX-License-Identifier: MIT\n"
                "pragma solidity ^0.8.0;\n"
                'import "./KernelFactory.sol";\n'
                'import {Ownable} from "solady/auth/Ownable.sol";\n'
                "contract FactoryStaker {}\n"
            ),
            "lib/solady/src/utils/EIP712.sol": (
                "// SPDX-License-Identifier: MIT\n"
                "pragma solidity ^0.8.0;\n"
                "abstract contract EIP712 {}\n"
            ),
            "lib/solady/src/utils/LibClone.sol": (
                "// SPDX-License-Identifier: MIT\n"
                "pragma solidity ^0.8.0;\n"
                "library LibClone {}\n"
            ),
            "lib/solady/src/utils/ECDSA.sol": (
                "// SPDX-License-Identifier: MIT\n"
                "pragma solidity ^0.8.0;\n"
                "library ECDSA {}\n"
            ),
            "lib/solady/src/auth/Ownable.sol": (
                "// SPDX-License-Identifier: MIT\n"
                "pragma solidity ^0.8.0;\n"
                "abstract contract Ownable {}\n"
            ),
            "lib/ExcessivelySafeCall/src/ExcessivelySafeCall.sol": (
                "// SPDX-License-Identifier: MIT OR Apache-2.0\n"
                "pragma solidity ^0.8.0;\n"
                "library ExcessivelySafeCall {}\n"
            ),
        }
        for relative_path, content in files.items():
            path = checkout / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
