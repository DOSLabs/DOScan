import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
IMMUTABLE_IMAGE_RE = re.compile(
    r"^(?P<repository>[^\s:@]+(?:/[^\s:@]+)*):"
    r"(?P<tag>[^\s@]+)@sha256:(?P<digest>[0-9a-f]{64})$"
)
ENV_REFERENCE_RE = re.compile(
    r"^\$\{(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?::-(?P<default>.*))?\}$"
)
YAML_KEY_RE = re.compile(r"^(?P<key>[A-Za-z0-9_.-]+):(?P<value>.*)$")

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
FEATURES_DOCUMENT = "docs/FEATURES.md"
CHANGELOG_DOCUMENT = "docs/CHANGELOG.md"
ARCHITECTURE_DOCUMENT = "docs/DOScan-ARCHITECTURE.md"
COMMON_BLOCKSCOUT_ENV = "docker-compose/envs/common-blockscout.env"
DEPLOY_WORKFLOW = ".github/workflows/deploy-config.yml"
DEPENDENCY_WORKFLOW = ".github/workflows/dependency-build.yml"
VALIDATOR_COMMAND = "python .github/scripts/validate-docs-production-status.py"
GCP_KEYS = (
    "GCP_INSTANCE",
    "GCP_ZONE",
    "GCP_TESTNET_INSTANCE",
    "GCP_TESTNET_ZONE",
)
PROTECTED_BACKEND_ENV = {
    "MICROSERVICE_METADATA_ENABLED": "true",
    "MICROSERVICE_BENS_ENABLED": "false",
    "MICROSERVICE_BENS_URL": "",
    "MICROSERVICE_BENS_PROTOCOLS": "",
}
BENS_KEYS = tuple(key for key in PROTECTED_BACKEND_ENV if "BENS" in key)
NAME_SERVICE_API_HOST = "NEXT_PUBLIC_NAME_SERVICE_API_HOST"
FRONTEND_ENV_FILES = (
    "docker-compose/envs/common-frontend.env",
    "docker-compose/envs/common-frontend-scan.env",
    "docker-compose/envs/common-frontend-testnet.env",
    "docker-compose/envs/common-frontend-beta.env",
)
REQUIRED_DEPENDENCY_PUSH_PATHS = frozenset(
    (
        *COMPOSE_FILES,
        COMMON_BLOCKSCOUT_ENV,
        "docker-compose/envs/common-blockscout-mainnet.env",
        "docker-compose/envs/common-blockscout-testnet.env",
        "docker-compose/envs/common-blockscout-beta.env",
        "docker-compose/envs/common-frontend*.env",
        *STATUS_DOCUMENTS,
        DEPLOY_WORKFLOW,
        DEPENDENCY_WORKFLOW,
        ".github/scripts/validate-docs-production-status.py",
        ".github/scripts/tests/**",
    )
)


class StructureError(ValueError):
    pass


def diagnostic(path: Path, invariant: str, expected: object, actual: object) -> str:
    return (
        f"{path.as_posix()}: {invariant}; "
        f"expected {expected!r}; actual {actual!r}"
    )


def read_required(root: Path, relative_path: str) -> str:
    return (root / relative_path).read_text(encoding="utf-8")


def strip_inline_comment(value: str, require_closed_quote: bool = False) -> str:
    quote: str | None = None
    escaped = False
    for index, character in enumerate(value):
        if escaped:
            escaped = False
            continue
        if quote is not None:
            if quote == '"' and character == "\\":
                escaped = True
            elif character == quote:
                quote = None
            continue
        if character in ("'", '"'):
            quote = character
        elif character == "#" and (index == 0 or value[index - 1].isspace()):
            return value[:index].rstrip()
    if quote is not None and require_closed_quote:
        raise StructureError("unterminated quoted value")
    return value.rstrip()


def parse_scalar(value: str) -> str:
    normalized = strip_inline_comment(value, require_closed_quote=True).strip()
    if not normalized:
        return ""
    if normalized[0] in ("'", '"'):
        quote = normalized[0]
        if len(normalized) < 2 or normalized[-1] != quote:
            raise StructureError("unsupported characters after quoted value")
        return normalized[1:-1]
    return normalized


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) is None:
            raise StructureError(f"invalid env key at line {line_number}: {key!r}")
        values[key] = parse_scalar(raw_value)
    return values


