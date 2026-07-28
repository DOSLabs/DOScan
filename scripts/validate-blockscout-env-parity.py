#!/usr/bin/env python3
"""Validate that Mainnet and Testnet only differ for chain-specific settings."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV_DIR = ROOT / "docker-compose" / "envs"

COMMON_FILE = ENV_DIR / "common-blockscout.env"
MAINNET_FILE = ENV_DIR / "common-blockscout-mainnet.env"
TESTNET_FILE = ENV_DIR / "common-blockscout-testnet.env"

ALLOWED_DIFFERENT_KEYS = {
    "BLOCKSCOUT_HOST",
    "CHAIN_ID",
    "DATABASE_URL",
    "ETHEREUM_JSONRPC_DISABLE_ARCHIVE_BALANCES",
    "ETHEREUM_JSONRPC_HTTP_URL",
    "ETHEREUM_JSONRPC_PENDING_TRANSACTIONS_TYPE",
    "ETHEREUM_JSONRPC_TRACE_URL",
    "ETHEREUM_JSONRPC_WS_URL",
    "INDEXER_DISABLE_INTERNAL_TRANSACTIONS_FETCHER",
    "INDEXER_DISABLE_PENDING_TRANSACTIONS_FETCHER",
    "INDEXER_INTERNAL_TRANSACTIONS_TRACER_TYPE",
    "MICROSERVICE_ACCOUNT_ABSTRACTION_ENABLED",
    "MICROSERVICE_ACCOUNT_ABSTRACTION_URL",
    "NEW_TAGS",
    "NFT_MEDIA_HANDLER_BUCKET_FOLDER",
    "SECRET_KEY_BASE",
    "SUBNETWORK",
}

ALLOWED_DIFFERENT_PREFIXES = ("CUSTOM_CONTRACT_ADDRESSES_",)

SHARED_FEATURE_KEYS = {
    "ADMIN_PANEL_ENABLED",
    "API_RATE_LIMIT_IS_BLOCKSCOUT_BEHIND_PROXY",
    "API_RATE_LIMIT_REMOTE_IP_HEADERS",
    "DISABLE_FILE_LOGGING",
    "HEALTH_MONITOR_BLOCKS_PERIOD",
    "HEALTH_MONITOR_CHECK_INTERVAL",
    "INDEXER_TOKEN_INSTANCE_CIDR_BLACKLIST",
    "MICROSERVICE_SC_VERIFIER_ENABLED",
    "MICROSERVICE_SC_VERIFIER_TYPE",
    "MICROSERVICE_SC_VERIFIER_URL",
    "NFT_MEDIA_HANDLER_ENABLED",
    "NFT_MEDIA_HANDLER_REMOTE_DISPATCHER_NODE_MODE_ENABLED",
    "PUBLIC_METRICS_ENABLED",
    "PUBLIC_METRICS_UPDATE_PERIOD_HOURS",
    "SOURCIFY_INTEGRATION_ENABLED",
    "SOURCIFY_REPO_URL",
    "SOURCIFY_SERVER_URL",
}


def read_env(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key] = value
    return result


def is_allowed_difference(key: str) -> bool:
    return key in ALLOWED_DIFFERENT_KEYS or key.startswith(ALLOWED_DIFFERENT_PREFIXES)


def main() -> int:
    common = read_env(COMMON_FILE)
    mainnet_override = read_env(MAINNET_FILE)
    testnet_override = read_env(TESTNET_FILE)

    errors: list[str] = []

    for key in sorted(SHARED_FEATURE_KEYS):
        if key not in common:
            errors.append(f"{key} must be active in {COMMON_FILE.name}")
        if key in mainnet_override:
            errors.append(f"{key} must not be overridden in {MAINNET_FILE.name}")
        if key in testnet_override:
            errors.append(f"{key} must not be overridden in {TESTNET_FILE.name}")

    mainnet = common | mainnet_override
    testnet = common | testnet_override

    expected_nft_media_folders = {
        MAINNET_FILE.name: (mainnet_override, "mainnet/nft-media"),
        TESTNET_FILE.name: (testnet_override, "testnet/nft-media"),
    }
    for file_name, (overrides, expected_folder) in expected_nft_media_folders.items():
        actual_folder = overrides.get("NFT_MEDIA_HANDLER_BUCKET_FOLDER")
        if actual_folder != expected_folder:
            errors.append(
                f"NFT_MEDIA_HANDLER_BUCKET_FOLDER in {file_name} must be "
                f"{expected_folder!r}, got {actual_folder!r}"
            )

    for key in sorted(mainnet.keys() | testnet.keys()):
        if mainnet.get(key) != testnet.get(key) and not is_allowed_difference(key):
            errors.append(f"Unexpected Mainnet/Testnet difference: {key}")

    if errors:
        print("Blockscout environment parity validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    differences = [
        key
        for key in sorted(mainnet.keys() | testnet.keys())
        if mainnet.get(key) != testnet.get(key)
    ]
    print(
        "Blockscout environment parity passed. "
        f"{len(differences)} chain-specific differences are allowed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
