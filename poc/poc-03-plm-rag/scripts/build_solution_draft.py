from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


DECISION_ARCHETYPES = {
    "ENGINEERING_SOFTWARE_COMPATIBILITY": (
        "COMPATIBILITY_MATRIX_AND_ADAPTER",
        "兼容性矩阵与可配置适配",
        "integration",
    ),
    "PHASED_SCOPE": ("PHASED_ROLLOUT_CONTROL", "分期范围与发布控制", "governance"),
    "PROJECT_PRODUCT_QUOTATION_MODEL": (
        "DOMAIN_OBJECT_MODEL",
        "项目、产品、报价单与版本对象模型",
        "domain",
    ),
    "QUOTATION_TEST_SAMPLES": ("ACCEPTANCE_DATASET", "报价验收数据集", "quality"),
    "MASTER_DATA_OWNERSHIP": (
        "MASTER_DATA_OWNERSHIP_AND_SYNC",
        "主数据责任与同步控制",
        "integration",
    ),
    "DOCUMENT_MIGRATION_AND_PUBLISH": (
        "MIGRATION_AND_PUBLISH_PIPELINE",
        "文档迁移与受控发布链路",
        "data",
    ),
    "CONTROLLED_BUSINESS_DEFINITION": (
        "CONTROLLED_RULE_DICTIONARY",
        "受控业务规则字典",
        "domain",
    ),
    "UNKNOWN_EXTERNAL_INTEGRATION": (
        "READ_ONLY_INTEGRATION_SPIKE",
        "外部系统只读接口验证",
        "integration",
    ),
    "CONTRACT_PRECEDENCE": (
        "CONTRACT_TRACE_MATRIX",
        "合同条款、功能与责任追溯矩阵",
        "governance",
    ),
    "CUSTOM_DELIVERY_RESPONSIBILITY": (
        "DELIVERY_AND_MAINTENANCE_PACKAGE",
        "二开交付与维护责任包",
        "governance",
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build internal solution draft package")
    parser.add_argument("--review-package", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--generated-at", required=True)
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def standard_component(domain: str) -> str:
    if "权限" in domain:
        return "auth + project + workflow"
    if any(word in domain for word in ("文档", "图文档", "分发")):
        return "document + workflow + trace"
    if any(word in domain for word in ("项目", "计划")):
        return "project + plan + workflow"
    return "capability + document + workflow + trace"


def solution_strategy(requirement: dict[str, Any], decision: dict[str, Any] | None) -> dict[str, str]:
    if decision:
        archetype, name, layer = DECISION_ARCHETYPES.get(
            decision["profile"],
            ("CONTROLLED_SCOPE_BASELINE", "受控范围工作基线", "governance"),
        )
        return {
            "archetype": archetype,
            "solution_name": name,
            "layer": layer,
            "build_mode": "工作基线 + 配置/专项设计",
            "component": "trace + review + 对应业务模块",
        }

    category = requirement["category"]
    domain_title = f"{requirement['domain']} {requirement['title']}"
    if category == "标准功能":
        return {
            "archetype": "STANDARD_CONFIGURATION",
            "solution_name": "标准能力配置与流程启用",
            "layer": "standard",
            "build_mode": "标准配置",
            "component": standard_component(requirement["domain"]),
        }
    if category == "非标功能":
        if any(word in domain_title for word in ("接口", "集成", "同步", "ERP", "SAP", "PDM", "ECM", "Meego", "CAD")):
            return {
                "archetype": "INTEGRATION_ADAPTER",
                "solution_name": "受控接口适配与失败恢复",
                "layer": "integration",
                "build_mode": "非标接口",
                "component": "integration adapter + plugin host + audit",
            }
        if "迁移" in domain_title:
            return {
                "archetype": "DATA_MIGRATION_PIPELINE",
                "solution_name": "可校验、可重跑的数据迁移链路",
                "layer": "data",
                "build_mode": "非标迁移",
                "component": "document + metadata + migration job + audit",
            }
        if any(word in domain_title for word in ("权限", "保密")):
            return {
                "archetype": "SECURITY_EXTENSION",
                "solution_name": "字段级授权与脱敏扩展",
                "layer": "security",
                "build_mode": "非标扩展",
                "component": "auth + project authorization + audit",
            }
        return {
            "archetype": "DOMAIN_EXTENSION",
            "solution_name": "领域规则扩展与版本化计算",
            "layer": "domain",
            "build_mode": "非标扩展",
            "component": "domain service + workflow + trace",
        }
    if category == "差异项":
        if any(word in domain_title for word in ("兼容", "客户端", "Office", "CAD")):
            return {
                "archetype": "COMPATIBILITY_CONTROL",
                "solution_name": "兼容矩阵、受控降级与替代路径",
                "layer": "integration",
                "build_mode": "差异适配",
                "component": "client compatibility + document parser + audit",
            }
        if any(word in domain_title for word in ("数据", "编码", "版本", "成本")):
            return {
                "archetype": "DATA_AND_RULE_GOVERNANCE",
                "solution_name": "数据规则治理与版本控制",
                "layer": "data",
                "build_mode": "差异治理",
                "component": "metadata + domain rule + trace + review",
            }
        return {
            "archetype": "CONTROLLED_PROCESS_EXTENSION",
            "solution_name": "受控流程扩展与例外管理",
            "layer": "domain",
            "build_mode": "流程差异处理",
            "component": "workflow + review + trace",
        }
    return {
        "archetype": "CONTROLLED_SCOPE_BASELINE",
        "solution_name": "受控范围工作基线",
        "layer": "governance",
        "build_mode": "工作基线",
        "component": "trace + review",
    }


def interface_spec(requirement: dict[str, Any], strategy: dict[str, str]) -> str:
    if strategy["layer"] != "integration":
        return "不单独创建接口；通过模块内部 Application Service 和 TraceLink 关联。"
    return (
        "通过独立适配层定义认证、对象标识、字段映射、幂等键、错误码、超时、重试和审计；"
        "业务模块不得直连外部系统或管理外部凭据。"
    )


def migration_spec(requirement: dict[str, Any], strategy: dict[str, str]) -> str:
    if strategy["layer"] != "data" and "迁移" not in requirement["title"]:
        return "无独立迁移批次；只处理本需求产生的版本化业务数据。"
    return (
        "按盘点、清洗、映射、试迁移、校验、正式迁移和差异复核执行；每批保存 Hash、来源、版本、"
        "成功/失败清单和可重跑标识。"
    )


def permission_design(requirement: dict[str, Any], strategy: dict[str, str]) -> str:
    if strategy["layer"] == "security" or "权限" in f"{requirement['domain']} {requirement['title']}":
        return "按 ProjectId、角色、对象状态和受控字段授权；默认拒绝，查询、导出、接口和审计使用同一权限口径。"
    return "沿用项目级授权与角色权限；方案不得绕过统一 auth、project authorization 和 audit。"


def acceptance_plan(requirement: dict[str, Any], strategy: dict[str, str]) -> str:
    base = requirement.get("acceptance_draft", "")
    if strategy["layer"] == "integration":
        extra = "补充正常、重复、超时、限流、无效响应和重试后恢复场景。"
    elif strategy["layer"] == "data":
        extra = "补充数量、Hash、版本、权限、失败重跑和抽样打开校验。"
    elif strategy["layer"] == "security":
        extra = "补充授权、拒绝、跨项目访问、导出脱敏和审计完整性测试。"
    else:
        extra = "补充正常、边界、退回、升版和历史追溯场景。"
    return f"{base} {extra}".strip()


def build_package(review: dict[str, Any], generated_at: str) -> dict[str, Any]:
    if review.get("version") != "R4" or not review.get("fingerprint"):
        raise ValueError("Source must be a fingerprinted R4 requirement review package")
    if any(row.get("formal_status") != "NOT_FORMAL_REQUIREMENT" for row in review["requirements"]):
        raise ValueError("R5 accepts only non-formal requirement drafts")

    decision_index = {row["decision_id"]: row for row in review["decisions"]}
    solutions: list[dict[str, Any]] = []
    for requirement in review["requirements"]:
        decision = decision_index.get(requirement.get("resolution_id", ""))
        strategy = solution_strategy(requirement, decision)
        solution_id = requirement["candidate_id"].replace("REQC-", "SOLD-")
        solution = {
            "solution_id": solution_id,
            "project_id": requirement["project_id"],
            "project_name": requirement["project_name"],
            "requirement_id": requirement["candidate_id"],
            "requirement_title": requirement["title"],
            "requirement_category": requirement["category"],
            "priority": requirement["review_priority"],
            "risk": requirement["risk"],
            "archetype": strategy["archetype"],
            "solution_name": strategy["solution_name"],
            "layer": strategy["layer"],
            "build_mode": strategy["build_mode"],
            "component": strategy["component"],
            "solution_outline": (
                f"以“{requirement['statement']}”为目标，复用 {strategy['component']}；"
                f"采用{strategy['solution_name']}，保留版本、证据、评审和审计链路。"
            ),
            "interface_spec": interface_spec(requirement, strategy),
            "migration_spec": migration_spec(requirement, strategy),
            "permission_design": permission_design(requirement, strategy),
            "acceptance_plan": acceptance_plan(requirement, strategy),
            "explicit_exclusion": (
                decision["explicit_exclusion"]
                if decision
                else "未在需求与验收标准中明确的自动化、实时性、性能和第三方能力不自动纳入。"
            ),
            "dependency": (
                decision["included_scope"]
                if decision
                else requirement.get("decision_basis", "按现有证据和范围继续设计。")
            ),
            "requirement_trace": requirement["candidate_id"],
            "decision_trace": requirement.get("resolution_id", ""),
            "evidence_link": requirement["evidence_link"],
            "status": "SOLUTION_DRAFT_INTERNAL",
            "formal_status": "NOT_FORMAL_SOLUTION",
            "draft_version": "DRAFT-R5",
        }
        solutions.append(solution)

    project_summaries: list[dict[str, Any]] = []
    for project in review["projects"]:
        rows = [row for row in solutions if row["project_id"] == project["project_id"]]
        project_summaries.append(
            {
                "project_id": project["project_id"],
                "project_name": project["project_name"],
                "solution_count": len(rows),
                "standard_count": sum(row["build_mode"] == "标准配置" for row in rows),
                "custom_count": sum("非标" in row["build_mode"] for row in rows),
                "integration_count": sum(row["layer"] == "integration" for row in rows),
                "data_count": sum(row["layer"] == "data" for row in rows),
                "governance_count": sum(row["layer"] == "governance" for row in rows),
                "p0_count": sum(row["priority"] == "P0" for row in rows),
                "high_risk_count": sum(row["risk"] == "高" for row in rows),
                "status": "SOLUTION_DRAFT_READY",
                "next_action": "整理项目级需求与方案交付包；正式化继续受 Phase 0 和 Review Gate 约束。",
            }
        )

    interfaces = [row for row in solutions if row["layer"] == "integration"]
    migrations = [row for row in solutions if row["layer"] == "data" or "迁移" in row["requirement_title"]]
    permissions = [
        row
        for row in solutions
        if row["layer"] == "security" or "权限" in f"{row['requirement_title']}"
    ]
    package = {
        "schema_version": "1.0",
        "package_id": "PLM-INTERNAL-SOLUTION-DRAFT-R5",
        "version": "R5",
        "generated_at": generated_at,
        "status": "INTERNAL_SOLUTION_DRAFT_READY",
        "source_package_id": review["package_id"],
        "source_fingerprint": review["fingerprint"],
        "boundaries": [
            "每条内部需求评审稿对应一个内部解决方案草案",
            "方案草案不得自动升级为正式 Solution 或 SolutionSection",
            "正式方案需要 Requirement Review、Solution Review 和对应 Gate",
            "本轮不调用外部模型，不构成客户数据外发授权",
        ],
        "projects": project_summaries,
        "solutions": solutions,
        "interface_specs": [row["solution_id"] for row in interfaces],
        "migration_specs": [row["solution_id"] for row in migrations],
        "permission_designs": [row["solution_id"] for row in permissions],
        "fingerprint": "",
    }
    digest = json.dumps(package, ensure_ascii=False, sort_keys=True).encode("utf-8")
    package["fingerprint"] = hashlib.sha256(digest).hexdigest()
    return package


def main() -> int:
    args = parse_args()
    source_path = args.review_package.resolve()
    package = build_package(load_json(source_path), args.generated_at)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "internal-solution-draft-package.json"
    output_path.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    evidence_source = source_path.parent / "evidence-navigator.html"
    if evidence_source.is_file():
        shutil.copy2(evidence_source, output_dir / "evidence-navigator.html")
    print(
        json.dumps(
            {
                "status": package["status"],
                "project_count": len(package["projects"]),
                "solution_count": len(package["solutions"]),
                "interface_count": len(package["interface_specs"]),
                "migration_count": len(package["migration_specs"]),
                "permission_count": len(package["permission_designs"]),
                "output": str(output_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