def yaml_lines(text: str) -> list[tuple[int, int, str]]:
    lines: list[tuple[int, int, str]] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        prefix = raw_line[: len(raw_line) - len(raw_line.lstrip())]
        if "\t" in prefix:
            raise StructureError(f"tab indentation at line {line_number}")
        content = strip_inline_comment(raw_line.lstrip()).rstrip()
        if content:
            lines.append((line_number, len(prefix), content))
    return lines


def split_yaml_mapping(content: str) -> tuple[str, str] | None:
    match = YAML_KEY_RE.fullmatch(content)
    if match is None:
        return None
    return match.group("key"), match.group("value").strip()


def mapping_block(
    lines: list[tuple[int, int, str]],
    key: str,
    indent: int,
    start: int = 0,
    end: int | None = None,
) -> tuple[int, int]:
    if end is None:
        end = len(lines)
    occurrences: list[int] = []
    for index in range(start, end):
        _, line_indent, content = lines[index]
        entry = split_yaml_mapping(content)
        if line_indent == indent and entry is not None and entry[0] == key:
            occurrences.append(index)
    if not occurrences:
        raise StructureError(f"missing mapping {key!r}")
    if len(occurrences) > 1:
        raise StructureError(f"duplicate mapping {key!r}")
    mapping_index = occurrences[0]
    _, _, content = lines[mapping_index]
    _, value = split_yaml_mapping(content)
    if value:
        raise StructureError(f"unsupported inline value for mapping {key!r}")
    block_end = end
    for index in range(mapping_index + 1, end):
        if lines[index][1] <= indent:
            block_end = index
            break
    return mapping_index + 1, block_end


def direct_mapping_children(
    lines: list[tuple[int, int, str]],
    start: int,
    end: int,
    indent: int,
    context: str,
) -> dict[str, tuple[str, int, int]]:
    positions: list[tuple[str, str, int]] = []
    for index in range(start, end):
        _, line_indent, content = lines[index]
        if line_indent != indent:
            continue
        entry = split_yaml_mapping(content)
        if entry is None:
            raise StructureError(f"unsupported {context} entry at line {lines[index][0]}")
        positions.append((entry[0], entry[1], index))

    children: dict[str, tuple[str, int, int]] = {}
    for position, (key, value, index) in enumerate(positions):
        if key in children:
            raise StructureError(f"duplicate {context} entry {key!r}")
        child_end = end
        if position + 1 < len(positions):
            child_end = positions[position + 1][2]
        children[key] = (value, index + 1, child_end)
    return children


def parse_env_file_property(
    value: str,
    lines: list[tuple[int, int, str]],
    start: int,
    end: int,
) -> list[str]:
    if value:
        if value.startswith(("[", "{")):
            raise StructureError("unsupported inline env_file structure")
        return [parse_scalar(value)]

    env_files: list[str] = []
    for index in range(start, end):
        line_number, indent, content = lines[index]
        if indent != 6 or not content.startswith("- "):
            raise StructureError(f"unsupported env_file entry at line {line_number}")
        item = content[2:].strip()
        if not item or split_yaml_mapping(item) is not None:
            raise StructureError(f"unsupported env_file entry at line {line_number}")
        env_files.append(parse_scalar(item))
    if not env_files:
        raise StructureError("empty env_file list")
    return env_files


def parse_environment_property(
    value: str,
    lines: list[tuple[int, int, str]],
    start: int,
    end: int,
) -> dict[str, str | None]:
    if value:
        raise StructureError("unsupported inline environment structure")

    environment: dict[str, str | None] = {}
    style: str | None = None
    for index in range(start, end):
        line_number, indent, content = lines[index]
        if indent != 6:
            raise StructureError(f"unsupported environment entry at line {line_number}")
        if content.startswith("- "):
            if style == "mapping":
                raise StructureError("mixed environment mapping and list structures")
            style = "list"
            item = parse_scalar(content[2:])
            if "=" in item:
                key, raw_value = item.split("=", 1)
                parsed_value: str | None = raw_value
            else:
                key = item
                parsed_value = None
        else:
            if style == "list":
                raise StructureError("mixed environment mapping and list structures")
            style = "mapping"
            entry = split_yaml_mapping(content)
            if entry is None:
                raise StructureError(f"unsupported environment entry at line {line_number}")
            key, raw_value = entry
            parsed_value = parse_scalar(raw_value) if raw_value else None
        key = key.strip()
        if key in environment:
            raise StructureError(f"duplicate environment key {key!r}")
        environment[key] = parsed_value
    return environment


