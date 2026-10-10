from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


EVIDENCE_RANK = {
    "ACTUAL_SURVEY": 4,
    "CONTRACT": 3,
    "TECHNICAL_AGREEMENT": 3,
    "RISK_ASSESSMENT": 2,
    "SOLUTION": 1,
}

REQUIREMENT_KIND = {
    "标准功能": "标准功能候选",
    "非标功能": "非标功能候选",
    "差异项": "差异处理候选",
    "待确认项": "需求前置决策",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build desktop-discovery results and requirement candidates"
    )
    parser.add_argument("--analysis-package", type=Path, required=True)
    parser.add_argument("--execution-package", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--generated-at", required=True)
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def evidence_type(items: list[dict[str, Any]]) -> str:
    types = [
        item.get("project_evidence", {}).get("source_type", "")
        for item in items
        if item.get("project_evidence")
    ]
    if not types:
        return "NO_DIRECT_EVIDENCE"
    return max(types, key=lambda value: EVIDENCE_RANK.get(value, 0))


def evidence_level(source_type: str) -> tuple[str, str, str]:
    if source_type == "ACTUAL_SURVEY":
        return (
            "既有实际调研记录",
            "较高",
            "结论来自既有面对面调研记录，但不是本轮新增客户确认；变更与例外仍需需求评审。",
        )
    if source_type in {"CONTRACT", "TECHNICAL_AGREEMENT"}:
        return (
            "合同/技术约束",
            "中",
            "可确认交付边界和责任约束；具体业务操作仍按资料推定，正式需求前需项目负责人确认。",
        )
    if source_type in {"RISK_ASSESSMENT", "SOLUTION"}:
        return (
            "方案/风险材料推断",
            "低",
            "缺少实际调研记录，本结论只能作为工作假设，不能描述为客户已确认事实。",
        )
    return (
        "无直接证据的工作假设",
        "低",
        "现有资料不足。仅生成下一环节占位项，并保留为前置决策。",
    )


def compact_join(values: list[str], limit: int = 420) -> str:
    result: list[str] = []
    for value in values:
        value = " ".join(str(value or "").split())
        if value and value not in result:
            result.append(value)
    text = "；".join(result)
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def requirement_statement(item: dict[str, Any]) -> str:
    title = item["title"]
    if item["category"] == "标准功能":
        return f"在本项目约定范围内配置并启用“{title}”。"
    if item["category"] == "非标功能":
        return f"评估并实现“{title}”，明确二开或接口边界、维护责任和验收样例。"
    if item["category"] == "差异项":
        return f"针对“{title}”确定配置、流程调整或非标实现方案，并记录例外。"
    return f"在形成正式需求前完成决策：“{title}”。"


def acceptance_draft(item: dict[str, Any]) -> str:
    if item["category"] == "待确认项":
        return "责任人给出唯一书面结论，影响范围和生效版本明确，结论可追溯后再转为正式需求。"
    action = str(item["action"]).rstrip("。；;")
    return (
        f"完成建议动作：{action}；使用可追溯样例验证“{item['title']}”；"
        "范围、责任人和例外已记录。"
    )


def candidate_status(item: dict[str, Any]) -> str:
    if item["category"] == "待确认项":
        return "BLOCKED_BY_DECISION"
    source_type = item.get("project_evidence", {}).get("source_type", "")
    if source_type in {"ACTUAL_SURVEY", "CONTRACT", "TECHNICAL_AGREEMENT"}:
        return "DRAFT_READY"
    return "DRAFT_WITH_ASSUMPTION"


def build_package(
    analysis: dict[str, Any], execution: dict[str, Any], generated_at: str
) -> dict[str, Any]:
    source_analysis = execution.get("source_analysis", {})
    if source_analysis.get("fingerprint") != analysis.get("fingerprint"):
        raise ValueError("Execution package does not reference the supplied analysis package")

    first_batch_projects = [row for row in execution["projects"] if row["wave"] == 1]
    project_ids = {row["project_id"] for row in first_batch_projects}
    if not project_ids:
        raise ValueError("Execution package has no first-batch projects")
    item_index = {item["item_id"]: item for item in analysis["items"]}

    discovery_results: list[dict[str, Any]] = []
    for task in execution["tasks"]:
        if task["project_id"] not in project_ids:
            continue
        linked = [item_index[item_id] for item_id in task["related_item_ids"] if item_id in item_index]
        primary = linked[:1]
        source_type = evidence_type(primary)
        level, confidence, limitation = evidence_level(source_type)
        conclusion = compact_join(
            [
                f"现有资料支持：{item['title']}。建议动作：{item['action']}"
                for item in primary
            ]
        )
        if not conclusion:
            conclusion = f"现有资料不足以回答“{task['topic']}”，暂作为需求前置决策。"
        discovery_results.append(
            {
                "result_id": f"DSR-{task['task_id']}",
                "task_id": task["task_id"],
                "project_id": task["project_id"],
                "project_name": task["project_name"],
                "priority": task["priority"],
                "topic": task["topic"],
                "result": conclusion,
                "evidence_level": level,
                "confidence": confidence,
                "limitation": limitation,
                "expected_output": task["expected_output"],
                "related_item_ids": task["related_item_ids"],
                "evidence_link": task["evidence_link"],
                "next_stage": "已转需求候选/前置决策",
                "review_status": "桌面调研草案",
            }
        )

    requirements: list[dict[str, Any]] = []
    assumptions: list[dict[str, Any]] = []
    for item in analysis["items"]:
        if item["project_id"] not in project_ids:
            continue
        status = candidate_status(item)
        requirement = {
            "candidate_id": f"REQC-{item['item_id']}",
            "project_id": item["project_id"],
            "project_name": item["project_name"],
            "kind": REQUIREMENT_KIND[item["category"]],
            "category": item["category"],
            "domain": item["domain"],
            "title": item["title"],
            "statement": requirement_statement(item),
            "acceptance_draft": acceptance_draft(item),
            "implementation_note": item["action"],
            "capability_match": (
                "标准能力已有直接对照"
                if item.get("standard_evidence")
                else "未定位到标准能力直接对照"
            ),
            "confidence": item["confidence"],
            "trace_source": item["item_id"],
            "evidence_link": item["evidence_link"],
            "status": status,
            "review_decision": "待需求评审",
            "review_notes": "",
        }
        requirements.append(requirement)
        if item["category"] == "待确认项":
            assumptions.append(
                {
                    "assumption_id": f"ASM-{item['item_id']}",
                    "project_id": item["project_id"],
                    "project_name": item["project_name"],
                    "issue": item["title"],
                    "basis": item["basis"],
                    "working_assumption": (
                        f"暂按“{item['action']}”作为需求分析工作假设，不作为客户最终结论。"
                    ),
                    "impact": "未确认前不得冻结相关需求、接口、范围或验收规则。",
                    "evidence_link": item["evidence_link"],
                    "status": "OPEN_WORKING_ASSUMPTION",
                }
            )

    project_summaries = []
    for project in first_batch_projects:
        project_requirements = [
            row for row in requirements if row["project_id"] == project["project_id"]
        ]
        ready = [row for row in project_requirements if row["status"] == "DRAFT_READY"]
        assumed = [
            row for row in project_requirements if row["status"] == "DRAFT_WITH_ASSUMPTION"
        ]
        blocked = [
            row for row in project_requirements if row["status"] == "BLOCKED_BY_DECISION"
        ]
        project_summaries.append(
            {
                "project_id": project["project_id"],
                "project_name": project["project_name"],
                "source_maturity": project["source_maturity"],
                "discovery_result_count": sum(
                    row["project_id"] == project["project_id"] for row in discovery_results
                ),
                "requirement_count": len(project_requirements),
                "draft_ready_count": len(ready),
                "assumption_count": len(assumed),
                "blocked_count": len(blocked),
                "summary": compact_join(
                    [
                        "标准基线："
                        + "、".join(
                            row["title"] for row in project_requirements if row["category"] == "标准功能"
                        ),
                        "非标重点："
                        + "、".join(
                            row["title"] for row in project_requirements if row["category"] == "非标功能"
                        ),
                        "差异处理："
                        + "、".join(
                            row["title"] for row in project_requirements if row["category"] == "差异项"
                        ),
                    ],
                    limit=520,
                ),
                "next_action": "进入需求候选评审；前置决策保持打开，不阻止其余候选继续分析。",
                "status": "REQUIREMENT_CANDIDATES_READY",
            }
        )

    package = {
        "schema_version": "1.0",
        "package_id": "PLM-DESKTOP-DISCOVERY-REQUIREMENTS-R3",
        "version": "R3",
        "generated_at": generated_at,
        "status": "REQUIREMENT_CANDIDATES_READY",
        "mode": "DESKTOP_DISCOVERY_NO_NEW_INTERVIEW",
        "source_analysis_fingerprint": analysis["fingerprint"],
        "source_execution_fingerprint": execution["fingerprint"],
        "scope": "第一批项目（Wave 1）",
        "boundaries": [
            "结果仅基于已有调研、合同/技术协议、风险评估、方案和标准能力资料",
            "未安排新的客户访谈，不得把资料推断描述为新增客户确认",
            "需求条目均为候选，不是正式 Requirement，不进入需求冻结",
            "待确认项转为工作假设和前置决策，不自动关闭",
            "本轮不调用任何外部模型，也不构成独立留出集数据外发授权",
        ],
        "projects": project_summaries,
        "discovery_results": discovery_results,
        "requirements": requirements,
        "assumptions": assumptions,
        "fingerprint": "",
    }
    digest = json.dumps(package, ensure_ascii=False, sort_keys=True).encode("utf-8")
    package["fingerprint"] = hashlib.sha256(digest).hexdigest()
    return package


def main() -> int:
    args = parse_args()
    analysis_path = args.analysis_package.resolve()
    execution_path = args.execution_package.resolve()
    analysis = load_json(analysis_path)
    execution = load_json(execution_path)
    package = build_package(analysis, execution, args.generated_at)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "desktop-discovery-requirements-package.json"
    output_path.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    evidence_source = analysis_path.parent / "evidence-navigator.html"
    if evidence_source.is_file():
        shutil.copy2(evidence_source, output_dir / "evidence-navigator.html")
    print(
        json.dumps(
            {
                "status": package["status"],
                "project_count": len(package["projects"]),
                "discovery_result_count": len(package["discovery_results"]),
                "requirement_count": len(package["requirements"]),
                "assumption_count": len(package["assumptions"]),
                "output": str(output_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
