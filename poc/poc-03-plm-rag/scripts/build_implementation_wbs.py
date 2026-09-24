from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "poc-03.implementation-wbs.v1"


def _owner_role(item: dict[str, Any]) -> str:
    specialty_types = set(item.get("specialty_types") or [])
    layer = str(item.get("layer") or "")
    if "MigrationRunbook" in specialty_types or "DataMapping" in specialty_types:
        return "数据工程师"
    if "InterfaceSpec" in specialty_types or layer == "integration":
        return "集成工程师"
    if "PermissionMatrix" in specialty_types or layer == "security":
        return "安全/权限负责人"
    if item.get("category") == "标准功能":
        return "PLM顾问"
    if item.get("category") == "待确认项":
        return "项目负责人"
    return "业务顾问"


def _task_from_delivery(item: dict[str, Any], setup_id: str) -> dict[str, Any]:
    wave = str(item["delivery_wave"])
    task_id = f"WBS-{item['project_id']}-{item['delivery_id'].split('-')[-1]}"
    dependency = setup_id
    if wave == "W0":
        dependency = setup_id
    return {
        "task_id": task_id,
        "project_id": item["project_id"],
        "project_name": item["project_name"],
        "wave": wave,
        "wave_name": item["delivery_wave_name"],
        "task_type": "需求交付任务",
        "task_name": item["requirement_title"],
        "category": item["category"],
        "priority": item["priority"],
        "risk": item["risk"],
        "owner_role": _owner_role(item),
        "support_roles": "测试负责人；项目负责人",
        "predecessors": [dependency],
        "entry_condition": item["entry_condition"],
        "work_output": item["solution_name"],
        "acceptance": item["acceptance_plan"],
        "evidence": item["completion_evidence"],
        "explicit_exclusion": item["explicit_exclusion"],
        "requirement_id": item["requirement_id"],
        "solution_id": item["solution_id"],
        "delivery_id": item["delivery_id"],
        "specialty_types": item.get("specialty_types") or [],
        "trace_link": item["evidence_link"],
        "status": "DRAFT_NOT_SCHEDULED",
        "gate": "内部工作草案；待 Phase 0 与正式评审 Gate",
    }