def parse_compose_services(compose: str) -> dict[str, dict[str, object]]:
    lines = yaml_lines(compose)
    services_start, services_end = mapping_block(lines, "services", 0)
    service_children = direct_mapping_children(
        lines, services_start, services_end, 2, "service"
    )
    services: dict[str, dict[str, object]] = {}
    for service, (service_value, service_start, service_end) in service_children.items():
        if service_value:
            raise StructureError(f"unsupported service structure for {service!r}")
        properties = direct_mapping_children(
            lines, service_start, service_end, 4, f"{service} property"
        )
        parsed: dict[str, object] = {
            "image": None,
            "env_files": [],
            "environment": {},
        }
        if "image" in properties:
            image_value, _, _ = properties["image"]
            if not image_value:
                raise StructureError(f"unsupported empty image for service {service!r}")
            parsed["image"] = parse_scalar(image_value)
        if "env_file" in properties:
            value, start, end = properties["env_file"]
            parsed["env_files"] = parse_env_file_property(value, lines, start, end)
        if "environment" in properties:
            value, start, end = properties["environment"]
            parsed["environment"] = parse_environment_property(
                value, lines, start, end
            )
        services[service] = parsed
    return services


def read_workflow_env(text: str, keys: tuple[str, ...]) -> dict[str, str]:
    lines = yaml_lines(text)
    env_start, env_end = mapping_block(lines, "env", 0)
    children = direct_mapping_children(lines, env_start, env_end, 2, "workflow env")
    values: dict[str, str] = {}
    for key in keys:
        if key not in children:
            continue
        value, child_start, child_end = children[key]
        if not value or child_start != child_end:
            raise StructureError(f"unsupported workflow env value for {key!r}")
        values[key] = parse_scalar(value)
    return values


def extract_service_image(compose: str, service: str) -> str | None:
    service_data = parse_compose_services(compose).get(service)
    return None if service_data is None else service_data["image"]


def parse_immutable_image(image: str) -> dict[str, str] | None:
    match = IMMUTABLE_IMAGE_RE.fullmatch(image)
    return match.groupdict() if match else None


def backend_runtime_version(image: str) -> str | None:
    parsed = parse_immutable_image(image)
    if parsed is None:
        return None
    return f"v{parsed['tag'].replace('.commit.', '.+commit.')}"


def markdown_section(text: str, heading_pattern: str) -> str:
    lines = text.splitlines()
    heading_re = re.compile(heading_pattern)
    matches = [index for index, line in enumerate(lines) if heading_re.fullmatch(line)]
    if not matches:
        raise StructureError(f"missing Markdown section matching {heading_pattern!r}")
    if len(matches) > 1:
        raise StructureError(f"duplicate Markdown section matching {heading_pattern!r}")
    start = matches[0]
    level = len(lines[start]) - len(lines[start].lstrip("#"))
    end = len(lines)
    for index in range(start + 1, len(lines)):
        match = re.match(r"^(?P<marks>#+)\s+", lines[index])
        if match is not None and len(match.group("marks")) <= level:
            end = index
            break
    return "\n".join(lines[start + 1 : end])


def markdown_table(
    section: str, expected_header: tuple[str, ...]
) -> list[dict[str, str]]:
    lines = section.splitlines()
    for index, line in enumerate(lines):
        if not line.strip().startswith("|"):
            continue
        header = tuple(markdown_cells(line))
        if header != expected_header:
            continue
        if index + 1 >= len(lines):
            break
        separator = markdown_cells(lines[index + 1])
        if len(separator) != len(header) or not all(
            re.fullmatch(r":?-{3,}:?", cell) for cell in separator
        ):
            raise StructureError(f"invalid Markdown table separator for {header!r}")
        rows: list[dict[str, str]] = []
        for row_line in lines[index + 2 :]:
            if not row_line.strip().startswith("|"):
                break
            cells = markdown_cells(row_line)
            if len(cells) != len(header):
                raise StructureError(f"invalid Markdown table row for {header!r}")
            rows.append(dict(zip(header, cells)))
        return rows
    raise StructureError(f"missing Markdown table with header {expected_header!r}")


