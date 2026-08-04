import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
IMMUTABLE_IMAGE_RE = re.compile(
    r"^(?P<repository>[^\s:@]+(?:/[^\s:@]+)*):"
    r"(?P<tag>[^\s@]+)@sha256:(?P<digest>[0-9a-f]{64})$"
)

COMPOSE_FILES = (
    "docker-compose/docker-compose-mainnet.yml",
    "docker-compose/docker-compose-testnet.yml",
    "docker-compose/docker-compose-beta.yml",
)
STATUS_DOCUMENTS = (
    "docs/FEATURES.md",
    "docs/CHANGELOG.md",
    "docs/DOScan-ARCHITECTURE.md",
)
ARCHITECTURE_DOCUMENT = "docs/DOScan-ARCHITECTURE.md"
COMMON_BLOCKSCOUT_ENV = "docker-compose/envs/common-blockscout.env"
DEPLOY_WORKFLOW = ".github/workflows/deploy-config.yml"
GCP_KEYS = (
    "GCP_INSTANCE",
    "GCP_ZONE",
    "GCP_TESTNET_INSTANCE",
    "GCP_TESTNET_ZONE",
)
BENS_KEYS = (
    "MICROSERVICE_BENS_ENABLED",
    "MICROSERVICE_BENS_URL",
    "MICROSERVICE_BENS_PROTOCOLS",
)
NAME_SERVICE_API_HOST = "NEXT_PUBLIC_NAME_SERVICE_API_HOST"
FRONTEND_ENV_FILES = (
    "docker-compose/envs/common-frontend.env",
    "docker-compose/envs/common-frontend-scan.env",
    "docker-compose/envs/common-frontend-testnet.env",
    "docker-compose/envs/common-frontend-beta.env",
)


def diagnostic(path: Path, invariant: str, expected: object, actual: object) -> str:
    return (
        f"{path.as_posix()}: {invariant}; "
        f"expected {expected!r}; actual {actual!r}"
    )


def read_required(root: Path, relative_path: str) -> str:
    return (root / relative_path).read_text(encoding="utf-8")


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def read_workflow_env(text: str, keys: tuple[str, ...]) -> dict[str, str]:
    values: dict[str, str] = {}
    key_pattern = "|".join(re.escape(key) for key in keys)
    assignment_pattern = re.compile(
        rf"^\s*(?P<key>{key_pattern}):\s*(?P<value>[^#]*?)(?:\s+#.*)?$"
    )
    for line in text.splitlines():
        match = assignment_pattern.match(line)
        if match is not None:
            values[match.group("key")] = match.group("value").strip().strip("\"'")
    return values


def extract_service_image(compose: str, service: str) -> str | None:
    lines = compose.splitlines()
    service_pattern = re.compile(rf"^  {re.escape(service)}:\s*(?:#.*)?$")
    service_index = next(
        (index for index, line in enumerate(lines) if service_pattern.match(line)),
        None,
    )
    if service_index is None:
        return None

    image_pattern = re.compile(r"^\s{4}image:\s*(\S+)\s*(?:#.*)?$")
    next_service_pattern = re.compile(r"^  [^\s:#][^:]*:\s*(?:#.*)?$")
    for line in lines[service_index + 1 :]:
        if next_service_pattern.match(line):
            break
        image_match = image_pattern.match(line)
        if image_match:
            return image_match.group(1)
    return None


def parse_immutable_image(image: str) -> dict[str, str] | None:
    match = IMMUTABLE_IMAGE_RE.fullmatch(image)
    return match.groupdict() if match else None


def backend_runtime_version(image: str) -> str | None:
    parsed = parse_immutable_image(image)
    if parsed is None:
        return None
    return f"v{parsed['tag'].replace('.commit.', '.+commit.')}"