def build_wbs(source: dict[str, Any], generated_at: str) -> dict[str, Any]:
    tasks: list[dict[str, Any]] = []
    project_summaries: list[dict[str, Any]] = []
    delivery_items = list(source["delivery_items"])

    for project in source["projects"]:
        project_id = str(project["project_id"])
        project_items = [row for row in delivery_items if row["project_id"] == project_id]
        setup_id = f"WBS-{project_id}-000"
        integration_id = f"WBS-{project_id}-090"
        acceptance_id = f"WBS-{project_id}-100"
        handover_id = f"WBS-{project_id}-110"

        tasks.append(
            {
                "task_id": setup_id,
                "project_id": project_id,
                "project_name": project["project_name"],
                "wave": "W0",
                "wave_name": "范围与决策收敛",
                "task_type": "项目控制任务",
                "task_name": "建立实施工作基线与评审入口",
                "category": "项目治理",
                "priority": "P0",
                "risk": "中",
                "owner_role": "项目负责人",
                "support_roles": "业务顾问；PLM顾问；测试负责人",
                "predecessors": [],
                "entry_condition": "内部需求与解决方案交付包可追溯。",
                "work_output": "范围清单、决策清单、评审计划和版本基线",
                "acceptance": "范围、排除项、决策责任和评审入口均有唯一记录。",
                "evidence": "基线版本、评审记录和 TraceLink。",
                "explicit_exclusion": "不替代正式需求、合同变更或架构冻结。",
                "requirement_id": "",
                "solution_id": "",
                "delivery_id": "",
                "specialty_types": [],
                "trace_link": "",
                "status": "DRAFT_NOT_SCHEDULED",
                "gate": "Phase 0 完成后方可正式排期",
            }
        )
        requirement_tasks = [_task_from_delivery(item, setup_id) for item in project_items]
        tasks.extend(requirement_tasks)
        requirement_ids = [task["task_id"] for task in requirement_tasks]
        tasks.extend(
            [
                {
                    "task_id": integration_id,
                    "project_id": project_id,
                    "project_name": project["project_name"],
                    "wave": "W3",
                    "wave_name": "非标与专项实现",
                    "task_type": "项目控制任务",
                    "task_name": "完成集成、迁移、权限与专项联调",
                    "category": "专项联调",
                    "priority": "P0",
                    "risk": "高" if project["high_risk_count"] else "中",
                    "owner_role": "集成工程师",
                    "support_roles": "数据工程师；安全/权限负责人；测试负责人",
                    "predecessors": requirement_ids,
                    "entry_condition": "项目需求交付任务已形成可验证输出。",
                    "work_output": "专项契约、联调记录、数据对账和异常闭环",
                    "acceptance": "正常、边界、失败恢复和审计场景均有证据。",
                    "evidence": "接口/迁移/权限专项记录与测试报告。",
                    "explicit_exclusion": "无前置数据、接口或环境时不得承诺完成联调。",
                    "requirement_id": "",
                    "solution_id": "",
                    "delivery_id": "",
                    "specialty_types": ["InterfaceSpec", "MigrationRunbook", "PermissionMatrix"],
                    "trace_link": "",
                    "status": "DRAFT_NOT_SCHEDULED",
                    "gate": "专项评审 Gate",
                },
                {
                    "task_id": acceptance_id,
                    "project_id": project_id,
                    "project_name": project["project_name"],
                    "wave": "W4",
                    "wave_name": "验收、交接与正式化",
                    "task_type": "项目控制任务",
                    "task_name": "组织集成验收与正式化评审",
                    "category": "验收治理",
                    "priority": "P0",
                    "risk": "中",
                    "owner_role": "测试负责人",
                    "support_roles": "项目负责人；业务顾问；PLM顾问",
                    "predecessors": [integration_id],
                    "entry_condition": "全部实施任务和专项联调有可审计结果。",
                    "work_output": "验收报告、遗留项清单和正式化评审记录",
                    "acceptance": "验收用例、结果、偏差和责任边界全部可追溯。",
                    "evidence": "签字评审、测试结果、遗留项及关闭证据。",
                    "explicit_exclusion": "未闭环高风险项不得被视为验收通过。",
                    "requirement_id": "",
                    "solution_id": "",
                    "delivery_id": "",
                    "specialty_types": [],
                    "trace_link": "",
                    "status": "DRAFT_NOT_SCHEDULED",
                    "gate": "项目验收 Gate",
                },
                {
                    "task_id": handover_id,
                    "project_id": project_id,
                    "project_name": project["project_name"],
                    "wave": "W4",
                    "wave_name": "验收、交接与正式化",
                    "task_type": "项目控制任务",
                    "task_name": "完成培训、运维与项目交接",
                    "category": "项目交接",
                    "priority": "P1",
                    "risk": "低",
                    "owner_role": "运维/培训负责人",
                    "support_roles": "项目负责人；测试负责人",
                    "predecessors": [acceptance_id],
                    "entry_condition": "验收 Gate 已通过或遗留项已获书面接收。",
                    "work_output": "培训材料、运维手册、交接清单和版本说明",
                    "acceptance": "接收人、交付物版本、已知问题和支持边界明确。",
                    "evidence": "交接签收、培训记录和发布版本说明。",
                    "explicit_exclusion": "未签收内容不默认为已交付。",
                    "requirement_id": "",
                    "solution_id": "",
                    "delivery_id": "",
                    "specialty_types": [],
                    "trace_link": "",
                    "status": "DRAFT_NOT_SCHEDULED",
                    "gate": "交接 Gate",
                },
            ]
        )

        project_summaries.append(
            {
                **project,
                "wbs_task_count": len(project_items) + 4,
                "project_control_task_count": 4,
                "requirement_delivery_task_count": len(project_items),
                "planning_status": "DRAFT_NOT_SCHEDULED",
            }
        )

    wave_counts = Counter(task["wave"] for task in tasks)
    role_counts = Counter(task["owner_role"] for task in tasks)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "package_id": "PLM-IMPLEMENTATION-WBS-20260921-R7",
        "version": "R7",
        "generated_at": generated_at,
        "status": "WBS_DRAFT_INTERNAL",
        "formal_status": "NOT_FORMAL_WBS",
        "source_package_id": source["package_id"],
        "boundaries": [
            "本 WBS 是内部实施草案，不代表合同计划、正式需求、正式方案或承诺日期。",
            "当前仍处于 Phase 0；Architecture/Data Model/API Contract Freeze 完成前不得据此启动正式业务编码。",
            "未编造人员姓名、日历日期或承诺工期；正式排期需在资源、环境和 Gate 条件明确后形成。",
            "40 条需求交付任务全部保留 Requirement/Solution/Delivery/证据追溯。",
        ],
        "summary": {
            "project_count": len(project_summaries),
            "task_count": len(tasks),
            "requirement_delivery_task_count": len(delivery_items),
            "project_control_task_count": len(tasks) - len(delivery_items),
            "wave_counts": dict(sorted(wave_counts.items())),
            "owner_role_counts": dict(sorted(role_counts.items())),
        },
        "waves": source["delivery_sequence"],
        "projects": project_summaries,
        "tasks": tasks,
        "roles": [
            {"role": "项目负责人", "responsibility": "范围、决策、Gate、风险与跨团队协调"},
            {"role": "业务顾问", "responsibility": "业务事实、流程、边界与验收样例"},
            {"role": "PLM顾问", "responsibility": "标准能力配置、差异评估与方案落地"},
            {"role": "集成工程师", "responsibility": "接口契约、联调、失败恢复与对账"},
            {"role": "数据工程师", "responsibility": "数据盘点、映射、迁移、回退与质量校验"},
            {"role": "安全/权限负责人", "responsibility": "角色权限、最小权限、审计与例外"},
            {"role": "测试负责人", "responsibility": "用例、质量门槛、缺陷闭环与验收证据"},
            {"role": "运维/培训负责人", "responsibility": "部署运维、培训、交接与支持边界"},
        ],
    }
    fingerprint_source = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    payload["fingerprint"] = hashlib.sha256(fingerprint_source).hexdigest()
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an internal implementation WBS draft.")
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--generated-at", default=datetime.now().astimezone().isoformat())
    args = parser.parse_args()
    source = json.loads(args.source.read_text(encoding="utf-8"))
    payload = build_wbs(source, args.generated_at)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