def markdown_cells(line: str) -> list[str]:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return []
    cells: list[str] = []
    for cell in stripped[1:-1].split("|"):
        value = cell.strip()
        if len(value) >= 2 and value.startswith("`") and value.endswith("`"):
            value = value[1:-1]
        cells.append(value)
    return cells


def rows_by_key(
    rows: list[dict[str, str]], key_column: str, context: str
) -> dict[str, dict[str, str]]:
    keyed: dict[str, dict[str, str]] = {}
    for row in rows:
        key = row[key_column]
        if key in keyed:
            raise StructureError(f"duplicate {context} row {key!r}")
        keyed[key] = row
    return keyed


def append_mismatch(
    errors: list[str],
    path: Path,
    invariant: str,
    expected: object,
    actual: object,
) -> None:
    if actual != expected:
        errors.append(diagnostic(path, invariant, expected, actual))


def validate_features_document(
    document: str,
    path: Path,
    backend_image: str | None,
    frontend_version: str | None,
    errors: list[str],
) -> None:
    try:
        runtime = markdown_section(document, r"## Runtime Baseline")
        runtime_rows = rows_by_key(
            markdown_table(
                runtime,
                (
                    "Environment",
                    "Explorer",
                    "Chain ID",
                    "Frontend",
                    "Backend",
                    "Runtime status",
                ),
            ),
            "Environment",
            "runtime baseline",
        )
    except StructureError as error:
        errors.append(diagnostic(path, "current runtime structure", "supported table", str(error)))
    else:
        backend_version = (
            backend_runtime_version(backend_image) if backend_image is not None else None
        )
        for environment in ("Mainnet", "Testnet"):
            row = runtime_rows.get(environment, {})
            if frontend_version is not None:
                append_mismatch(
                    errors,
                    path,
                    f"frontend version ({environment})",
                    frontend_version,
                    row.get("Frontend", "missing"),
                )
            if backend_version is not None:
                append_mismatch(
                    errors,
                    path,
                    f"backend version ({environment})",
                    backend_version,
                    row.get("Backend", "missing"),
                )
        pin_match = re.search(
            r"Both production environments pin the custom backend image below:\s*"
            r"```text\s*\n(?P<image>[^\n]+)\n```",
            runtime,
        )
        if backend_image is not None:
            append_mismatch(
                errors,
                path,
                "backend image",
                backend_image,
                pin_match.group("image").strip() if pin_match else "missing",
            )

    try:
        integrations = markdown_section(
            document, r"### Backend Integrations and Services"
        )
        integration_rows = rows_by_key(
            markdown_table(
                integrations,
                ("Service or integration", "Mainnet", "Testnet", "Runtime path"),
            ),
            "Service or integration",
            "backend integration",
        )
        metadata_row = integration_rows.get("Metadata Service", {})
        metadata_actual = (
            f"Mainnet={metadata_row.get('Mainnet', 'missing')}, "
            f"Testnet={metadata_row.get('Testnet', 'missing')}"
        )
        append_mismatch(
            errors,
            path,
            "metadata documentation status",
            "Mainnet=Enabled, Testnet=Enabled",
            metadata_actual,
        )
    except StructureError as error:
        errors.append(
            diagnostic(path, "metadata documentation status", "Enabled", str(error))
        )

    try:
        disabled = markdown_section(
            document, r"## Deliberately Disabled or Blocked Features"
        )
        disabled_rows = rows_by_key(
            markdown_table(
                disabled, ("Feature", "Status", "Reason or prerequisite")
            ),
            "Feature",
            "disabled feature",
        )
        bens_actual = disabled_rows.get("BENS / name service", {}).get(
            "Status", "missing"
        )
        if bens_actual.lower() not in ("disabled", "not configured"):
            errors.append(
                diagnostic(
                    path,
                    "BENS documentation status",
                    "Disabled or Not configured",
                    bens_actual,
                )
            )
    except StructureError as error:
        errors.append(
            diagnostic(
                path,
                "BENS documentation status",
                "Disabled or Not configured",
                str(error),
            )
        )


