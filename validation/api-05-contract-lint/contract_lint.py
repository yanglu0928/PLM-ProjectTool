from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Iterable


CONTRACT_VERSION = "API-CONTRACT-CANDIDATE-V1"
VALIDATION_ONLY = True
SOURCE_DOCS = (
    "docs/api-contract/api-01-resource-common-protocol-v1-candidate.md",
    "docs/api-contract/api-02-platform-security-document-governance-v1-candidate.md",
    "docs/api-contract/api-03-ai-rag-job-plugin-output-v1-candidate.md",
    "docs/api-contract/api-04-implementation-business-chain-v1-candidate.md",
)
EXPECTED_OPERATION_COUNTS = {
    SOURCE_DOCS[1]: 86,
    SOURCE_DOCS[2]: 79,
    SOURCE_DOCS[3]: 158,
}
EXPECTED_ROOT_COUNT = 65
EXPECTED_OWNER_COUNT = 22
EXPECTED_ERROR_COUNT = 150
EXPECTED_SSE_EVENT_COUNT = 18
EXPECTED_QUERY_COUNT = 20
ALLOWED_CONTROLS = frozenset("SLCIMEA")
NON_IDEMPOTENT_POST_EXCEPTIONS = frozenset({"AUTH_LOGIN", "AUTH_SESSION_RENEW"})

SCOPE_ALIASES = {
    "{scope_base}": ("/api/v1/projects/{project_id}", "/api/v1/global"),
    "{solution_scope}": ("/api/v1/projects/{project_id}", "/api/v1/global"),
    "{plan_scope}": ("/api/v1/projects/{project_id}", "/api/v1/global"),
}

QUERY_OPERATION_MAP = {
    "Q-AUTH-01": ("AUTH_LOGIN",),
    "Q-PRJ-01": ("PROJECT_LIST",),
    "Q-PRJ-02": ("PROJECT_MEMBER_LIST", "PROJECT_DEPARTMENT_LIST"),
    "Q-WFL-01": ("WORKFLOW_GET", "WORKFLOW_TRANSITION_LIST"),
    "Q-VER-01": (
        "DOCUMENT_VERSION_LIST",
        "CAP_VERSION_LIST",
        "HND_VERSION_LIST",
        "SURVEY_VERSION_LIST",
        "REQ_VERSION_LIST",
        "PRT_VERSION_LIST",
        "SOL_OUTLINE_VERSION_LIST",
        "SOL_SECTION_VERSION_LIST",
        "PLAN_VERSION_LIST",
    ),
    "Q-RVW-01": ("REVIEW_LIST", "REVIEW_GET"),
    "Q-DOC-01": ("DOCUMENT_VERSION_GET", "DOCUMENT_PARSE_LIST"),
    "Q-EVD-01": ("EVIDENCE_LIST", "EVIDENCE_GET"),
    "Q-TRC-01": ("TRACE_GRAPH_UPSTREAM", "TRACE_GRAPH_DOWNSTREAM"),
    "Q-AUD-01": ("AUDIT_PROJECT_LIST", "AUDIT_ADMIN_LIST"),
    "Q-JOB-01": ("JOB_ADMIN_LIST",),
    "Q-JOB-02": ("INTERNAL_PORT:JobService.recover_expired_leases",),
    "Q-OUT-01": ("INTERNAL_PORT:OutboxDispatcher.claim_due",),
    "Q-RET-01": ("INTERNAL_PORT:RetentionService.list_due_candidates",),
    "Q-RAG-01": ("RAG_RETRIEVAL_CREATE", "RAG_RETRIEVAL_RESULT_GET"),
    "Q-RAG-02": ("RAG_RETRIEVAL_CREATE", "RAG_RETRIEVAL_RESULT_GET"),
    "Q-REQ-01": ("REQ_RELATION_LIST",),
    "Q-WBS-01": ("PLAN_VERSION_WBS_LIST", "PLAN_VERSION_GET"),
    "Q-PLG-01": ("INTERNAL_PORT:PluginService.invoke", "PLUGIN_INSTALLATION_LIST"),
    "Q-OUTPUT-01": ("OUTPUT_REQUEST_LIST", "OUTPUT_ARTIFACT_LIST"),
}

