from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ErrorSpec:
    code: str
    status_code: int
    message: str


# The common codes and HTTP meanings come from the frozen API-01 contract.
# REQUEST_METHOD_NOT_ALLOWED is an additive code for the framework's 405.
COMMON_ERRORS: dict[str, ErrorSpec] = {
    'JOB_NOT_RETRYABLE': ErrorSpec('JOB_NOT_RETRYABLE',409,'此任务不允许重试。'),
    'AUDIT_EXPORT_SCOPE_INVALID': ErrorSpec('AUDIT_EXPORT_SCOPE_INVALID',422,'导出范围或用途不允许。'),
    "REQUEST_MALFORMED": ErrorSpec("REQUEST_MALFORMED", 400, "请求格式不正确。"),
    "REQUEST_METHOD_NOT_ALLOWED": ErrorSpec(
        "REQUEST_METHOD_NOT_ALLOWED", 405, "此操作不支持该请求方法。"
    ),
    "AUTH_REQUIRED": ErrorSpec("AUTH_REQUIRED", 401, "请先登录。"),
    "AUTH_INVALID_CREDENTIALS": ErrorSpec("AUTH_INVALID_CREDENTIALS", 401, "用户名或密码不正确。"),
    "AUTH_SESSION_EXPIRED": ErrorSpec("AUTH_SESSION_EXPIRED", 401, "登录已失效。"),
    "AUTH_USER_DISABLED": ErrorSpec("AUTH_USER_DISABLED", 409, "管理命令与用户当前状态冲突。"),
    "AUTH_CSRF_INVALID": ErrorSpec("AUTH_CSRF_INVALID", 403, "请求安全校验失败。"),
    "LICENSE_OPERATION_DENIED": ErrorSpec(
        "LICENSE_OPERATION_DENIED", 403, "当前许可不允许此操作。"
    ),
    "RESOURCE_NOT_FOUND": ErrorSpec("RESOURCE_NOT_FOUND", 404, "资源不存在。"),
    "CONFLICT_VERSION": ErrorSpec("CONFLICT_VERSION", 409, "资源已更新，请刷新后重试。"),
    "CONFLICT_STATE": ErrorSpec("CONFLICT_STATE", 409, "当前状态不允许此操作。"),
    "CONFLICT_DUPLICATE": ErrorSpec("CONFLICT_DUPLICATE", 409, "资源已存在。"),
    "CONFLICT_IDEMPOTENCY": ErrorSpec(
        "CONFLICT_IDEMPOTENCY", 409, "请求与已受理的操作不一致。"
    ),
    "FILE_TOO_LARGE": ErrorSpec("FILE_TOO_LARGE", 413, "文件超过允许大小。"),
    "FILE_TYPE_UNSUPPORTED": ErrorSpec(
        "FILE_TYPE_UNSUPPORTED", 415, "不支持此文件类型。"
    ),
    "FILE_UPLOAD_EXPIRED": ErrorSpec(
        "FILE_UPLOAD_EXPIRED", 409, "上传意图已过期或已终止。"
    ),
    "FILE_INTEGRITY_MISMATCH": ErrorSpec(
        "FILE_INTEGRITY_MISMATCH", 409, "文件内容与声明不一致。"
    ),
    "FILE_CONTENT_UNAVAILABLE": ErrorSpec(
        "FILE_CONTENT_UNAVAILABLE", 503, "文件内容暂不可用。"
    ),
    "VALIDATION_FAILED": ErrorSpec("VALIDATION_FAILED", 422, "请求内容不符合要求。"),
    "SURVEY_CONCLUSION_SOURCE_INVALID": ErrorSpec(
        "SURVEY_CONCLUSION_SOURCE_INVALID", 422, "调研结论来源不符合要求。"
    ),
    "EVIDENCE_LOCATOR_INVALID": ErrorSpec("EVIDENCE_LOCATOR_INVALID", 422, "证据定位无效。"),
    "EVIDENCE_FINGERPRINT_MISMATCH": ErrorSpec("EVIDENCE_FINGERPRINT_MISMATCH", 409, "证据来源内容已变化。"),
    "PLATFORM_SECRET_PURPOSE_INVALID": ErrorSpec(
        "PLATFORM_SECRET_PURPOSE_INVALID", 422, "Secret 用途或使用方不受支持。"
    ),
    "PLATFORM_SENSITIVE_VALUE_FORBIDDEN": ErrorSpec(
        "PLATFORM_SENSITIVE_VALUE_FORBIDDEN", 422, "此配置值不允许保存。"
    ),
    "CONFLICT_VERSION_REQUIRED": ErrorSpec(
        "CONFLICT_VERSION_REQUIRED", 428, "请提供资源版本。"
    ),
    "AUTH_RATE_LIMITED": ErrorSpec("AUTH_RATE_LIMITED", 429, "请求过于频繁，请稍后重试。"),
    "SYSTEM_INTERNAL": ErrorSpec("SYSTEM_INTERNAL", 500, "服务暂时无法完成请求。"),
    "SYSTEM_UNAVAILABLE": ErrorSpec("SYSTEM_UNAVAILABLE", 503, "服务暂时不可用。"),
    "AI_PROVIDER_UNAVAILABLE": ErrorSpec("AI_PROVIDER_UNAVAILABLE", 503, "Provider 暂不可用。"),
    "AI_PROMPT_VERSION_INVALID": ErrorSpec(
        "AI_PROMPT_VERSION_INVALID", 422, "Prompt 版本或策略与任务不兼容。"
    ),
    "AI_EGRESS_AUTHORIZATION_REQUIRED": ErrorSpec(
        "AI_EGRESS_AUTHORIZATION_REQUIRED", 403, "本次 AI 操作缺少有效外发授权。"
    ),
    "PLATFORM_SECRET_UNAVAILABLE": ErrorSpec(
        "PLATFORM_SECRET_UNAVAILABLE", 503, "Secret 服务暂时不可用。"
    ),
    "PROJECT_USER_ALREADY_ASSIGNED": ErrorSpec(
        "PROJECT_USER_ALREADY_ASSIGNED", 409, "用户已属于其他项目。"
    ),
    "PROJECT_ROLE_INVALID": ErrorSpec(
        "PROJECT_ROLE_INVALID", 422, "项目负责人不符合要求。"
    ),
    "PROJECT_ARCHIVED": ErrorSpec(
        "PROJECT_ARCHIVED", 409, "项目已归档，不允许修改。"
    ),
    "WORKFLOW_GATE_NOT_SATISFIED": ErrorSpec(
        "WORKFLOW_GATE_NOT_SATISFIED", 409,
        "当前清单、证据或评审尚不满足要求。",
    ),
    "WORKFLOW_TRANSITION_INVALID": ErrorSpec(
        "WORKFLOW_TRANSITION_INVALID", 409,
        "当前工作流不允许此阶段迁移。",
    ),
    "PROJECT_DEPARTMENT_IN_USE": ErrorSpec(
        "PROJECT_DEPARTMENT_IN_USE", 409, "部门仍有在用成员，不能停用。"
    ),
    "CAPABILITY_EVIDENCE_REQUIRED": ErrorSpec(
        "CAPABILITY_EVIDENCE_REQUIRED", 422, "能力项缺少合格的全局证据。"
    ),
    "HANDOVER_SOURCE_REQUIRED": ErrorSpec(
        "HANDOVER_SOURCE_REQUIRED", 422, "交接分析缺少合格的固定来源。"
    ),
    "HANDOVER_ITEM_INCOMPLETE": ErrorSpec(
        "HANDOVER_ITEM_INCOMPLETE", 422, "交接问题项缺少合格证据或资料缺失声明。"
    ),
    "HANDOVER_CONFIRMATION_PROMPT_REQUIRED": ErrorSpec(
        "HANDOVER_CONFIRMATION_PROMPT_REQUIRED", 422, "待确认项缺少完整确认指引。"
    ),
    "HANDOVER_ACTION_STATE_INVALID": ErrorSpec(
        "HANDOVER_ACTION_STATE_INVALID", 409, "当前待办状态不允许此操作。"
    ),
    "HANDOVER_ACTION_EVIDENCE_REQUIRED": ErrorSpec(
        "HANDOVER_ACTION_EVIDENCE_REQUIRED", 422, "待办缺少所需证据。"
    ),
    "HANDOVER_ACTION_RESOLUTION_REQUIRED": ErrorSpec(
        "HANDOVER_ACTION_RESOLUTION_REQUIRED", 422, "关闭待办缺少验证结果或解决追溯。"
    ),
    "BUSINESS_REVIEW_NOT_ELIGIBLE": ErrorSpec(
        "BUSINESS_REVIEW_NOT_ELIGIBLE", 422, "当前版本不满足送审条件。"
    ),
    "REVIEW_SUBJECT_LOCKED": ErrorSpec(
        "REVIEW_SUBJECT_LOCKED", 409, "当前主题版本正在评审中。"
    ),
    "REVIEW_REVIEWER_INELIGIBLE": ErrorSpec(
        "REVIEW_REVIEWER_INELIGIBLE", 422, "确认人集合不符合评审要求。"
    ),
    "REVIEW_COMMENT_REQUIRED": ErrorSpec(
        "REVIEW_COMMENT_REQUIRED", 422, "退回决定必须填写实质意见。"
    ),
    "REVIEW_DECISION_EXISTS": ErrorSpec(
        "REVIEW_DECISION_EXISTS", 409, "当前确认人已作出最终决定。"
    ),
}


class ApplicationError(Exception):
    """A classified failure; caller-controlled exception text is never public."""

    def __init__(self, code: str) -> None:
        if code not in COMMON_ERRORS:
            raise ValueError("unregistered application error code")
        self.spec = COMMON_ERRORS[code]
        super().__init__(code)