def validate_changelog_document(
    document: str,
    path: Path,
    backend_image: str | None,
    frontend_version: str | None,
    errors: list[str],
) -> None:
    try:
        baseline = markdown_section(
            document,
            r"## \[[^]]+\] - Production Documentation and Runtime Baseline",
        )
    except StructureError as error:
        errors.append(
            diagnostic(path, "current production baseline", "labeled release section", str(error))
        )
        return

    version_match = re.search(
        r"^- Mainnet and Testnet run Frontend `(?P<frontend>[^`]+)` and "
        r"custom Backend `(?P<backend>[^`]+)` on GCP\.$",
        baseline,
        re.MULTILINE,
    )
    pin_match = re.search(
        r"^- Both production Compose files pin `(?P<backend>[^`]+)`\.$",
        baseline,
        re.MULTILINE,
    )
    status_match = re.search(
        r"^- Corrected feature status: the admin panel and BENS are "
        r"(?P<bens>enabled|disabled|not configured), while Metadata Service is "
        r"(?P<metadata>enabled|disabled)\.$",
        baseline,
        re.MULTILINE | re.IGNORECASE,
    )

    if frontend_version is not None:
        append_mismatch(
            errors,
            path,
            "frontend version",
            frontend_version,
            version_match.group("frontend") if version_match else "missing",
        )
    if backend_image is not None:
        append_mismatch(
            errors,
            path,
            "backend image",
            backend_image,
            pin_match.group("backend") if pin_match else "missing",
        )
        expected_backend_version = backend_runtime_version(backend_image)
        append_mismatch(
            errors,
            path,
            "backend version",
            expected_backend_version,
            version_match.group("backend") if version_match else "missing",
        )

    metadata_actual = (
        status_match.group("metadata").capitalize() if status_match else "missing"
    )
    append_mismatch(
        errors,
        path,
        "metadata documentation status",
        "Enabled",
        metadata_actual,
    )
    bens_actual = status_match.group("bens").capitalize() if status_match else "missing"
    if bens_actual.lower() not in ("disabled", "not configured"):
        errors.append(
            diagnostic(
                path,
                "BENS documentation status",
                "Disabled or Not configured",
                bens_actual,
            )
        )


def validate_architecture_document(
    document: str,
    path: Path,
    backend_image: str | None,
    frontend_image: str | None,
    workflow_env: dict[str, str],
    errors: list[str],
) -> None:
    try:
        deployed = markdown_section(document, r"## Deployed Environments")
        deployed_rows = rows_by_key(
            markdown_table(
                deployed,
                (
                    "Environment",
                    "Public origin",
                    "Chain ID",
                    "GCP host",
                    "Zone",
                    "Deployment path",
                ),
            ),
            "Environment",
            "deployed environment",
        )
    except StructureError as error:
        errors.append(
            diagnostic(path, "deployed environment structure", "supported table", str(error))
        )
    else:
        topology_fields = (
            ("Mainnet", "GCP host", "GCP_INSTANCE"),
            ("Mainnet", "Zone", "GCP_ZONE"),
            ("Testnet", "GCP host", "GCP_TESTNET_INSTANCE"),
            ("Testnet", "Zone", "GCP_TESTNET_ZONE"),
        )
        for environment, column, key in topology_fields:
            if key not in workflow_env:
                continue
            actual = deployed_rows.get(environment, {}).get(column, "missing")
            append_mismatch(errors, path, key, workflow_env[key], actual)

    try:
        runtime = markdown_section(document, r"## Runtime Versions")
        runtime_rows = rows_by_key(
            markdown_table(runtime, ("Component", "Production version")),
            "Component",
            "runtime version",
        )
    except StructureError as error:
        errors.append(diagnostic(path, "runtime version structure", "supported table", str(error)))
    else:
        if frontend_image is not None:
            append_mismatch(
                errors,
                path,
                "frontend image",
                frontend_image,
                runtime_rows.get("Frontend", {}).get("Production version", "missing"),
            )
        if backend_image is not None:
            append_mismatch(
                errors,
                path,
                "backend image",
                backend_image,
                runtime_rows.get("Backend", {}).get("Production version", "missing"),
            )

    try:
        metadata = markdown_section(document, r"### Metadata Service")
    except StructureError as error:
        errors.append(
            diagnostic(path, "metadata documentation status", "Enabled", str(error))
        )
        errors.append(
            diagnostic(
                path,
                "BENS documentation status",
                "Disabled or Not configured",
                str(error),
            )
        )
        return

    metadata_match = re.search(
        r"^\s*MICROSERVICE_METADATA_ENABLED\s*=\s*(?P<value>[^\n]+)$",
        metadata,
        re.MULTILINE,
    )
    try:
        metadata_actual = (
            parse_scalar(metadata_match.group("value")) if metadata_match else "missing"
        )
    except StructureError as error:
        metadata_actual = str(error)
    append_mismatch(
        errors,
        path,
        "metadata documentation status",
        "true",
        metadata_actual,
    )

    bens_match = re.search(
        r"\bBENS is (?P<status>not configured|disabled|enabled|configured)\.",
        metadata,
        re.IGNORECASE,
    )
    bens_actual = bens_match.group("status").capitalize() if bens_match else "missing"
    if bens_actual.lower() not in ("disabled", "not configured"):
        errors.append(
            diagnostic(
                path,
                "BENS documentation status",
                "Disabled or Not configured",
                bens_actual,
            )
        )