ENUM_CATALOG = {
    "Scope": ("DEPLOYMENT", "GLOBAL", "PROJECT", "GLOBAL_OR_PROJECT"),
    "ProjectRole": (
        "DEPLOYMENT_ADMIN",
        "PROJECT_MANAGER",
        "IMPLEMENTATION_MEMBER",
        "CUSTOMER_MANAGER",
        "CUSTOMER_MEMBER",
        "SYSTEM_ACTOR",
    ),
    "Exposure": ("DIRECT", "NESTED", "READ_ONLY", "INTERNAL"),
    "VersionState": ("DRAFT", "IN_REVIEW", "APPROVED", "RETURNED", "SUPERSEDED", "RESTRICTED"),
    "ReviewDecision": ("APPROVE", "RETURN"),
    "FactStatus": ("NOT_FORMAL_FACT",),
    "EvidencePurpose": ("SUPPORTS", "CONTRADICTS", "DERIVED_FROM", "REFERENCE_ONLY"),
    "JobState": ("PENDING", "RUNNING", "RETRY_WAIT", "SUCCEEDED", "FAILED", "CANCEL_REQUESTED", "CANCELLED"),
    "RequirementClassification": (
        "STANDARD_FUNCTION",
        "NONSTANDARD_FUNCTION",
        "DIFFERENCE",
        "PENDING_CONFIRMATION",
    ),
    "CapabilityMatch": ("DIRECT", "PARTIAL", "NONE", "UNKNOWN"),
    "HandoverItemType": ("GAP", "MISSING", "CONFLICT", "RISK", "SCOPE", "NEED_CONFIRM"),
    "ActionItemState": ("OPEN", "IN_PROGRESS", "SUBMITTED", "VERIFIED", "CLOSED", "CANCELLED"),
    "SurveyRoundState": ("PLANNED", "OPEN", "CLOSED", "CANCELLED"),
    "SurveyAssignmentState": ("ASSIGNED", "IN_PROGRESS", "SUBMITTED", "VALIDATED", "RETURNED"),
    "PrototypeState": ("ACTIVE", "NOT_REQUIRED", "ARCHIVED", "RESTRICTED"),
    "ReferenceEligibility": ("REFERENCE_ONLY", "ELIGIBLE", "RESTRICTED", "REVOKED"),
    "StructuredSpecType": ("PROCESS_MODEL", "INTERFACE_SPEC", "MIGRATION_SPEC", "PERMISSION_DESIGN"),
    "WbsDependencyType": ("FS",),
}


@dataclass(frozen=True)
class Operation:
    operation_id: str
    method: str
    declared_paths: tuple[str, ...]
    expanded_paths: tuple[str, ...]
    roles: str
    controls_text: str
    controls: tuple[str, ...]
    result: str
    source: str


@dataclass(frozen=True)
class RootExposure:
    root_id: str
    owner: str
    exposure: str
    api_family: str


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def read_sources(root: Path) -> dict[str, str]:
    return {name: (root / name).read_text(encoding="utf-8") for name in SOURCE_DOCS}


def section(text: str, start: str, end: str | None) -> str:
    if start not in text:
        return ""
    value = text.split(start, 1)[1]
    return value.split(end, 1)[0] if end and end in value else value


def extract_controls(value: str) -> tuple[str, ...]:
    found = re.findall(r"(?<![A-Za-z])([SLCIMEA])(?![A-Za-z])", value)
    return tuple(sorted(set(found), key="SLCIMEA".index))


def expand_paths(paths: Iterable[str]) -> tuple[str, ...]:
    expanded: list[str] = []
    for path in paths:
        alias = next((item for item in SCOPE_ALIASES if path.startswith(item)), None)
        if alias:
            suffix = path[len(alias):]
            expanded.extend(base + suffix for base in SCOPE_ALIASES[alias])
        else:
            expanded.append(path)
    return tuple(expanded)


