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
    "REQUEST_MALFORMED": ErrorSpec("REQUEST_MALFORMED", 400, "请求格式不正确。"),
    "REQUEST_METHOD_NOT_ALLOWED": ErrorSpec(
        "REQUEST_METHOD_NOT_ALLOWED", 405, "此操作不支持该请求方法。"
    ),
    "AUTH_REQUIRED": ErrorSpec("AUTH_REQUIRED", 401, "请先登录。"),
    "AUTH_INVALID_CREDENTIALS": ErrorSpec("AUTH_INVALID_CREDENTIALS", 401, "用户名或密码不正确。"),
    "AUTH_SESSION_EXPIRED": ErrorSpec("AUTH_SESSION_EXPIRED", 401, "登录已失效。"),
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
    "VALIDATION_FAILED": ErrorSpec("VALIDATION_FAILED", 422, "请求内容不符合要求。"),
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
    "PROJECT_DEPARTMENT_IN_USE": ErrorSpec(
        "PROJECT_DEPARTMENT_IN_USE", 409, "部门仍有在用成员，不能停用。"
    ),
}


class ApplicationError(Exception):
    """A classified failure; caller-controlled exception text is never public."""

    def __init__(self, code: str) -> None:
        if code not in COMMON_ERRORS:
            raise ValueError("unregistered application error code")
        self.spec = COMMON_ERRORS[code]
        super().__init__(code)