def local_env_reference(
    compose_path: str, reference: str
) -> tuple[str | None, bool]:
    expression = ENV_REFERENCE_RE.fullmatch(reference)
    unresolved = expression is not None or "$" in reference
    candidate = expression.group("default") if expression is not None else reference
    if not candidate or "$" in candidate or candidate.startswith(("/", "\\")):
        return None, unresolved or bool(candidate)
    compose_directory = Path(compose_path).parent
    relative = (compose_directory / Path(candidate)).as_posix()
    while relative.startswith("./"):
        relative = relative[2:]
    if relative == ".." or relative.startswith("../"):
        return None, True
    return relative, unresolved


def protected_invariant(key: str) -> str:
    if key == "MICROSERVICE_METADATA_ENABLED":
        return "metadata enabled"
    return f"BENS disabled ({key})"


def validate_protected_values(
    values: dict[str, str | None],
    path: Path,
    errors: list[str],
    require_metadata: bool,
) -> None:
    for key, expected in PROTECTED_BACKEND_ENV.items():
        actual = values.get(key)
        if actual is None and (not require_metadata or key != "MICROSERVICE_METADATA_ENABLED"):
            continue
        if actual != expected:
            errors.append(
                diagnostic(
                    path,
                    protected_invariant(key),
                    expected,
                    actual if actual is not None else "missing",
                )
            )


def validate_backend_sources(
    root: Path,
    compose_path: str,
    backend: dict[str, object],
    env_cache: dict[str, dict[str, str] | None],
    errors: list[str],
) -> None:
    unresolved_sources: list[str] = []
    for reference in backend["env_files"]:
        local_path, unresolved = local_env_reference(compose_path, reference)
        if unresolved:
            unresolved_sources.append(reference)
        if local_path is None or local_path == COMMON_BLOCKSCOUT_ENV:
            continue
        if local_path not in env_cache:
            try:
                env_cache[local_path] = read_env(root / local_path)
            except FileNotFoundError:
                env_cache[local_path] = None
                errors.append(
                    diagnostic(
                        Path(local_path), "missing required file", "present", "missing"
                    )
                )
            except StructureError as error:
                env_cache[local_path] = None
                errors.append(
                    diagnostic(Path(local_path), "env structure", "supported env", str(error))
                )
        values = env_cache.get(local_path)
        if values is not None:
            validate_protected_values(values, Path(local_path), errors, False)

    inline_environment = backend["environment"]
    validate_protected_values(
        inline_environment, Path(compose_path), errors, require_metadata=False
    )
    if unresolved_sources:
        for key, expected in PROTECTED_BACKEND_ENV.items():
            actual = inline_environment.get(key)
            if actual != expected:
                errors.append(
                    diagnostic(
                        Path(compose_path),
                        f"unresolved env source protection ({key})",
                        f"{key}={expected!r} pinned in backend environment",
                        f"{key}={actual!r}; sources={unresolved_sources!r}",
                    )
                )


