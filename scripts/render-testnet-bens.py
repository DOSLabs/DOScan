#!/usr/bin/env python3
"""Render the BENS config from a DOS Names deployment manifest."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BENS_DIR = ROOT / "docker-compose" / "bens"
ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
REPLACEMENTS = {
    "__ROOT_REGISTRY_ADDRESS__": "rootRegistry",
}
REQUIRED_CONTRACTS = {
    "dosRegistry",
    "dosRegistrar",
    "permissionedResolverImplementation",
    "rootRegistry",
}


def load_deployment(path: Path) -> dict[str, object]:
    deployment = json.loads(path.read_text(encoding="utf-8"))
    if deployment.get("chainId") != 3939:
        raise ValueError("Deployment manifest chainId must be 3939")
    deployment_block = deployment.get("deploymentBlock")
    if not isinstance(deployment_block, int) or deployment_block < 0:
        raise ValueError(
            "Deployment manifest deploymentBlock must be a non-negative integer"
        )
    contracts = deployment.get("contracts")
    if not isinstance(contracts, dict):
        raise ValueError("Deployment manifest contracts must be an object")
    for field in REQUIRED_CONTRACTS:
        value = contracts.get(field)
        if not isinstance(value, str) or not ADDRESS_RE.fullmatch(value):
            raise ValueError(f"Deployment contract {field} has an invalid address")
        if int(value, 16) == 0:
            raise ValueError(f"Deployment contract {field} must not be the zero address")
    if deployment.get("smokeName") != "bens-smoke.dos":
        raise ValueError("Deployment manifest smokeName must be bens-smoke.dos")
    return deployment


def render_config(
    template_path: Path,
    output_path: Path,
    deployment: dict[str, object],
) -> None:
    contracts = deployment["contracts"]
    if not isinstance(contracts, dict):
        raise ValueError("Deployment manifest contracts must be an object")
    rendered = template_path.read_text(encoding="utf-8")
    for placeholder, field in REPLACEMENTS.items():
        rendered = rendered.replace(placeholder, str(contracts[field]))
    leftovers = sorted(set(re.findall(r"__[A-Z0-9_]+__", rendered)))
    if leftovers:
        raise ValueError(f"Unresolved placeholders in {template_path.name}: {leftovers}")
    output_path.write_text(rendered, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--deployment",
        type=Path,
        default=BENS_DIR / "deployment.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=BENS_DIR / "config.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    deployment = load_deployment(args.deployment)
    render_config(BENS_DIR / "config.template.json", args.output, deployment)
    print("Rendered DOScan Testnet BENS configuration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
