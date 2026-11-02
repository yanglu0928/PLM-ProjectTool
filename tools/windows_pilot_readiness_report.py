"""Combine non-secret Pilot references and package preflight claims into a non-authorizing report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_windows_pilot_input_register import DATABASE_CREDENTIAL_TARGET, validate_register


EXPECTED_STARTUP_FIELDS = {
    "blocker_codes",
    "database_credential_reference_verified",
    "database_credential_target_reference",
    "formal_license_trust_verified",
    "formal_startup_ready",
    "packaged_product_public_key_resource_present",
    "service_identity_acl_verified",
    "tls_certificate_configured",
    "tls_private_key_configured",
}
FIELD_GUIDANCE = {
    "product_public_key_sha256": {
        "label": "产品公钥 SHA-256",
        "maintain": "登记正式产品公钥文件的 64 位 SHA-256 摘要。",
        "source": "从受控发布材料取得公钥文件并独立计算摘要；摘要本身不代表信任校验通过。",
        "never": "不要粘贴公钥文件正文、私钥或签名材料。",
        "owner_role": "发布负责人",
        "next_step": "向受控发布材料责任人核对公钥资源与独立SHA-256记录，再登记摘要。",
    },
    "license_evidence_ref": {
        "label": "License 核验记录",
        "maintain": "登记正式 License 核验/签发流程对应的 LIC- 编号。",
        "source": "来自受控工作台的正式 License 验证记录。",
        "never": "不要填写 License 正文、签名值、客户码或私钥。",
        "owner_role": "License 管理负责人",
        "next_step": "从受控工作台取得正式验证记录编号，并由第二责任人核对引用。",
    },
    "service_identity_ref": {
        "label": "Windows 服务身份",
        "maintain": "登记固定 Windows 服务身份引用，例如 NT SERVICE\\PLMProjectTool。",
        "source": "来自目标部署主机上已配置并独立核实的服务身份。",
        "never": "不要填写账户密码、Token 或含凭据的命令行。",
        "owner_role": "Windows 运维负责人",
        "next_step": "在目标主机核对服务账户名称与安装/数据目录权限，记录证据编号。",
    },
    "tls_certificate_thumbprint": {
        "label": "TLS 证书 Thumbprint",
        "maintain": "登记目标 HTTPS 证书的 40 或 64 位十六进制 Thumbprint。",
        "source": "从目标部署证书存储/受控证书清单读取公开指纹。",
        "never": "不要提供证书私钥、PFX/P12 文件或导出密码。",
        "owner_role": "信息安全/证书负责人",
        "next_step": "在受控证书存储核对公开Thumbprint与有效期，登记证据引用。",
    },
    "tls_dns_name": {
        "label": "TLS DNS 名称",
        "maintain": "登记与 HTTPS 证书匹配的 DNS 主机名。",
        "source": "来自已批准部署域名和证书 SAN。",
        "never": "不要填写用户名、口令或访问 Token。",
        "owner_role": "网络与证书负责人",
        "next_step": "将批准的部署域名与证书SAN逐项比对后登记主机名。",
    },
    "evidence_refs.license": {
        "label": "License 证据引用",
        "maintain": "登记正式 License 核验记录的 EVD- 编号。",
        "source": "来自经独立复核的 License 证据目录。",
        "never": "不要附加 License 文件或签名载荷。",
        "owner_role": "License 管理负责人",
        "next_step": "由独立复核人检查受控License审查记录存在且编号有效。",
    },
    "evidence_refs.service_acl": {
        "label": "服务 ACL 证据引用",
        "maintain": "登记服务身份、安装目录和数据目录 ACL 检查的 EVD- 编号。",
        "source": "来自目标主机受控的 ACL 审核记录。",
        "never": "不要粘贴用户/客户资料或账户秘密。",
        "owner_role": "Windows 安全/运维负责人",
        "next_step": "生成最小化ACL核查记录并单独复核安装目录与数据目录权限。",
    },
    "evidence_refs.tls_chain_renewal": {
        "label": "TLS 链与续期证据引用",
        "maintain": "登记证书链、DNS 匹配和续期安排的 EVD- 编号。",
        "source": "来自证书管理系统或受控证书核验记录。",
        "never": "不要附加私钥或私有证书导出包。",
        "owner_role": "信息安全/证书负责人",
        "next_step": "复核可信链、域名匹配和续期责任，登记受控证据编号。",
    },
    "evidence_refs.database_scope": {
        "label": "数据库凭据范围证据引用",
        "maintain": "登记数据库凭据目标、作用域与轮换约束的 EVD- 编号。",
        "source": "来自 Credential Manager 目标配置与数据库权限核验记录。",
        "never": "不要填写密码、连接串或 Credential Manager Secret 内容。",
        "owner_role": "数据库运维负责人",
        "next_step": "核对固定Credential Manager目标及最小权限/轮换记录，只登记证据编号。",
    },
}

FIELD_BLOCKERS = {
    "packaged_product_public_key_resource_present": "FORMAL_PRODUCT_PUBLIC_KEY_NOT_PACKAGED",
    "formal_license_trust_verified": "FORMAL_LICENSE_TRUST_NOT_VERIFIED",
    "database_credential_reference_verified": "DATABASE_CREDENTIAL_REFERENCE_NOT_VERIFIED",
    "service_identity_acl_verified": "SERVICE_IDENTITY_ACL_NOT_VERIFIED",
}

RECOMMENDED_ACTIONS = (
    {
        "code": "TRUST_KEY_LICENSE",
        "title": "核对正式产品公钥与 License 信任",
        "blocker_codes": ("FORMAL_PRODUCT_PUBLIC_KEY_NOT_PACKAGED", "FORMAL_LICENSE_TRUST_NOT_VERIFIED"),
        "fields": ("product_public_key_sha256", "license_evidence_ref", "evidence_refs.license"),
        "owner_role": "发布负责人 / License 管理负责人",
        "next_step": "从受控发布与License工作台独立核对材料及证据编号。",
    },
    {
        "code": "DATABASE_SCOPE",
        "title": "核对数据库凭据目标与权限范围",
        "blocker_codes": ("DATABASE_CREDENTIAL_REFERENCE_NOT_VERIFIED",),
        "fields": ("evidence_refs.database_scope",),
        "owner_role": "数据库运维负责人",
        "next_step": "核实固定Credential Manager目标、最小权限和轮换记录。",
    },
    {
        "code": "SERVICE_IDENTITY_ACL",
        "title": "核对 Windows 服务身份与目录权限",
        "blocker_codes": ("SERVICE_IDENTITY_ACL_NOT_VERIFIED",),
        "fields": ("service_identity_ref", "evidence_refs.service_acl"),
        "owner_role": "Windows 运维 / 安全负责人",
        "next_step": "核实服务身份以及安装目录、数据目录ACL并登记独立证据。",
    },
    {
        "code": "TLS_CHAIN_ENDPOINT",
        "title": "核对 HTTPS 证书链、域名与续期",
        "blocker_codes": ("TLS_CERTIFICATE_CONFIGURATION_NOT_VERIFIED",),
        "fields": ("tls_certificate_thumbprint", "tls_dns_name", "evidence_refs.tls_chain_renewal"),
        "owner_role": "信息安全 / 证书负责人",
        "next_step": "核对证书链与SAN域名、有效期及续期责任。",
    },
)


def _manifest_blockers(manifest: Any) -> tuple[bool, list[str]]:
    if not isinstance(manifest, dict):
        return False, []
    startup = manifest.get("startup_preflight")
    if (manifest.get("kind") != "WINDOWS_PARENT_PACKAGE_NON_RELEASE_CANDIDATE"
            or manifest.get("release_eligible") is not False
            or manifest.get("legal_clearance") is not False
            or not isinstance(startup, dict)
            or set(startup) != EXPECTED_STARTUP_FIELDS
            or startup.get("database_credential_target_reference") != DATABASE_CREDENTIAL_TARGET
            or not isinstance(startup.get("blocker_codes"), list)
            or any(type(startup.get(key)) is not bool for key in (
                "database_credential_reference_verified", "formal_license_trust_verified",
                "formal_startup_ready", "packaged_product_public_key_resource_present",
                "service_identity_acl_verified", "tls_certificate_configured",
                "tls_private_key_configured",
            ))):
        return False, []

    codes = [code for key, code in FIELD_BLOCKERS.items() if startup[key] is not True]
    if startup["tls_certificate_configured"] is not True or startup["tls_private_key_configured"] is not True:
        codes.append("TLS_CERTIFICATE_CONFIGURATION_NOT_VERIFIED")
    codes = sorted(set(codes))
    declared = startup["blocker_codes"]
    if (any(not isinstance(code, str) for code in declared)
            or sorted(declared) != codes
            or startup["formal_startup_ready"] is not (not codes)):
        return False, []
    return True, codes


def build_report(manifest: Any, register: Any) -> dict[str, Any]:
    manifest_valid, startup_codes = _manifest_blockers(manifest)
    register_result = validate_register(register)
    reason_codes = {"NON_RELEASE_CANDIDATE"}
    if not manifest_valid:
        reason_codes.add("PACKAGE_MANIFEST_INVALID")
    else:
        reason_codes.update(startup_codes)
    if register_result["status"] == "INVALID":
        reason_codes.add("INPUT_REGISTER_INVALID")
    elif register_result["status"] == "INCOMPLETE":
        reason_codes.add("INPUT_REGISTER_INCOMPLETE")
    else:
        reason_codes.add("INPUT_REGISTER_REQUIRES_INDEPENDENT_VERIFICATION")

    missing = set(register_result["missing_fields"])
    recommended_actions = []
    for action in RECOMMENDED_ACTIONS:
        active_blockers = [code for code in action["blocker_codes"] if code in startup_codes]
        active_fields = [field for field in action["fields"] if field in missing]
        if active_blockers or active_fields:
            recommended_actions.append({
                "code": action["code"],
                "title": action["title"],
                "blocker_codes": active_blockers,
                "fields": active_fields,
                "owner_role": action["owner_role"],
                "next_step": action["next_step"],
            })

    return {
        "status": "DIAGNOSTIC_ONLY_NOT_READY",
        "pilot_ready": False,
        "launch_authorized": False,
        "release_eligible": False,
        "legal_clearance": False,
        "package_manifest_status": "VALID_NON_RELEASE_CANDIDATE" if manifest_valid else "INVALID",
        "input_register_status": register_result["status"],
        "input_register_missing_fields": register_result["missing_fields"],
        "input_register_guidance": {
            field: FIELD_GUIDANCE[field]
            for field in register_result["missing_fields"]
            if field in FIELD_GUIDANCE
        },
        "recommended_actions": recommended_actions,
        "startup_blocker_codes": startup_codes if manifest_valid else [],
        "reason_codes": sorted(reason_codes),
    }


def render_readable_report(report: dict[str, Any]) -> str:
    """Render a fixed, non-authorizing Chinese operator summary."""
    lines = [
        "PLM Pilot 准备度检查（只读诊断）",
        "诊断状态：当前未就绪",
        "启动授权：否",
        "发行资格：否",
        "法律放行：否",
        "包清单：有效（非发行候选）" if report.get("package_manifest_status") == "VALID_NON_RELEASE_CANDIDATE" else "包清单：无效",
    ]
    status_labels = {
        "INCOMPLETE": "信息不完整",
        "INVALID": "格式无效，请按固定模板修正",
        "COMPLETE_REQUIRES_INDEPENDENT_VERIFICATION": "登记完整，仍需独立核验",
    }
    register_status = report.get("input_register_status")
    lines.append("登记表：" + status_labels.get(register_status, "无法确认"))
    blockers = report.get("startup_blocker_codes", [])
    if blockers:
        lines.append("启动阻断项：")
        lines.extend("- " + code for code in blockers if isinstance(code, str))
    actions = report.get("recommended_actions", [])
    if actions:
        lines.append("建议处理顺序（只作提示，不代表核验通过）：")
        for index, action in enumerate(actions, start=1):
            blockers = ", ".join(action.get("blocker_codes", [])) or "登记引用待补充"
            lines.extend((
                f"{index}. {action.get('title', '处理就绪阻断项')}",
                "  对应阻断：" + blockers,
                "  涉及字段：" + (", ".join(action.get("fields", [])) or "独立核验"),
                "  建议责任角色：" + str(action.get("owner_role", "项目负责人")),
                "  下一步操作：" + str(action.get("next_step", "按固定模板补充非秘密证据引用")),
            ))
    guidance = report.get("input_register_guidance", {})
    if guidance:
        lines.append("待补充字段：")
        for item in guidance.values():
            if not isinstance(item, dict):
                continue
            label = item.get("label", "未命名字段")
            lines.extend((
                "- " + str(label),
                "  需要维护：" + str(item.get("maintain", "按模板维护固定引用")),
                "  参考来源：" + str(item.get("source", "参照受控证据记录")),
                "  请勿填写：" + str(item.get("never", "密码、密钥或客户材料")),
                "  建议责任角色：" + str(item.get("owner_role", "项目负责人")),
                "  下一步操作：" + str(item.get("next_step", "按固定模板补充非秘密证据引用")),
            ))
    elif register_status == "COMPLETE_REQUIRES_INDEPENDENT_VERIFICATION":
        lines.append("登记项齐全，但必须独立核验证据；这不代表可以启动或发行。")
    return chr(10).join(lines) + chr(10)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--register", type=Path, required=True)
    parser.add_argument("--format", choices=("json", "text"), default="json")
    args = parser.parse_args()
    try:
        manifest = _read_json(args.manifest)
        register = _read_json(args.register)
    except (OSError, UnicodeError, json.JSONDecodeError):
        report = build_report(None, None)
        report["reason_codes"] = sorted(set(report["reason_codes"]) | {"INPUT_FILE_UNREADABLE_OR_INVALID_JSON"})
        exit_code = 2
    else:
        report = build_report(manifest, register)
        if report["package_manifest_status"] == "INVALID" or report["input_register_status"] == "INVALID":
            exit_code = 2
        elif report["input_register_status"] == "INCOMPLETE":
            exit_code = 1
        else:
            exit_code = 0
    if args.format == "text":
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="strict")
        sys.stdout.write(render_readable_report(report))
    else:
        print(json.dumps(report, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