def dependency_workflow_errors(text: str, path: Path) -> list[str]:
    errors: list[str] = []
    lines = yaml_lines(text)
    on_start, on_end = mapping_block(lines, "on", 0)
    push_start, push_end = mapping_block(lines, "push", 2, on_start, on_end)
    paths_start, paths_end = mapping_block(
        lines, "paths", 4, push_start, push_end
    )
    actual_paths: set[str] = set()
    for index in range(paths_start, paths_end):
        line_number, indent, content = lines[index]
        if indent != 6 or not content.startswith("- "):
            raise StructureError(f"unsupported push path at line {line_number}")
        actual_paths.add(parse_scalar(content[2:]))
    missing_paths = sorted(REQUIRED_DEPENDENCY_PUSH_PATHS - actual_paths)
    if missing_paths:
        errors.append(
            diagnostic(
                path,
                "required push paths",
                "complete guard source set",
                f"missing: {', '.join(missing_paths)}",
            )
        )

    jobs_start, jobs_end = mapping_block(lines, "jobs", 0)
    workflow_start, workflow_end = mapping_block(
        lines, "workflow-scripts", 2, jobs_start, jobs_end
    )
    job_properties = direct_mapping_children(
        lines,
        workflow_start,
        workflow_end,
        4,
        "workflow-scripts job property",
    )
    if "steps" not in job_properties:
        raise StructureError("missing workflow-scripts steps mapping")
    steps_value, steps_start, steps_end = job_properties["steps"]
    if steps_value:
        raise StructureError("unsupported inline workflow-scripts steps")

    def guard_control_reasons(
        properties: dict[str, tuple[str, int, int]], scope: str
    ) -> list[str]:
        reasons: list[str] = []
        controls = (("if", "true"), ("continue-on-error", "false"))
        for key, safe_value in controls:
            if key not in properties:
                continue
            value, child_start, child_end = properties[key]
            if child_start != child_end:
                raise StructureError(f"unsupported {scope} {key} structure")
            actual = parse_scalar(value).lower()
            if actual != safe_value:
                reasons.append(f"{scope} {key}: {actual or 'missing'}")
        return reasons

    job_reasons = guard_control_reasons(job_properties, "job")
    step_markers = [
        index
        for index in range(steps_start, steps_end)
        if lines[index][1] == 6
    ]
    for index in step_markers:
        if not lines[index][2].startswith("- "):
            raise StructureError(
                f"unsupported workflow step at line {lines[index][0]}"
            )

    active_command = False
    inactive_reasons: list[str] = []
    for marker_position, marker_index in enumerate(step_markers):
        step_end = steps_end
        if marker_position + 1 < len(step_markers):
            step_end = step_markers[marker_position + 1]
        inline_entry = split_yaml_mapping(lines[marker_index][2][2:].strip())
        if inline_entry is None:
            raise StructureError(
                f"unsupported workflow step at line {lines[marker_index][0]}"
            )
        step_properties = direct_mapping_children(
            lines,
            marker_index + 1,
            step_end,
            8,
            "workflow step property",
        )
        inline_key, inline_value = inline_entry
        if inline_key in step_properties:
            raise StructureError(f"duplicate workflow step property {inline_key!r}")
        step_properties[inline_key] = (
            inline_value,
            marker_index + 1,
            marker_index + 1,
        )
        if "run" not in step_properties:
            continue
        run_value, run_start, run_end = step_properties["run"]
        if run_value in ("|", ">", "|-", ">-"):
            block_commands = [
                lines[index][2].strip()
                for index in range(run_start, run_end)
                if lines[index][1] > 8
            ]
            runs_validator = VALIDATOR_COMMAND in block_commands
        else:
            if run_start != run_end:
                raise StructureError("unsupported validator run step structure")
            runs_validator = parse_scalar(run_value) == VALIDATOR_COMMAND
        if not runs_validator:
            continue
        step_reasons = guard_control_reasons(step_properties, "step")
        if not job_reasons and not step_reasons:
            active_command = True
            break
        inactive_reasons.extend(job_reasons + step_reasons)
    if not active_command:
        actual = ", ".join(dict.fromkeys(inactive_reasons)) or "missing"
        errors.append(
            diagnostic(path, "active validator run step", VALIDATOR_COMMAND, actual)
        )
    return errors