def validate_repository(root: Path) -> list[str]:
    errors: list[str] = []
    images: dict[str, dict[str, str]] = {"backend": {}, "frontend": {}}
    documents: dict[str, str] = {}

    for compose_path in COMPOSE_FILES:
        try:
            compose = read_required(root, compose_path)
        except FileNotFoundError:
            errors.append(
                diagnostic(
                    Path(compose_path), "missing required file", "present", "missing"
                )
            )
            continue

        for service in images:
            image = extract_service_image(compose, service)
            if image is None:
                errors.append(
                    diagnostic(
                        Path(compose_path),
                        f"{service} image",
                        "service image key",
                        "missing",
                    )
                )
            elif parse_immutable_image(image) is None:
                errors.append(
                    diagnostic(
                        Path(compose_path),
                        f"{service} immutable image pin",
                        "tag@sha256:<64 lowercase hexadecimal characters>",
                        image,
                    )
                )
            else:
                images[service][compose_path] = image

    canonical_images: dict[str, str] = {}
    mainnet_path = COMPOSE_FILES[0]
    for service, service_images in images.items():
        canonical_image = service_images.get(mainnet_path)
        if canonical_image is None:
            continue
        canonical_images[service] = canonical_image
        for compose_path, image in service_images.items():
            if image != canonical_image:
                errors.append(
                    diagnostic(
                        Path(compose_path), f"{service} image", canonical_image, image
                    )
                )

    backend_image = canonical_images.get("backend")
    frontend_image = canonical_images.get("frontend")
    frontend_version = (
        parse_immutable_image(frontend_image)["tag"] if frontend_image is not None else None
    )
    for document_path in STATUS_DOCUMENTS:
        try:
            document = read_required(root, document_path)
        except FileNotFoundError:
            errors.append(
                diagnostic(
                    Path(document_path),
                    "missing required file",
                    "present",
                    "missing",
                )
            )
            continue

        documents[document_path] = document

        if backend_image is not None and backend_image not in document:
            errors.append(
                diagnostic(
                    Path(document_path), "backend image", backend_image, "token not found"
                )
            )
        if frontend_version is not None and frontend_version not in document:
            errors.append(
                diagnostic(
                    Path(document_path),
                    "frontend version",
                    frontend_version,
                    "token not found",
                )
            )
        if document_path == ARCHITECTURE_DOCUMENT and frontend_image is not None:
            if frontend_image not in document:
                errors.append(
                    diagnostic(
                        Path(document_path),
                        "frontend image",
                        frontend_image,
                        "token not found",
                    )
                )

    common_blockscout_path = root / COMMON_BLOCKSCOUT_ENV
    try:
        blockscout_env = read_env(common_blockscout_path)
    except FileNotFoundError:
        errors.append(
            diagnostic(
                Path(COMMON_BLOCKSCOUT_ENV), "missing required file", "present", "missing"
            )
        )
    else:
        metadata_enabled = blockscout_env.get("MICROSERVICE_METADATA_ENABLED")
        if metadata_enabled != "true":
            errors.append(
                diagnostic(
                    Path(COMMON_BLOCKSCOUT_ENV),
                    "metadata enabled",
                    "true",
                    metadata_enabled if metadata_enabled is not None else "missing",
                )
            )
        for key in BENS_KEYS:
            value = blockscout_env.get(key)
            is_active = (
                value is not None and value != "false"
                if key == "MICROSERVICE_BENS_ENABLED"
                else bool(value)
            )
            if is_active:
                errors.append(
                    diagnostic(
                        Path(COMMON_BLOCKSCOUT_ENV),
                        f"BENS disabled ({key})",
                        "unset",
                        value,
                    )
                )

    for frontend_env_file in FRONTEND_ENV_FILES:
        frontend_env_path = root / frontend_env_file
        try:
            frontend_env = read_env(frontend_env_path)
        except FileNotFoundError:
            errors.append(
                diagnostic(
                    Path(frontend_env_file),
                    "missing required file",
                    "present",
                    "missing",
                )
            )
            continue
        name_service_api_host = frontend_env.get(NAME_SERVICE_API_HOST)
        if name_service_api_host:
            errors.append(
                diagnostic(
                    Path(frontend_env_file),
                    f"{NAME_SERVICE_API_HOST} disabled",
                    "unset",
                    name_service_api_host,
                )
            )

    try:
        workflow_env = read_workflow_env(read_required(root, DEPLOY_WORKFLOW), GCP_KEYS)
    except FileNotFoundError:
        errors.append(
            diagnostic(Path(DEPLOY_WORKFLOW), "missing required file", "present", "missing")
        )
    else:
        architecture_document = documents.get(ARCHITECTURE_DOCUMENT)
        for key in GCP_KEYS:
            value = workflow_env.get(key)
            if not value:
                errors.append(
                    diagnostic(
                        Path(DEPLOY_WORKFLOW),
                        key,
                        "defined workflow value",
                        "missing",
                    )
                )
            elif architecture_document is not None and value not in architecture_document:
                errors.append(
                    diagnostic(
                        Path(ARCHITECTURE_DOCUMENT), key, value, "token not found"
                    )
                )

    return errors


def main() -> int:
    errors = validate_repository(ROOT)
    if errors:
        print("Production documentation drift validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Production documentation drift validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