def parse_operations(sources: dict[str, str]) -> list[Operation]:
    operations: list[Operation] = []
    row = re.compile(r"^\|([A-Z][A-Z0-9_]+)\|(GET|POST|PATCH|PUT) (.+?)\|([^|]+)\|([^|]+)\|([^|]+)\|$")
    for name in SOURCE_DOCS[1:]:
        for line in sources[name].splitlines():
            match = row.match(line)
            if not match:
                continue
            operation_id, method, path_cell, roles, controls_text, result = match.groups()
            declared_paths = tuple(re.findall(r"`([^`]+)`", path_cell))
            if not declared_paths:
                raise AssertionError(f"{operation_id} has no declared path")
            operations.append(
                Operation(
                    operation_id=operation_id,
                    method=method,
                    declared_paths=declared_paths,
                    expanded_paths=expand_paths(declared_paths),
                    roles=roles.strip(),
                    controls_text=controls_text.strip(),
                    controls=extract_controls(controls_text),
                    result=result.strip(),
                    source=name,
                )
            )
    return operations


def parse_root_exposure(api01: str) -> list[RootExposure]:
    body = section(api01, "## 65 Root → API 资源目录", "## API-02～API-05 输入清单")
    roots: list[RootExposure] = []
    for line in body.splitlines():
        if not line.startswith("|"):
            continue
        cells = line.strip("|").split("|")
        if len(cells) != 4:
            continue
        root_ids = re.findall(r"[A-Z]{2,3}-\d{2}", cells[1])
        if not root_ids:
            continue
        owner_match = re.match(r"([a-z_]+)", cells[0])
        if not owner_match:
            raise AssertionError(f"Cannot parse owner from: {line}")
        exposures = [item.strip() for item in cells[2].split("/")]
        if len(exposures) == 1:
            exposures *= len(root_ids)
        elif len(exposures) < len(root_ids):
            exposures.extend([exposures[-1]] * (len(root_ids) - len(exposures)))
        if len(exposures) != len(root_ids):
            raise AssertionError(f"Exposure count mismatch: {line}")
        for root_id, exposure in zip(root_ids, exposures, strict=True):
            roots.append(RootExposure(root_id, owner_match.group(1), exposure, cells[0].strip()))
    return roots


def parse_schema_root_ids(root: Path) -> set[str]:
    value = (root / "validation/sc-04-database-schema/schema_manifest.py").read_text(encoding="utf-8")
    return set(re.findall(r'RootSpec\("([A-Z]{2,3}-\d{2})"', value))


def parse_schema_query_ids(root: Path) -> set[str]:
    value = (root / "validation/sc-04-database-schema/schema_manifest.py").read_text(encoding="utf-8")
    return set(re.findall(r'"(Q-[A-Z]+-\d{2})"', value))


def parse_errors(sources: dict[str, str]) -> dict[str, dict[str, object]]:
    occurrences: dict[str, list[dict[str, object]]] = defaultdict(list)
    sections = {
        SOURCE_DOCS[0]: section(sources[SOURCE_DOCS[0]], "## HTTP 状态与通用错误", "## Trace 与请求上下文"),
        SOURCE_DOCS[1]: section(sources[SOURCE_DOCS[1]], "## 错误码目录", "## 强制 Audit 动作"),
        SOURCE_DOCS[2]: section(sources[SOURCE_DOCS[2]], "## 错误码目录", "## 强制 Audit 动作"),
        SOURCE_DOCS[3]: section(sources[SOURCE_DOCS[3]], "## 错误码目录", "## 强制 Audit 动作"),
    }
    for source, body in sections.items():
        for line in body.splitlines():
            if not line.startswith("|"):
                continue
            cells = line.strip("|").split("|")
            if len(cells) != 3:
                continue
            if re.fullmatch(r"\d{3}", cells[0]):
                status, code_cell, meaning = cells
            elif re.fullmatch(r"\d{3}", cells[1]):
                code_cell, status, meaning = cells
            else:
                continue
            for code in re.findall(r"`([A-Z][A-Z0-9_]+)`", code_cell):
                if code.endswith("_"):
                    continue
                occurrences[code].append({"http": int(status), "source": source, "meaning": meaning})
    catalog: dict[str, dict[str, object]] = {}
    for code, items in sorted(occurrences.items()):
        statuses = {item["http"] for item in items}
        if len(statuses) != 1:
            raise AssertionError(f"Conflicting HTTP status for {code}: {statuses}")
        catalog[code] = {
            "http": next(iter(statuses)),
            "sources": sorted({str(item["source"]) for item in items}),
            "meaning": items[-1]["meaning"],
        }
    return catalog