def validate_repository(root: Path) -> list[str]:
    errors: list[str] = []
    images: dict[str, dict[str, str]] = {"backend": {}, "frontend": {}}
    compose_services: dict[str, dict[str, dict[str, object]]] = {}
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
        try:
            services = parse_compose_services(compose)
        except StructureError as error:
            errors.append(
                diagnostic(
                    Path(compose_path),
                    "Compose structure",
                    "one supported top-level services mapping",
                    str(error),
                )
            )
            continue
        compose_services[compose_path] = services
        for service in images:
            image = services.get(service, {}).get("image")
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

    common_env_values: dict[str, str] | None = None
    try:
        common_env_values = read_env(root / COMMON_BLOCKSCOUT_ENV)
    except FileNotFoundError:
        errors.append(
            diagnostic(
                Path(COMMON_BLOCKSCOUT_ENV), "missing required file", "present", "missing"
            )
        )
    except StructureError as error:
        errors.append(
            diagnostic(
                Path(COMMON_BLOCKSCOUT_ENV), "env structure", "supported env", str(error)
            )
        )
    else:
        validate_protected_values(
            common_env_values,
            Path(COMMON_BLOCKSCOUT_ENV),
            errors,
            require_metadata=True,
        )

    env_cache: dict[str, dict[str, str] | None] = {
        COMMON_BLOCKSCOUT_ENV: common_env_values
    }
    for compose_path, services in compose_services.items():
        backend = services.get("backend")
        if backend is not None:
            validate_backend_sources(
                root, compose_path, backend, env_cache, errors
            )

    for frontend_env_file in FRONTEND_ENV_FILES:
        try:
            frontend_env = read_env(root / frontend_env_file)
        except FileNotFoundError:
            errors.append(
                diagnostic(
                    Path(frontend_env_file), "missing required file", "present", "missing"
                )
            )
            continue
        except StructureError as error:
            errors.append(
                diagnostic(
                    Path(frontend_env_file), "env structure", "supported env", str(error)
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

    workflow_env: dict[str, str] = {}
    try:
        workflow_text = read_required(root, DEPLOY_WORKFLOW)
    except FileNotFoundError:
        errors.append(
            diagnostic(Path(DEPLOY_WORKFLOW), "missing required file", "present", "missing")
        )
    else:
        try:
            workflow_env = read_workflow_env(workflow_text, GCP_KEYS)
        except StructureError as error:
            errors.append(
                diagnostic(
                    Path(DEPLOY_WORKFLOW),
                    "workflow structure",
                    "one supported top-level env mapping",
                    str(error),
                )
            )
        else:
            for key in GCP_KEYS:
                if not workflow_env.get(key):
                    errors.append(
                        diagnostic(
                            Path(DEPLOY_WORKFLOW),
                            key,
                            "defined workflow value",
                            "missing",
                        )
                    )

    for document_path in STATUS_DOCUMENTS:
        try:
            documents[document_path] = read_required(root, document_path)
        except FileNotFoundError:
            errors.append(
                diagnostic(
                    Path(document_path), "missing required file", "present", "missing"
                )
            )

    backend_image = canonical_images.get("backend")
    frontend_image = canonical_images.get("frontend")
    frontend_version = None
    if frontend_image is not None:
        parsed_frontend = parse_immutable_image(frontend_image)
        if parsed_frontend is not None:
            frontend_version = parsed_frontend["tag"]

    if FEATURES_DOCUMENT in documents:
        validate_features_document(
            documents[FEATURES_DOCUMENT],
            Path(FEATURES_DOCUMENT),
            backend_image,
            frontend_version,
            errors,
        )
    if CHANGELOG_DOCUMENT in documents:
        validate_changelog_document(
            documents[CHANGELOG_DOCUMENT],
            Path(CHANGELOG_DOCUMENT),
            backend_image,
            frontend_version,
            errors,
        )
    if ARCHITECTURE_DOCUMENT in documents:
        validate_architecture_document(
            documents[ARCHITECTURE_DOCUMENT],
            Path(ARCHITECTURE_DOCUMENT),
            backend_image,
            frontend_image,
            workflow_env,
            errors,
        )

    try:
        dependency_workflow = read_required(root, DEPENDENCY_WORKFLOW)
    except FileNotFoundError:
        errors.append(
            diagnostic(
                Path(DEPENDENCY_WORKFLOW), "missing required file", "present", "missing"
            )
        )
    else:
        try:
            errors.extend(
                dependency_workflow_errors(
                    dependency_workflow, Path(DEPENDENCY_WORKFLOW)
                )
            )
        except StructureError as error:
            errors.append(
                diagnostic(
                    Path(DEPENDENCY_WORKFLOW),
                    "workflow structure",
                    "supported workflow-scripts job and push paths",
                    str(error),
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
