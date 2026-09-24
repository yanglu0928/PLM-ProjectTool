from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


DECISION_PROFILES: tuple[dict[str, Any], ...] = (
    {
        "profile": "ENGINEERING_SOFTWARE_COMPATIBILITY",
        "keywords": ("设计软件", "版本"),
        "decision": "以现网已验证的软件版本和文件格式作为一期兼容基线。接口采用可配置适配层；升级、跨版本批量转换和未验证插件不纳入一期承诺。",
        "scope": "建立软件、版本、插件、文件格式和升级窗口矩阵；每个组合至少完成打开、保存、签入签出和发布验证。",
        "exclusion": "未提供版本和样例的组合只登记为兼容性待测项，不承诺可用。",
        "acceptance": "版本矩阵完整；已纳入组合逐项通过样例验证；未验证组合在范围中明确排除。",
        "risk": "中",
    },
    {
        "profile": "PHASED_SCOPE",
        "keywords": ("一期/后续", "范围"),
        "decision": "一期只覆盖资料最成熟、跨系统依赖最少且能形成闭环验收的核心流程；多中心扩展、低成熟度接口和历史数据深度治理进入后续阶段。",
        "scope": "按业务价值、依赖、数据准备度和验收可行性形成一期清单；每项同时标注责任人和排除项。",
        "exclusion": "未进入一期清单的诉求不默认为一期交付，不以预留字段替代范围确认。",
        "acceptance": "一期范围、依赖、责任人和后续清单一一对应，且不存在同一事项跨阶段重复计入。",
        "risk": "中",
    },
    {
        "profile": "PROJECT_PRODUCT_QUOTATION_MODEL",
        "keywords": ("项目、产品、报价单",),
        "decision": "采用一项目对应多个产品、每个产品独立维护多版本报价单的模型。项目层只做汇总视图；产品间复制必须显式触发，后续变更不自动传播。",
        "scope": "保留项目、产品、报价单和报价版本四级标识；报价审批和生效状态绑定到具体产品版本。",
        "exclusion": "不采用共享可变报价明细，避免一个产品的修改影响其他产品历史版本。",
        "acceptance": "两个多产品样例可独立报价、汇总、复制和升版；历史版本不被新版本覆盖。",
        "risk": "中",
    },
    {
        "profile": "QUOTATION_TEST_SAMPLES",
        "keywords": ("报价模板", "对账"),
        "decision": "一期使用不少于 10 份脱敏报价样例作为计算与接口验收集，覆盖常规、缺省、边界、舍入、版本变更和 ERP 对账场景。",
        "scope": "真实脱敏样例不足时先用确定性合成样例开发，但正式验收必须补齐真实脱敏样例并重新对账。",
        "exclusion": "合成样例通过不等同于客户历史报价对账通过。",
        "acceptance": "验收集样例数量不少于 10，关键字段齐全，逐项计算结果与基准结果一致。",
        "risk": "中",
    },
    {
        "profile": "MASTER_DATA_OWNERSHIP",
        "keywords": ("物料编码", "主数据边界"),
        "decision": "SAP 继续作为物料编码和已生效物料主数据的权威源；PLM 负责研发对象、配方版本、变更过程和编码申请。配方号改为受控规则生成，发布后向 SAP 回写。",
        "scope": "明确编码申请、审批、分配、回写、失败重试和人工纠错责任；个人自定义配方号停止新增，历史编号保留映射。",
        "exclusion": "PLM 不直接改写 SAP 已生效编码；SAP 不覆盖 PLM 中的研发版本历史。",
        "acceptance": "新建、变更、撤销、重复申请和回写失败场景均可追溯，双方主数据不存在双主冲突。",
        "risk": "高",
    },
    {
        "profile": "DOCUMENT_MIGRATION_AND_PUBLISH",
        "keywords": ("迁移范围", "下发规则"),
        "decision": "先迁移有效目录、当前批准版本、必要元数据和有效权限；历史版本、失效文件和无归属资料单列清理批次。PLM 仅在受控发布后单向下发到文档平台。",
        "scope": "先完成目录、文件量、格式、Hash、权限、版本和所有者盘点；增量迁移采用可重跑批次并保留失败清单。",
        "exclusion": "未完成盘点的目录不直接全量迁移；文档平台不得反向覆盖 PLM 受控版本。",
        "acceptance": "抽样文件可打开，元数据和权限一致，Hash 可核对，失败可重跑，下发记录可追溯。",
        "risk": "高",
    },
    {
        "profile": "CONTROLLED_BUSINESS_DEFINITION",
        "keywords": ("定义存在分歧",),
        "decision": "建立唯一受控分类规则：业务部门提出分类，采购与质量共同确认，PLM 保存判定依据和例外；存在分歧时暂按更严格的专用件管理。",
        "scope": "规则至少包含判定条件、责任角色、生效日期、例外和历史数据处理方式。",
        "exclusion": "不允许开发、采购或质量任一方以个人口径直接覆盖受控分类。",
        "acceptance": "同一部品在相同条件下得到唯一分类；例外有审批与有效期；历史变更可追溯。",
        "risk": "高",
    },
    {
        "profile": "UNKNOWN_EXTERNAL_INTEGRATION",
        "keywords": ("同步字段", "数据规模"),
        "decision": "一期按只读查询和最小字段映射设计外部系统集成；批量同步、写回和性能承诺在取得接口文档、样例及数据规模后再纳入。",
        "scope": "先验证认证、查询、分页、错误码、限流、字段映射和审计；接口适配层与业务规则分离。",
        "exclusion": "缺少正式接口文档时不承诺写回、实时同步或峰值性能。",
        "acceptance": "最小查询链路使用脱敏样例通过；未知字段、超时、限流和不可用场景有明确降级结果。",
        "risk": "高",
    },
    {
        "profile": "CONTRACT_PRECEDENCE",
        "keywords": ("合同", "优先级"),
        "decision": "工作基线按已签署主合同、后签署补充/变更文件、对应技术协议和项目管理文件的顺序解释；同层冲突进入合同变更控制，不由实施团队自行扩大责任。",
        "scope": "建立条款、功能、交付物、责任方、验收依据和冲突项矩阵，并保留原条款定位。",
        "exclusion": "该顺序仅用于内部需求分析，不替代法务意见或双方正式合同解释。",
        "acceptance": "每项交付要求可追溯到唯一有效条款；冲突项有责任人和正式变更路径。",
        "risk": "高",
    },
    {
        "profile": "CUSTOM_DELIVERY_RESPONSIBILITY",
        "keywords": ("培训", "源码", "维护责任"),
        "decision": "定制开发必须交付可部署制品、受托范围内的源码、配置与迁移脚本、接口说明、测试证据、运维手册和培训材料；质保期限与计价按有效合同执行，缺失部分进入变更控制。",
        "scope": "培训采用一次主培训和可复用材料；接口按契约、错误码、样例和联调记录验收；后续变更按影响评估后计价。",
        "exclusion": "第三方闭源组件源码、非本项目通用资产和未签约长期运维不自动纳入交付。",
        "acceptance": "交付清单逐项签收；部署可复现；接口测试通过；培训资料可复用；维护边界有书面记录。",
        "risk": "高",
    },
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build delegated requirement review package")
    parser.add_argument("--source-package", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--generated-at", required=True)
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_assumption(assumption: dict[str, Any]) -> dict[str, Any]:
    issue = assumption["issue"]
    for profile in DECISION_PROFILES:
        if all(keyword in issue for keyword in profile["keywords"]):
            return dict(profile)
    return {
        "profile": "CONSERVATIVE_SCOPE_DEFAULT",
        "decision": "保留现有可验证范围，未知部分不承诺自动化或性能；采用可配置、可回滚实现，并将例外纳入变更控制。",
        "scope": "仅处理现有证据能够支持的对象、流程和接口；缺失资料不阻塞其他候选继续分析。",
        "exclusion": "不得把缺失资料补写为客户事实，也不得据此扩大合同、接口或验收范围。",
        "acceptance": "已知范围可追溯，未知项有明确边界和变更入口，现有流程可回退。",
        "risk": "中",
    }


def review_priority(requirement: dict[str, Any], resolution: dict[str, Any] | None) -> str:
    if resolution or requirement["status"] == "DRAFT_WITH_ASSUMPTION":
        return "P0"
    if requirement["category"] in {"非标功能", "差异项"}:
        return "P0"
    return "P1"


def build_package(source: dict[str, Any], generated_at: str) -> dict[str, Any]:
    if source.get("version") != "R3" or not source.get("fingerprint"):
        raise ValueError("Source must be a fingerprinted R3 desktop-discovery package")
    if len({row["candidate_id"] for row in source["requirements"]}) != len(source["requirements"]):
        raise ValueError("Requirement candidate IDs must be unique")

    decisions: list[dict[str, Any]] = []
    resolution_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for assumption in source["assumptions"]:
        resolved = resolve_assumption(assumption)
        decision = {
            "decision_id": f"AID-{assumption['assumption_id']}",
            "assumption_id": assumption["assumption_id"],
            "project_id": assumption["project_id"],
            "project_name": assumption["project_name"],
            "issue": assumption["issue"],
            "source_basis": assumption["basis"],
            "profile": resolved["profile"],
            "recommended_decision": resolved["decision"],
            "included_scope": resolved["scope"],
            "explicit_exclusion": resolved["exclusion"],
            "acceptance_basis": resolved["acceptance"],
            "risk": resolved["risk"],
            "evidence_link": assumption["evidence_link"],
            "status": "ADOPTED_WORKING_BASELINE",
            "authority": "AI_DELEGATED_BY_USER",
            "formalization": "INTERNAL_ONLY_UNTIL_FORMAL_GATE",
        }
        decisions.append(decision)
        resolution_by_key[(assumption["project_id"], assumption["issue"])] = decision

    reviewed_requirements: list[dict[str, Any]] = []
    for requirement in source["requirements"]:
        resolution = resolution_by_key.get((requirement["project_id"], requirement["title"]))
        if resolution:
            disposition = "采用 AI 代决策工作基线后纳入需求评审稿"
            basis = resolution["recommended_decision"]
            resolution_id = resolution["decision_id"]
            risk = resolution["risk"]
        elif requirement["status"] == "DRAFT_WITH_ASSUMPTION":
            disposition = "带工作假设纳入需求评审稿"
            basis = "仅有方案或风险材料支持，实施前必须通过样例或接口验证收敛。"
            resolution_id = ""
            risk = "中"
        else:
            disposition = "纳入需求评审稿"
            basis = "已有实际调研、合同或技术协议证据，可继续完善边界和验收标准。"
            resolution_id = ""
            risk = "低" if requirement["category"] == "标准功能" else "中"
        reviewed_requirements.append(
            {
                **requirement,
                "source_status": requirement["status"],
                "review_priority": review_priority(requirement, resolution),
                "ai_disposition": disposition,
                "decision_basis": basis,
                "resolution_id": resolution_id,
                "risk": risk,
                "review_status": "INTERNAL_REVIEW_DRAFT",
                "formal_status": "NOT_FORMAL_REQUIREMENT",
                "draft_version": "DRAFT-R4",
            }
        )

    project_summaries: list[dict[str, Any]] = []
    for project in source["projects"]:
        rows = [row for row in reviewed_requirements if row["project_id"] == project["project_id"]]
        project_decisions = [row for row in decisions if row["project_id"] == project["project_id"]]
        project_summaries.append(
            {
                "project_id": project["project_id"],
                "project_name": project["project_name"],
                "requirement_count": len(rows),
                "p0_count": sum(row["review_priority"] == "P0" for row in rows),
                "p1_count": sum(row["review_priority"] == "P1" for row in rows),
                "working_decision_count": len(project_decisions),
                "high_risk_count": sum(row["risk"] == "高" for row in rows),
                "status": "INTERNAL_REVIEW_READY",
                "next_action": "进入标准能力匹配和解决方案草案；正式化继续受 Phase 0 与 Gate 约束。",
            }
        )

    package = {
        "schema_version": "1.0",
        "package_id": "PLM-DELEGATED-REQUIREMENT-REVIEW-R4",
        "version": "R4",
        "generated_at": generated_at,
        "status": "INTERNAL_REQUIREMENT_REVIEW_READY",
        "source_package_id": source["package_id"],
        "source_fingerprint": source["fingerprint"],
        "authority": "USER_DELEGATED_ROUTINE_DECISIONS",
        "decision_policy": [
            "已有证据优先",
            "保守默认和最小范围",
            "未知项不伪造客户事实",
            "所有工作决策可追溯且可回滚",
            "正式 Gate、客户数据外发、安全/License 和锁定基线变更仍需专项确认",
        ],
        "boundaries": [
            "本包关闭的是内部分析阻塞，不代表客户或项目经理确认",
            "所有条目仍为需求评审稿，不是正式 Requirement",
            "不触发需求冻结、Phase 6 或正式业务编码",
            "本轮不调用外部模型，不包含数据外发授权",
        ],
        "projects": project_summaries,
        "decisions": decisions,
        "requirements": reviewed_requirements,
        "fingerprint": "",
    }
    digest = json.dumps(package, ensure_ascii=False, sort_keys=True).encode("utf-8")
    package["fingerprint"] = hashlib.sha256(digest).hexdigest()
    return package


def main() -> int:
    args = parse_args()
    source_path = args.source_package.resolve()
    source = load_json(source_path)
    package = build_package(source, args.generated_at)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "delegated-requirement-review-package.json"
    output_path.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    evidence_source = source_path.parent / "evidence-navigator.html"
    if evidence_source.is_file():
        shutil.copy2(evidence_source, output_dir / "evidence-navigator.html")
    print(
        json.dumps(
            {
                "status": package["status"],
                "project_count": len(package["projects"]),
                "decision_count": len(package["decisions"]),
                "requirement_count": len(package["requirements"]),
                "p0_count": sum(row["review_priority"] == "P0" for row in package["requirements"]),
                "output": str(output_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
