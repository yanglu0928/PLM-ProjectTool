from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


WAVE_ORDER = {
    "W0": 0,
    "W1": 1,
    "W2": 2,
    "W3": 3,
    "W4": 4,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build internal project delivery package")
    parser.add_argument("--requirement-package", type=Path, required=True)
    parser.add_argument("--solution-package", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--generated-at", required=True)
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def delivery_wave(requirement: dict[str, Any], solution: dict[str, Any]) -> tuple[str, str]:
    if requirement["category"] == "待确认项":
        return "W0", "范围与决策收敛"
    if requirement["category"] == "标准功能":
        return "W1", "标准能力配置"
    if requirement["category"] == "差异项":
        return "W2", "差异验证与治理"
    if solution["layer"] in {"integration", "data", "security", "domain"}:
        return "W3", "非标与专项实现"
    return "W3", "专项实现"


def entry_condition(requirement: dict[str, Any], solution: dict[str, Any]) -> str:
    if requirement["category"] == "待确认项":
        return "责任方形成唯一书面结论，并明确范围、生效版本和排除项。"
    if solution["layer"] == "integration":
        return "接口文档、认证方式、字段样例、频率和错误码齐备；高风险接口先完成只读验证。"
    if solution["layer"] == "data":
        return "完成对象盘点、质量分析、映射规则、样例数据和回退方案。"
    if solution["layer"] == "security":
        return "完成角色、资源、项目、状态和字段级权限矩阵。"
    return "内部需求评审稿范围稳定，验收样例和责任人明确。"


def completion_evidence(requirement: dict[str, Any], solution: dict[str, Any]) -> str:
    if requirement["category"] == "待确认项":
        return "正式确认记录、影响分析、适用版本和 TraceLink。"
    if solution["layer"] == "integration":
        return "接口契约、字段映射、联调记录、失败恢复测试和审计记录。"
    if solution["layer"] == "data":
        return "迁移批次、数量与 Hash 对账、失败清单、重跑记录和抽样打开记录。"
    if solution["layer"] == "security":
        return "Role × Resource × Project 用例、拒绝用例、导出脱敏和审计证据。"
    return "配置记录、正常与边界用例、评审记录和可定位证据。"


def specialty_type(solution: dict[str, Any], solution_package: dict[str, Any]) -> list[str]:
    types: list[str] = []
    if solution["solution_id"] in solution_package["interface_specs"]:
        types.append("InterfaceSpec")
    if solution["solution_id"] in solution_package["migration_specs"]:
        types.append("MigrationSpec")
    if solution["solution_id"] in solution_package["permission_designs"]:
        types.append("PermissionDesign")
    return types


def survey_outline(project_id: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    categories = {
        category: [row["requirement_title"] for row in rows if row["category"] == category]
        for category in ("标准功能", "非标功能", "差异项", "待确认项")
    }
    topics = [
        ("01", "范围与责任", categories["待确认项"], "确认一期范围、责任方、明确排除和正式决策路径。", "范围边界与正式确认清单"),
        ("02", "标准业务与对象", categories["标准功能"], "核对对象、生命周期、流程、模板、角色和标准配置边界。", "标准配置清单与验收样例"),
        ("03", "非标与接口", categories["非标功能"], "拆分二开、接口方向、字段、认证、频率、异常和维护责任。", "非标范围与 InterfaceSpec 输入"),
        ("04", "差异与治理", categories["差异项"], "明确现状与目标差异，优先用配置、流程和数据治理收敛。", "差异处置结论与例外清单"),
        ("05", "数据、权限与迁移", [row["requirement_title"] for row in rows if row["layer"] in {"data", "security"}], "确认数据责任、质量、迁移批次、权限矩阵和审计要求。", "MigrationSpec 与 PermissionDesign 输入"),
        ("06", "验收、部署与运维", [row["requirement_title"] for row in rows if row["priority"] == "P0"], "把关键需求转为可重复的验收、部署、培训、交付和运维场景。", "验收计划与交付责任矩阵"),
    ]
    output: list[dict[str, Any]] = []
    for sequence, topic, inputs, objective, deliverable in topics:
        output.append(
            {
                "outline_id": f"SURV-{project_id}-{sequence}",
                "project_id": project_id,
                "sequence": int(sequence),
                "topic": topic,
                "focus_items": "；".join(inputs) if inputs else "按项目实际资料补充，不预设结论。",
                "objective": objective,
                "expected_output": deliverable,
                "status": "RECOMMENDED_INTERNAL",
            }
        )
    return output


def build_package(
    requirement_package: dict[str, Any],
    solution_package: dict[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    if requirement_package.get("version") != "R4" or not requirement_package.get("fingerprint"):
        raise ValueError("Requirement source must be a fingerprinted R4 package")
    if solution_package.get("version") != "R5" or not solution_package.get("fingerprint"):
        raise ValueError("Solution source must be a fingerprinted R5 package")
    if solution_package.get("source_fingerprint") != requirement_package["fingerprint"]:
        raise ValueError("R5 solution package is not bound to the supplied R4 requirement package")

    requirements = requirement_package["requirements"]
    solutions = solution_package["solutions"]
    if any(row.get("formal_status") != "NOT_FORMAL_REQUIREMENT" for row in requirements):
        raise ValueError("Delivery package accepts only non-formal requirement drafts")
    if any(row.get("formal_status") != "NOT_FORMAL_SOLUTION" for row in solutions):
        raise ValueError("Delivery package accepts only non-formal solution drafts")

    requirement_ids = [row["candidate_id"] for row in requirements]
    solution_requirement_ids = [row["requirement_id"] for row in solutions]
    if len(requirement_ids) != len(set(requirement_ids)):
        raise ValueError("Requirement IDs must be unique")
    if len(solution_requirement_ids) != len(set(solution_requirement_ids)):
        raise ValueError("Each requirement must have exactly one solution")
    if set(requirement_ids) != set(solution_requirement_ids):
        raise ValueError("R4 and R5 requirement coverage must match exactly")

    solution_index = {row["requirement_id"]: row for row in solutions}
    decision_index = {row["decision_id"]: row for row in requirement_package["decisions"]}
    delivery_items: list[dict[str, Any]] = []
    specialty_items: list[dict[str, Any]] = []
    formalization_items: list[dict[str, Any]] = []

    for requirement in requirements:
        solution = solution_index[requirement["candidate_id"]]
        wave_code, wave_name = delivery_wave(requirement, solution)
        types = specialty_type(solution, solution_package)
        delivery = {
            "delivery_id": requirement["candidate_id"].replace("REQC-", "DLV-"),
            "project_id": requirement["project_id"],
            "project_name": requirement["project_name"],
            "requirement_id": requirement["candidate_id"],
            "solution_id": solution["solution_id"],
            "priority": requirement["review_priority"],
            "risk": requirement["risk"],
            "category": requirement["category"],
            "domain": requirement["domain"],
            "requirement_title": requirement["title"],
            "requirement_statement": requirement["statement"],
            "capability_match": requirement["capability_match"],
            "build_mode": solution["build_mode"],
            "layer": solution["layer"],
            "solution_name": solution["solution_name"],
            "solution_outline": solution["solution_outline"],
            "component": solution["component"],
            "specialty_types": types,
            "delivery_wave": wave_code,
            "delivery_wave_name": wave_name,
            "entry_condition": entry_condition(requirement, solution),
            "acceptance_plan": solution["acceptance_plan"],
            "completion_evidence": completion_evidence(requirement, solution),
            "explicit_exclusion": solution["explicit_exclusion"],
            "dependency": solution["dependency"],
            "decision_trace": solution["decision_trace"],
            "evidence_link": solution["evidence_link"],
            "requirement_status": requirement["formal_status"],
            "solution_status": solution["formal_status"],
            "delivery_status": "INTERNAL_DELIVERY_DRAFT",
        }
        delivery_items.append(delivery)

        for specialty in types:
            content = {
                "InterfaceSpec": solution["interface_spec"],
                "MigrationSpec": solution["migration_spec"],
                "PermissionDesign": solution["permission_design"],
            }[specialty]
            specialty_items.append(
                {
                    "specialty_id": f"{specialty.upper()}-{solution['solution_id']}",
                    "project_id": solution["project_id"],
                    "project_name": solution["project_name"],
                    "requirement_id": requirement["candidate_id"],
                    "solution_id": solution["solution_id"],
                    "type": specialty,
                    "title": requirement["title"],
                    "design": content,
                    "entry_condition": delivery["entry_condition"],
                    "acceptance": delivery["acceptance_plan"],
                    "evidence_link": delivery["evidence_link"],
                    "status": "SPECIALTY_DRAFT_INTERNAL",
                }
            )

        if requirement.get("resolution_id"):
            decision = decision_index[requirement["resolution_id"]]
            formalization_items.append(
                {
                    "decision_id": decision["decision_id"],
                    "project_id": decision["project_id"],
                    "project_name": decision["project_name"],
                    "requirement_id": requirement["candidate_id"],
                    "solution_id": solution["solution_id"],
                    "issue": decision["issue"],
                    "working_baseline": decision["recommended_decision"],
                    "included_scope": decision["included_scope"],
                    "explicit_exclusion": decision["explicit_exclusion"],
                    "acceptance_basis": decision["acceptance_basis"],
                    "risk": decision["risk"],
                    "evidence_link": decision["evidence_link"],
                    "current_status": decision["status"],
                    "formalization_status": "AWAITING_FORMAL_REVIEW",
                    "formalization_action": "责任方书面确认后，按 Review Engine 升版并建立正式 Requirement/Solution TraceLink。",
                }
            )

    delivery_items.sort(key=lambda row: (row["project_id"], WAVE_ORDER[row["delivery_wave"]], row["requirement_id"]))

    project_summaries: list[dict[str, Any]] = []
    survey_items: list[dict[str, Any]] = []
    for project in requirement_package["projects"]:
        rows = [row for row in delivery_items if row["project_id"] == project["project_id"]]
        project_summaries.append(
            {
                "project_id": project["project_id"],
                "project_name": project["project_name"],
                "requirement_count": len(rows),
                "standard_count": sum(row["category"] == "标准功能" for row in rows),
                "custom_count": sum(row["category"] == "非标功能" for row in rows),
                "difference_count": sum(row["category"] == "差异项" for row in rows),
                "formalization_count": sum(row["category"] == "待确认项" for row in rows),
                "p0_count": sum(row["priority"] == "P0" for row in rows),
                "high_risk_count": sum(row["risk"] == "高" for row in rows),
                "specialty_count": sum(len(row["specialty_types"]) for row in rows),
                "internal_readiness": "INTERNAL_DELIVERY_READY",
                "formal_readiness": "BLOCKED_BY_PHASE0_AND_REVIEW_GATES",
                "recommended_next": "先完成工作基线正式化，再按 W1-W4 形成项目实施与验收基线。",
            }
        )
        survey_items.extend(survey_outline(project["project_id"], rows))

    package = {
        "schema_version": "1.0",
        "package_id": "PLM-INTERNAL-REQUIREMENT-SOLUTION-DELIVERY-R6",
        "version": "R6",
        "generated_at": generated_at,
        "status": "INTERNAL_DELIVERY_PACKAGE_READY",
        "requirement_source": {
            "package_id": requirement_package["package_id"],
            "fingerprint": requirement_package["fingerprint"],
        },
        "solution_source": {
            "package_id": solution_package["package_id"],
            "fingerprint": solution_package["fingerprint"],
        },
        "boundaries": [
            "本包是内部交付草案，不创建正式 Requirement、Solution、InterfaceSpec、MigrationSpec 或 PermissionDesign。",
            "10 条 AI 代决策仅为工作基线，必须经责任方书面确认和 Review Engine 才能正式化。",
            "Phase 0、Architecture Freeze、Data Model Freeze 和 API Contract Freeze 均不得被本包绕过。",
            "本轮只做本地确定性整合，不调用外部模型，不扩大客户数据外发范围。",
        ],
        "delivery_sequence": [
            {"code": "W0", "name": "范围与决策收敛"},
            {"code": "W1", "name": "标准能力配置"},
            {"code": "W2", "name": "差异验证与治理"},
            {"code": "W3", "name": "非标与专项实现"},
            {"code": "W4", "name": "验收、交接与正式化"},
        ],
        "projects": project_summaries,
        "delivery_items": delivery_items,
        "specialty_items": specialty_items,
        "formalization_items": formalization_items,
        "survey_outline": survey_items,
        "fingerprint": "",
    }
    digest = json.dumps(package, ensure_ascii=False, sort_keys=True).encode("utf-8")
    package["fingerprint"] = hashlib.sha256(digest).hexdigest()
    return package


def main() -> int:
    args = parse_args()
    requirement_path = args.requirement_package.resolve()
    solution_path = args.solution_package.resolve()
    package = build_package(load_json(requirement_path), load_json(solution_path), args.generated_at)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "internal-requirement-solution-delivery-package.json"
    output_path.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    evidence_source = requirement_path.parent / "evidence-navigator.html"
    if evidence_source.is_file():
        shutil.copy2(evidence_source, output_dir / "evidence-navigator.html")
    print(
        json.dumps(
            {
                "status": package["status"],
                "project_count": len(package["projects"]),
                "delivery_item_count": len(package["delivery_items"]),
                "specialty_count": len(package["specialty_items"]),
                "formalization_count": len(package["formalization_items"]),
                "survey_outline_count": len(package["survey_outline"]),
                "output": str(output_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
