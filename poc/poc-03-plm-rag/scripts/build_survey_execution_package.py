from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any


WAVE_LABELS = {
    1: "第1批：资料较完整，直接核实关键差异",
    2: "第2批：已有真实调研，补齐正式范围与约束",
    3: "第3批：已有合同约束，先补真实业务调研",
    4: "第4批：以方案资料为主，先确认项目状态和范围",
}

PRIORITY_KEYWORDS = (
    "范围",
    "责任",
    "合同",
    "项目状态",
    "项目背景",
    "升级基线",
    "接口",
    "集成",
    "迁移",
    "环境",
    "权限",
    "审计",
    "合规",
    "验收",
    "切换",
    "上线",
)

MATERIAL_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("范围", "项目状态", "项目背景", "合同", "责任"), "项目章程/合同或技术协议、组织架构、范围清单、关键干系人名单"),
    (("接口", "集成", "取数"), "系统清单、现有接口文档、字段样例、调用频率与异常日志样例"),
    (("迁移", "数据", "编码", "BOM", "DBOM"), "主数据与历史数据样例、编码规则、数据量统计、质量问题清单"),
    (("权限", "保密", "审计", "合规"), "组织/用户/角色清单、权限制度、保密分级、审计与合规要求"),
    (("验收", "上线", "切换", "回归"), "现有验收标准、关键业务样例、环境清单、上线窗口与回退要求"),
    (("流程", "变更", "设变", "生命周期", "项目管理"), "现状流程图、业务表单、审批样例、状态与例外场景清单"),
    (("CAD", "CrownCAD", "PDM", "ECM", "SAP", "ERP", "OA", "WMS"), "系统版本、客户端/服务端环境、集成边界、典型数据样例"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a local PLM survey execution package")
    parser.add_argument("--analysis-package", type=Path, required=True)
    parser.add_argument("--confirmation", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def project_wave(project: dict[str, Any]) -> int:
    has_survey = bool(project.get("has_actual_survey"))
    has_contract = bool(project.get("has_contract_or_tech"))
    source_count = int(project.get("source_count") or 0)
    if has_survey and has_contract:
        return 1
    if has_contract and source_count >= 5:
        return 1
    if has_survey:
        return 2
    if has_contract:
        return 3
    return 4


def task_priority(topic: str, wave: int) -> str:
    if any(keyword in topic for keyword in PRIORITY_KEYWORDS):
        return "P0"
    if wave >= 3 and any(keyword in topic for keyword in ("现状", "业务", "对象", "主线")):
        return "P0"
    return "P1"


def required_materials(topic: str) -> str:
    matches = [text for keywords, text in MATERIAL_RULES if any(key in topic for key in keywords)]
    if not matches:
        return "对应业务流程、表单/模板、典型业务样例、当前问题与期望结果"
    deduped: list[str] = []
    for match in matches:
        if match not in deduped:
            deduped.append(match)
    return "；".join(deduped)


def terms(value: str) -> set[str]:
    parts = re.split(r"[/、，,与及和\s]+", value)
    return {part for part in parts if len(part) >= 2}


def related_items(outline: dict[str, Any], items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = [item for item in items if item["project_id"] == outline["project_id"]]
    topic_terms = terms(outline["topic"])
    category_weight = {"待确认项": 6, "差异项": 4, "非标功能": 2, "标准功能": 0}

    def score(item: dict[str, Any]) -> tuple[int, str]:
        haystack = " ".join(
            str(item.get(key) or "") for key in ("domain", "title", "basis", "action")
        )
        overlap = sum(5 for term in topic_terms if term in haystack)
        return overlap + category_weight.get(item.get("category"), 0), item["item_id"]

    return sorted(candidates, key=score, reverse=True)[:2]


def source_maturity(project: dict[str, Any]) -> str:
    wave = project_wave(project)
    return {
        1: "较完整",
        2: "有真实调研，缺正式范围约束",
        3: "有合同约束，缺真实调研",
        4: "初步，需先核实项目状态",
    }[wave]


def first_action(wave: int) -> str:
    return {
        1: "先核实 P0 任务和高风险非标/差异，再确认实施边界。",
        2: "先确认范围、责任人与合同/技术约束，再补齐差异验证。",
        3: "先访谈业务负责人形成现状主线，再验证合同范围。",
        4: "先确认项目是否仍有效、当前阶段、目标与范围，再进入专题调研。",
    }[wave]


def build_package(analysis: dict[str, Any], confirmation: dict[str, Any]) -> dict[str, Any]:
    if confirmation.get("analysis_fingerprint") != analysis.get("fingerprint"):
        raise ValueError("Confirmation fingerprint does not match the analysis package")
    if confirmation.get("decision") != "APPROVED":
        raise ValueError("Analysis package has not been approved")

    project_rows: list[dict[str, Any]] = []
    task_rows: list[dict[str, Any]] = []
    for project in analysis["projects"]:
        wave = project_wave(project)
        outlines = [row for row in analysis["survey_outline"] if row["project_id"] == project["project_id"]]
        prepared: list[dict[str, Any]] = []
        for outline in outlines:
            linked = related_items(outline, analysis["items"])
            priority = task_priority(outline["topic"], wave)
            prepared.append(
                {
                    "task_id": outline["outline_id"],
                    "project_id": outline["project_id"],
                    "project_name": outline["project_name"],
                    "wave": wave,
                    "wave_label": WAVE_LABELS[wave],
                    "priority": priority,
                    "topic": outline["topic"],
                    "reason": outline["why"],
                    "participants": outline["participants"],
                    "required_materials": required_materials(outline["topic"]),
                    "questions": outline["questions"],
                    "expected_output": outline["expected_output"],
                    "acceptance_criteria": (
                        f"形成《{outline['expected_output']}》；关键边界、规则和责任人明确；"
                        "未决事项进入“决策追踪”并指定责任人和期限。"
                    ),
                    "related_item_ids": [item["item_id"] for item in linked],
                    "evidence_link": linked[0]["evidence_link"] if linked else "evidence-navigator.html",
                    "owner": "",
                    "planned_date": None,
                    "status": "未安排",
                    "notes": "",
                }
            )
        task_rows.extend(prepared)
        project_rows.append(
            {
                "project_id": project["project_id"],
                "project_name": project["project_name"],
                "wave": wave,
                "wave_label": WAVE_LABELS[wave],
                "source_maturity": source_maturity(project),
                "source_count": project["source_count"],
                "task_count": len(prepared),
                "p0_count": sum(row["priority"] == "P0" for row in prepared),
                "pending_decision_count": int(project["category_counts"].get("待确认项", 0)),
                "first_action": first_action(wave),
                "owner": "",
                "planned_start": None,
                "planned_end": None,
                "status": "未安排",
                "notes": "",
            }
        )

    project_rows.sort(key=lambda row: (row["wave"], -row["source_count"], row["project_id"]))
    order = {row["project_id"]: index for index, row in enumerate(project_rows, start=1)}
    for row in project_rows:
        row["recommended_order"] = order[row["project_id"]]
    task_rows.sort(key=lambda row: (order[row["project_id"]], row["priority"] != "P0", row["task_id"]))

    decision_rows = []
    for item in analysis["items"]:
        if item["category"] != "待确认项":
            continue
        decision_rows.append(
            {
                "decision_id": f"DEC-{item['item_id']}",
                "project_id": item["project_id"],
                "project_name": item["project_name"],
                "topic": item["title"],
                "question": item["basis"],
                "recommendation": item["action"],
                "evidence_link": item["evidence_link"],
                "owner": "",
                "due_date": None,
                "decision": "",
                "status": "待决策",
                "notes": "",
            }
        )
    decision_rows.sort(key=lambda row: (order[row["project_id"]], row["decision_id"]))

    package = {
        "schema_version": "1.0",
        "package_id": "PLM-SURVEY-EXECUTION-R2",
        "version": "R2",
        "generated_at": confirmation["confirmed_at"],
        "status": "READY_FOR_SCHEDULING",
        "source_analysis": {
            "package_id": analysis["package_id"],
            "version": analysis["version"],
            "fingerprint": analysis["fingerprint"],
            "confirmation_id": confirmation["confirmation_id"],
        },
        "scope_note": (
            "R1 已确认为项目分析基线。本执行包用于组织调研与决策跟踪；"
            "不等同于正式需求、方案或独立留出集数据外发授权。"
        ),
        "projects": project_rows,
        "tasks": task_rows,
        "decisions": decision_rows,
        "fingerprint": "",
    }
    digest = json.dumps(package, ensure_ascii=False, sort_keys=True).encode("utf-8")
    package["fingerprint"] = hashlib.sha256(digest).hexdigest()
    return package


def main() -> int:
    args = parse_args()
    analysis_path = args.analysis_package.resolve()
    confirmation_path = args.confirmation.resolve()
    output_dir = args.output_dir.resolve()
    analysis = load_json(analysis_path)
    confirmation = load_json(confirmation_path)
    package = build_package(analysis, confirmation)

    output_dir.mkdir(parents=True, exist_ok=True)
    package_path = output_dir / "survey-execution-package.json"
    package_path.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    evidence_source = analysis_path.parent / "evidence-navigator.html"
    if evidence_source.is_file():
        shutil.copy2(evidence_source, output_dir / "evidence-navigator.html")
    print(
        json.dumps(
            {
                "status": package["status"],
                "project_count": len(package["projects"]),
                "task_count": len(package["tasks"]),
                "p0_count": sum(row["priority"] == "P0" for row in package["tasks"]),
                "decision_count": len(package["decisions"]),
                "output": str(package_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
