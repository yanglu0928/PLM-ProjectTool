from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "docs/architecture/module-directory-manifest-v1.json"
ARCHITECTURE_PATH = REPO_ROOT / "docs/architecture/architecture-freeze-candidate-v1.md"
API_MANIFEST_PATH = (
    REPO_ROOT
    / "validation/api-05-contract-lint/generated/api-contract-manifest-v1.json"
)
EVIDENCE_PATH = (
    REPO_ROOT
    / "validation/wbs-1.01-module-layout/evidence/windows-11/result.json"
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_frozen_dependency_matrix(text: str) -> dict[str, list[str]]:
    marker = "## 允许依赖矩阵"
    if marker not in text:
        raise ValueError("Architecture dependency matrix heading is missing")
    section = text.split(marker, 1)[1].split("### 强制禁止", 1)[0]
    matrix: dict[str, list[str]] = {}
    for line in section.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 2 or cells[0] in {"来源模块", "---"}:
            continue
        source, raw_targets = cells
        if source == "developer_workbench":
            continue
        targets = [] if raw_targets == "无业务模块" else raw_targets.split("、")
        matrix[source] = targets
    return matrix


def assert_acyclic(graph: dict[str, list[str]]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise ValueError(f"Dependency cycle detected at {node}")
        if node in visited:
            return
        visiting.add(node)
        for target in graph[node]:
            visit(target)
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)


def validate() -> dict[str, Any]:
    manifest = load_json(MANIFEST_PATH)
    api_manifest = load_json(API_MANIFEST_PATH)
    runtime_modules = manifest["runtime_modules"]
    names = [item["name"] for item in runtime_modules]
    graph = {item["name"]: item["allowed_dependencies"] for item in runtime_modules}
    known = set(names)

    if len(names) != 22 or len(known) != 22:
        raise ValueError(f"Expected 22 unique runtime modules, got {len(known)}")

    api_owners = {root["owner"] for root in api_manifest["roots"]}
    if known != api_owners:
        raise ValueError(
            f"Runtime modules differ from API owners: missing={sorted(api_owners-known)}, "
            f"extra={sorted(known-api_owners)}"
        )
    if len(api_manifest["roots"]) != 65:
        raise ValueError("API manifest must contain 65 roots")

    for source, targets in graph.items():
        unknown = set(targets) - known
        if unknown:
            raise ValueError(f"{source} has unknown dependencies: {sorted(unknown)}")
        if source in targets:
            raise ValueError(f"{source} must not depend on itself")
    assert_acyclic(graph)

    frozen = parse_frozen_dependency_matrix(
        ARCHITECTURE_PATH.read_text(encoding="utf-8")
    )
    if graph != frozen:
        raise ValueError("Directory manifest dependencies differ from frozen Architecture")

    backend = manifest["backend"]
    expected_layers = {"api", "application", "domain", "infrastructure"}
    if set(backend["module_layers"]) != expected_layers:
        raise ValueError("Backend module layers are incomplete")
    layer_graph = backend["layer_dependencies"]
    if set(layer_graph) != expected_layers:
        raise ValueError("Layer dependency graph is incomplete")
    assert_acyclic(layer_graph)

    workbench = manifest["developer_workbench"]
    if (
        not workbench["separate_trust_zone"]
        or workbench["included_in_customer_runtime"]
        or workbench["allowed_runtime_dependencies"]
        or workbench["root"].startswith(backend["root"])
    ):
        raise ValueError("Developer Workbench trust-zone isolation is invalid")

    pattern = re.compile(manifest["naming"]["directory_pattern"])
    forbidden = set(manifest["naming"]["forbidden_windows_names"])
    for name in names:
        if not pattern.fullmatch(name) or name.casefold() in forbidden:
            raise ValueError(f"Invalid Windows-compatible module name: {name}")

    missing_paths = [
        value
        for value in manifest["required_tracked_paths"]
        if not (REPO_ROOT / Path(value)).is_file()
    ]
    if missing_paths:
        raise ValueError(f"Required tracked paths are missing: {missing_paths}")

    return {
        "status": "PASS",
        "standard_id": manifest["standard_id"],
        "wbs": manifest["wbs"],
        "runtime_module_count": len(names),
        "api_owner_count": len(api_owners),
        "aggregate_root_count": len(api_manifest["roots"]),
        "dependency_edge_count": sum(len(value) for value in graph.values()),
        "dependency_cycle_count": 0,
        "required_path_count": len(manifest["required_tracked_paths"]),
        "missing_path_count": 0,
        "developer_workbench_isolated": True,
        "external_call_count": 0,
        "runtime_code_created": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = validate()
    if args.write:
        EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
        EVIDENCE_PATH.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