def parse_sse_events(sources: dict[str, str]) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    for source in SOURCE_DOCS[1:]:
        body = section(sources[source], "## SSE Event Contract", "## 错误码目录")
        for line in body.splitlines():
            cells = line.strip("|").split("|") if line.startswith("|") else []
            if len(cells) not in {2, 3}:
                continue
            event_match = re.fullmatch(r"`([a-z][a-z0-9.-]+)`", cells[0])
            if not event_match:
                continue
            trigger, payload = ("resource state change", cells[1]) if len(cells) == 2 else (cells[1], cells[2])
            events.append({"event_type": event_match.group(1), "trigger": trigger, "payload": payload, "source": source})
    return events


def source_hashes(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for name in SOURCE_DOCS:
        result[name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
    return result


def validate(root: Path) -> dict[str, object]:
    sources = read_sources(root)
    operations = parse_operations(sources)
    roots = parse_root_exposure(sources[SOURCE_DOCS[0]])
    errors = parse_errors(sources)
    events = parse_sse_events(sources)

    operation_ids = [item.operation_id for item in operations]
    if len(operation_ids) != len(set(operation_ids)):
        raise AssertionError("Operation IDs must be unique across API-02..04")
    by_source = Counter(item.source for item in operations)
    if dict(by_source) != EXPECTED_OPERATION_COUNTS:
        raise AssertionError(f"Operation count drift: {dict(by_source)}")

    method_paths: list[tuple[str, str]] = []
    for operation in operations:
        if not operation.roles or not operation.result:
            raise AssertionError(f"{operation.operation_id} lacks role or result")
        if not set(operation.controls).issubset(ALLOWED_CONTROLS):
            raise AssertionError(f"{operation.operation_id} has unknown control")
        if operation.method in {"POST", "PATCH", "PUT"} and operation.operation_id != "AUTH_LOGIN" and "C" not in operation.controls:
            raise AssertionError(f"{operation.operation_id} lacks CSRF control")
        if operation.method == "PATCH" and "M" not in operation.controls:
            raise AssertionError(f"{operation.operation_id} lacks If-Match control")
        if operation.method == "POST" and operation.operation_id not in NON_IDEMPOTENT_POST_EXCEPTIONS and "I" not in operation.controls:
            raise AssertionError(f"{operation.operation_id} lacks idempotency control")
        if operation.method == "GET" and "C" in operation.controls:
            raise AssertionError(f"{operation.operation_id} makes GET stateful")
        for path in operation.expanded_paths:
            if path.startswith("/api/v1/projects/") and "{project_id}" not in path:
                raise AssertionError(f"{operation.operation_id} project path lacks project_id")
            method_paths.append((operation.method, path))
    duplicates = [item for item, count in Counter(method_paths).items() if count > 1]
    if duplicates:
        raise AssertionError(f"Duplicate method/path variants: {duplicates}")
    if any("DELETE `" in value for value in sources.values()):
        raise AssertionError("V1 must not expose generic DELETE")

    root_ids = [item.root_id for item in roots]
    owners = {item.owner for item in roots}
    schema_roots = parse_schema_root_ids(root)
    if len(root_ids) != EXPECTED_ROOT_COUNT or len(set(root_ids)) != EXPECTED_ROOT_COUNT:
        raise AssertionError("API resource catalog must contain 65 unique Roots")
    if len(owners) != EXPECTED_OWNER_COUNT:
        raise AssertionError("API resource catalog must contain 22 Owners")
    if set(root_ids) != schema_roots:
        raise AssertionError("API and Schema Root catalogs differ")
    if any(item.exposure not in ENUM_CATALOG["Exposure"] for item in roots):
        raise AssertionError("Unknown Root exposure")

    if len(errors) != EXPECTED_ERROR_COUNT:
        raise AssertionError(f"Expected {EXPECTED_ERROR_COUNT} unique error codes, got {len(errors)}")
    event_types = [item["event_type"] for item in events]
    if len(event_types) != EXPECTED_SSE_EVENT_COUNT or len(set(event_types)) != EXPECTED_SSE_EVENT_COUNT:
        raise AssertionError("SSE event catalog must contain 18 unique event types")

    query_ids = parse_schema_query_ids(root)
    if query_ids != set(QUERY_OPERATION_MAP) or len(query_ids) != EXPECTED_QUERY_COUNT:
        raise AssertionError("Schema Query ID and API mapping catalogs differ")
    operation_set = set(operation_ids)
    for query_id, targets in QUERY_OPERATION_MAP.items():
        if not targets:
            raise AssertionError(f"{query_id} has no API/Application mapping")
        for target in targets:
            if not target.startswith("INTERNAL_PORT:") and target not in operation_set:
                raise AssertionError(f"{query_id} references missing operation {target}")

    for enum_name, values in ENUM_CATALOG.items():
        if not values or len(values) != len(set(values)):
            raise AssertionError(f"Enum {enum_name} is empty or duplicated")
        if any(not re.fullmatch(r"[A-Z][A-Z0-9_]*", item) for item in values):
            raise AssertionError(f"Enum {enum_name} has a non-canonical value")

    exposure_counts = Counter(item.exposure for item in roots)
    egress_operations = {
        item.operation_id for item in operations if "E" in item.controls
    }
    expected_egress = {
        "AI_TASK_CREATE",
        "AI_TASK_RETRY",
        "RAG_INDEX_BUILD",
        "RAG_INDEX_REBUILD",
        "RAG_RETRIEVAL_CREATE",
    }
    if egress_operations != expected_egress:
        raise AssertionError(f"Egress operation drift: {sorted(egress_operations)}")

    return {
        "status": "PASS",
        "contract_version": CONTRACT_VERSION,
        "validation_only": VALIDATION_ONLY,
        "owner_count": len(owners),
        "root_count": len(root_ids),
        "root_exposure_counts": dict(sorted(exposure_counts.items())),
        "operation_count": len(operation_ids),
        "operation_path_variant_count": len(method_paths),
        "error_code_count": len(errors),
        "sse_event_count": len(events),
        "query_mapping_count": len(QUERY_OPERATION_MAP),
        "enum_family_count": len(ENUM_CATALOG),
        "egress_operation_count": len(egress_operations),
        "generic_delete_count": 0,
        "external_call_count": 0,
        "source_hashes": source_hashes(root),
    }


def build_manifest(root: Path) -> dict[str, object]:
    sources = read_sources(root)
    operations = parse_operations(sources)
    return {
        "contract_version": CONTRACT_VERSION,
        "status": "CANDIDATE_NOT_GATE_2_FROZEN",
        "validation_only": VALIDATION_ONLY,
        "source_hashes": source_hashes(root),
        "roots": [asdict(item) for item in parse_root_exposure(sources[SOURCE_DOCS[0]])],
        "operations": [asdict(item) for item in operations],
        "errors": parse_errors(sources),
        "sse_events": parse_sse_events(sources),
        "query_operation_map": {key: list(value) for key, value in QUERY_OPERATION_MAP.items()},
        "enum_catalog": {key: list(value) for key, value in ENUM_CATALOG.items()},
    }


def write_outputs(root: Path) -> dict[str, object]:
    result = validate(root)
    base = root / "validation/api-05-contract-lint"
    generated = base / "generated"
    evidence = base / "evidence/windows-11"
    generated.mkdir(parents=True, exist_ok=True)
    evidence.mkdir(parents=True, exist_ok=True)
    (generated / "api-contract-manifest-v1.json").write_text(
        json.dumps(build_manifest(root), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (evidence / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate API Contract V1 candidate sources")
    parser.add_argument("--write", action="store_true", help="write manifest and evidence JSON")
    args = parser.parse_args()
    root = repo_root()
    result = write_outputs(root) if args.write else validate(root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
