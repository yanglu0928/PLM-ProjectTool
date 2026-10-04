import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";
import { parseProjectDepartment, ProjectDepartmentReadError,
  type ProjectDepartmentView } from "./projectDepartmentReadClient";

export interface ProjectDepartmentDeactivateFirstReceipt {
  readonly first_result: ProjectDepartmentView;
  readonly is_current_state_proof: false;
}

const messages = {
  PROJECT_DEPARTMENT_DEACTIVATE_INVALID_INPUT: "请重新读取部门及版本后再操作。",
  AUTH_RELOGIN_REQUIRED: "停用部门前请重新登录。",
  AUTH_CLIENT_BUSY: "正在处理会话操作，请稍候。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许停用部门。",
  RESOURCE_NOT_FOUND: "部门不存在或当前账户无权操作。",
  PROJECT_ARCHIVED: "项目已归档，无法停用部门。",
  PROJECT_DEPARTMENT_IN_USE: "仍有成员使用此部门，不能停用。",
  CONFLICT_VERSION: "部门信息已变化，请重新读取后再决定。",
  CONFLICT_STATE: "部门状态已变化，请重新读取后再决定。",
  CONFLICT_IDEMPOTENCY: "原操作记录与请求不一致，已停止重试。",
  PROJECT_DEPARTMENT_DEACTIVATE_UNCERTAIN: "停用结果无法确认；保留原操作记录和版本，先核对部门历史与审计。",
} as const;
export type ProjectDepartmentDeactivateErrorCode = keyof typeof messages;
export class ProjectDepartmentDeactivateError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: ProjectDepartmentDeactivateErrorCode) {
    super(messages[code]); this.name = "ProjectDepartmentDeactivateError";
    this.uncertain = code === "PROJECT_DEPARTMENT_DEACTIVATE_UNCERTAIN";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function identifier(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value)
    && value !== "00000000-0000-0000-0000-000000000000";
}
function version(etag: string): number | null {
  if (!/^"v(0|[1-9][0-9]*)"$/.test(etag)) return null;
  const number = Number(etag.slice(2, -1));
  return Number.isSafeInteger(number) && number < Number.MAX_SAFE_INTEGER ? number : null;
}
function prepare(projectId: string, before: ProjectDepartmentView, key: string) {
  if (!identifier(projectId) || typeof key !== "string" || !/^[\x20-\x7e]{16,128}$/.test(key)) {
    throw new ProjectDepartmentDeactivateError("PROJECT_DEPARTMENT_DEACTIVATE_INVALID_INPUT");
  }
  let current: ProjectDepartmentView;
  try { current = parseProjectDepartment(before); }
  catch { throw new ProjectDepartmentDeactivateError("PROJECT_DEPARTMENT_DEACTIVATE_INVALID_INPUT"); }
  const prior = version(current.etag);
  if (current.state !== "ACTIVE" || prior === null || prior >= Number.MAX_SAFE_INTEGER - 1) {
    throw new ProjectDepartmentDeactivateError("PROJECT_DEPARTMENT_DEACTIVATE_INVALID_INPUT");
  }
  return { before: current, expectedEtag: `"v${prior + 1}"` };
}

/** A replay of the immutable first 200 is never a current-state proof. */
export class ProjectDepartmentDeactivateClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) {
      throw new ProjectDepartmentDeactivateError("PROJECT_DEPARTMENT_DEACTIVATE_INVALID_INPUT");
    }
  }

  async deactivate(projectId: string, before: ProjectDepartmentView,
    key: string): Promise<ProjectDepartmentDeactivateFirstReceipt> {
    const request = prepare(projectId, before, key);
    let response: Response;
    try {
      response = await this.session.postProjectDepartmentDeactivate(
        projectId, request.before.department_id, request.before.etag, key,
      );
    } catch (failure) {
      if (failure instanceof SessionClientError && failure.code === "AUTH_RELOGIN_REQUIRED") {
        throw new ProjectDepartmentDeactivateError("AUTH_RELOGIN_REQUIRED");
      }
      if (failure instanceof SessionClientError && failure.code === "AUTH_CLIENT_BUSY") {
        throw new ProjectDepartmentDeactivateError("AUTH_CLIENT_BUSY");
      }
      throw new ProjectDepartmentDeactivateError("PROJECT_DEPARTMENT_DEACTIVATE_UNCERTAIN");
    }
    try {
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
        throw new ProjectDepartmentDeactivateError("PROJECT_DEPARTMENT_DEACTIVATE_UNCERTAIN");
      }
      const payload: unknown = await response.json();
      if (!record(payload) || !identifier(payload.trace_id)) {
        throw new ProjectDepartmentDeactivateError("PROJECT_DEPARTMENT_DEACTIVATE_UNCERTAIN");
      }
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const known: Record<string, number> = {
          AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403, LICENSE_OPERATION_DENIED: 403,
          RESOURCE_NOT_FOUND: 404, PROJECT_ARCHIVED: 409, PROJECT_DEPARTMENT_IN_USE: 409,
          CONFLICT_VERSION: 409, CONFLICT_STATE: 409, CONFLICT_IDEMPOTENCY: 409,
          REQUEST_MALFORMED: 400, VALIDATION_FAILED: 422, CONFLICT_VERSION_REQUIRED: 428,
        };
        if (typeof code === "string" && Object.hasOwn(known, code) && known[code] === response.status) {
          throw new ProjectDepartmentDeactivateError(["REQUEST_MALFORMED", "VALIDATION_FAILED",
            "CONFLICT_VERSION_REQUIRED"].includes(code)
            ? "PROJECT_DEPARTMENT_DEACTIVATE_INVALID_INPUT" : code as ProjectDepartmentDeactivateErrorCode);
        }
        throw new ProjectDepartmentDeactivateError("PROJECT_DEPARTMENT_DEACTIVATE_UNCERTAIN");
      }
      const first = parseProjectDepartment(payload.data);
      if (first.department_id !== request.before.department_id || first.code !== request.before.code
        || first.name !== request.before.name || first.created_at !== request.before.created_at
        || first.state !== "INACTIVE" || first.etag !== request.expectedEtag
        || response.headers.get("etag") !== request.expectedEtag) {
        throw new ProjectDepartmentDeactivateError("PROJECT_DEPARTMENT_DEACTIVATE_UNCERTAIN");
      }
      return Object.freeze({ first_result: first, is_current_state_proof: false as const });
    } catch (failure) {
      if (failure instanceof ProjectDepartmentDeactivateError) throw failure;
      if (failure instanceof ProjectDepartmentReadError) {
        throw new ProjectDepartmentDeactivateError("PROJECT_DEPARTMENT_DEACTIVATE_UNCERTAIN");
      }
      throw new ProjectDepartmentDeactivateError("PROJECT_DEPARTMENT_DEACTIVATE_UNCERTAIN");
    }
  }
}
