import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";
import { parseProjectMember, ProjectMemberReadError,
  type ProjectMemberView } from "./projectMemberReadClient";

export type ProjectMemberStateAction = "suspend" | "resume" | "remove";
export interface ProjectMemberStateFirstReceipt {
  readonly first_result: ProjectMemberView;
  readonly is_current_state_proof: false;
}

const messages = {
  PROJECT_MEMBER_STATE_INVALID_INPUT: "请重新读取成员及版本后再操作。",
  AUTH_RELOGIN_REQUIRED: "更改成员状态前请重新登录。",
  AUTH_CLIENT_BUSY: "正在处理会话操作，请稍候。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许更改项目成员状态。",
  RESOURCE_NOT_FOUND: "成员不存在或当前账户无权操作。",
  PROJECT_ARCHIVED: "项目已归档，无法更改成员。",
  PROJECT_ROLE_INVALID: "当前负责人或部门约束不允许此操作。",
  CONFLICT_VERSION: "成员信息已变化，请重新读取后再决定。",
  CONFLICT_STATE: "成员状态已变化，请重新读取后再决定。",
  CONFLICT_IDEMPOTENCY: "原操作记录与请求不一致，已停止重试。",
  PROJECT_MEMBER_STATE_UNCERTAIN: "状态修改结果无法确认；保留原操作记录和版本，先核对成员历史与审计。",
} as const;
export type ProjectMemberStateErrorCode = keyof typeof messages;
export class ProjectMemberStateError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: ProjectMemberStateErrorCode) {
    super(messages[code]); this.name = "ProjectMemberStateError";
    this.uncertain = code === "PROJECT_MEMBER_STATE_UNCERTAIN";
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
  const prior = Number(etag.slice(2, -1));
  return Number.isSafeInteger(prior) && prior < Number.MAX_SAFE_INTEGER ? prior : null;
}
function prepare(projectId: string, before: ProjectMemberView,
  action: ProjectMemberStateAction, key: string): { before: ProjectMemberView; expectedEtag: string } {
  if (!identifier(projectId) || (action !== "suspend" && action !== "resume" && action !== "remove")
    || typeof key !== "string" || !/^[\x20-\x7e]{16,128}$/.test(key)) {
    throw new ProjectMemberStateError("PROJECT_MEMBER_STATE_INVALID_INPUT");
  }
  let current: ProjectMemberView;
  try { current = parseProjectMember(before); }
  catch { throw new ProjectMemberStateError("PROJECT_MEMBER_STATE_INVALID_INPUT"); }
  const prior = version(current.etag);
  if (prior === null || prior >= Number.MAX_SAFE_INTEGER - 1
    || (action === "suspend" && current.state !== "ACTIVE")
    || (action === "resume" && current.state !== "SUSPENDED")
    || (action === "remove" && current.state === "REMOVED")) {
    throw new ProjectMemberStateError("PROJECT_MEMBER_STATE_INVALID_INPUT");
  }
  return { before: current, expectedEtag: `"v${prior + 1}"` };
}

/** A 200 can be a replay of the first immutable result, never proof of current state. */
export class ProjectMemberStateClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) {
      throw new ProjectMemberStateError("PROJECT_MEMBER_STATE_INVALID_INPUT");
    }
  }

  async change(projectId: string, before: ProjectMemberView,
    action: ProjectMemberStateAction, key: string): Promise<ProjectMemberStateFirstReceipt> {
    const request = prepare(projectId, before, action, key);
    let response: Response;
    try {
      response = await this.session.postProjectMemberState(
        projectId, request.before.member_id, action, request.before.etag, key,
      );
    } catch (failure) {
      if (failure instanceof SessionClientError && failure.code === "AUTH_RELOGIN_REQUIRED") {
        throw new ProjectMemberStateError("AUTH_RELOGIN_REQUIRED");
      }
      if (failure instanceof SessionClientError && failure.code === "AUTH_CLIENT_BUSY") {
        throw new ProjectMemberStateError("AUTH_CLIENT_BUSY");
      }
      throw new ProjectMemberStateError("PROJECT_MEMBER_STATE_UNCERTAIN");
    }
    try {
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
        throw new ProjectMemberStateError("PROJECT_MEMBER_STATE_UNCERTAIN");
      }
      const payload: unknown = await response.json();
      if (!record(payload) || !identifier(payload.trace_id)) {
        throw new ProjectMemberStateError("PROJECT_MEMBER_STATE_UNCERTAIN");
      }
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const known: Record<string, number> = {
          AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403, LICENSE_OPERATION_DENIED: 403,
          RESOURCE_NOT_FOUND: 404, PROJECT_ARCHIVED: 409, PROJECT_ROLE_INVALID: 422,
          CONFLICT_VERSION: 409, CONFLICT_STATE: 409, CONFLICT_IDEMPOTENCY: 409,
          REQUEST_MALFORMED: 400, VALIDATION_FAILED: 422, CONFLICT_VERSION_REQUIRED: 428,
        };
        if (typeof code === "string" && Object.hasOwn(known, code) && known[code] === response.status) {
          throw new ProjectMemberStateError(["REQUEST_MALFORMED", "VALIDATION_FAILED",
            "CONFLICT_VERSION_REQUIRED"].includes(code)
            ? "PROJECT_MEMBER_STATE_INVALID_INPUT" : code as ProjectMemberStateErrorCode);
        }
        throw new ProjectMemberStateError("PROJECT_MEMBER_STATE_UNCERTAIN");
      }
      const first = parseProjectMember(payload.data);
      const expectedState = action === "suspend" ? "SUSPENDED" : action === "resume" ? "ACTIVE" : "REMOVED";
      if (first.member_id !== request.before.member_id
        || first.user.user_id !== request.before.user.user_id
        || first.role !== request.before.role
        || first.department.department_id !== request.before.department.department_id
        || first.effective_at !== request.before.effective_at
        || first.state !== expectedState
        || (action === "remove" && (first.ended_at === null
          || Date.parse(first.ended_at) < Date.parse(first.effective_at)))
        || (action !== "remove" && first.ended_at !== null)
        || first.etag !== request.expectedEtag
        || response.headers.get("etag") !== request.expectedEtag) {
        throw new ProjectMemberStateError("PROJECT_MEMBER_STATE_UNCERTAIN");
      }
      return Object.freeze({ first_result: first, is_current_state_proof: false as const });
    } catch (failure) {
      if (failure instanceof ProjectMemberStateError) throw failure;
      if (failure instanceof ProjectMemberReadError) {
        throw new ProjectMemberStateError("PROJECT_MEMBER_STATE_UNCERTAIN");
      }
      throw new ProjectMemberStateError("PROJECT_MEMBER_STATE_UNCERTAIN");
    }
  }
}
