import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";
import { parseProjectMember, ProjectMemberReadError,
  type ProjectMemberView } from "./projectMemberReadClient";

export interface ProjectMemberPatchInput {
  readonly role?: ProjectMemberView["role"];
  readonly department_id?: string;
}

const messages = {
  PROJECT_MEMBER_PATCH_INVALID_INPUT: "请检查当前成员、目标角色和部门。",
  AUTH_RELOGIN_REQUIRED: "修改成员前请重新登录。",
  AUTH_CLIENT_BUSY: "正在处理会话操作，请稍候。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许修改项目成员。",
  RESOURCE_NOT_FOUND: "成员不存在或当前账户无权修改。",
  PROJECT_ARCHIVED: "项目已归档，无法修改成员。",
  PROJECT_ROLE_INVALID: "目标角色或部门不符合要求。",
  CONFLICT_VERSION: "成员信息已变化，请重新读取后再决定。",
  PROJECT_MEMBER_PATCH_UNCERTAIN: "成员修改结果无法确认。请重新读取成员历史，勿直接重试。",
} as const;
export type ProjectMemberPatchErrorCode = keyof typeof messages;
export class ProjectMemberPatchError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: ProjectMemberPatchErrorCode) {
    super(messages[code]); this.name = "ProjectMemberPatchError";
    this.uncertain = code === "PROJECT_MEMBER_PATCH_UNCERTAIN";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const roles = new Set(["PROJECT_MANAGER", "IMPLEMENTATION_MEMBER", "CUSTOMER_MANAGER", "CUSTOMER_MEMBER"]);
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function identifier(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value) && value !== "00000000-0000-0000-0000-000000000000";
}
function version(etag: string): number | null {
  if (!/^"v(0|[1-9][0-9]*)"$/.test(etag)) return null;
  const number = Number(etag.slice(2, -1));
  return Number.isSafeInteger(number) && number < Number.MAX_SAFE_INTEGER ? number : null;
}
function prepare(projectId: string, before: ProjectMemberView,
  input: ProjectMemberPatchInput): { before: ProjectMemberView; body: string; changed: boolean } {
  if (!identifier(projectId) || typeof input !== "object" || input === null || Array.isArray(input)
    || Object.keys(input).length === 0
    || Object.keys(input).some((key) => key !== "role" && key !== "department_id")) {
    throw new ProjectMemberPatchError("PROJECT_MEMBER_PATCH_INVALID_INPUT");
  }
  let current: ProjectMemberView;
  try { current = parseProjectMember(before); }
  catch { throw new ProjectMemberPatchError("PROJECT_MEMBER_PATCH_INVALID_INPUT"); }
  if (current.state === "REMOVED" || version(current.etag) === null
    || (input.role !== undefined && !roles.has(input.role))
    || (input.department_id !== undefined && !identifier(input.department_id))
    || (input.role === undefined && input.department_id === undefined)) {
    throw new ProjectMemberPatchError("PROJECT_MEMBER_PATCH_INVALID_INPUT");
  }
  const body: Record<string, string> = {};
  if (input.role !== undefined) body.role = input.role;
  if (input.department_id !== undefined) body.department_id = input.department_id;
  return { before: current, body: JSON.stringify(body),
    changed: (input.role !== undefined && input.role !== current.role)
      || (input.department_id !== undefined && input.department_id !== current.department.department_id) };
}

export class ProjectMemberPatchClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) {
      throw new ProjectMemberPatchError("PROJECT_MEMBER_PATCH_INVALID_INPUT");
    }
  }

  async patch(projectId: string, before: ProjectMemberView,
    input: ProjectMemberPatchInput): Promise<ProjectMemberView> {
    const request = prepare(projectId, before, input);
    let response: Response;
    try {
      response = await this.session.patchProjectMember(
        projectId, request.before.member_id, request.before.etag, request.body,
      );
    } catch (failure) {
      if (failure instanceof SessionClientError && failure.code === "AUTH_RELOGIN_REQUIRED") {
        throw new ProjectMemberPatchError("AUTH_RELOGIN_REQUIRED");
      }
      if (failure instanceof SessionClientError && failure.code === "AUTH_CLIENT_BUSY") {
        throw new ProjectMemberPatchError("AUTH_CLIENT_BUSY");
      }
      throw new ProjectMemberPatchError("PROJECT_MEMBER_PATCH_UNCERTAIN");
    }
    try {
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
        throw new ProjectMemberPatchError("PROJECT_MEMBER_PATCH_UNCERTAIN");
      }
      const payload: unknown = await response.json();
      if (!record(payload) || !identifier(payload.trace_id)) {
        throw new ProjectMemberPatchError("PROJECT_MEMBER_PATCH_UNCERTAIN");
      }
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const expected: Record<string, number> = {
          AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403, LICENSE_OPERATION_DENIED: 403,
          RESOURCE_NOT_FOUND: 404, PROJECT_ARCHIVED: 409, PROJECT_ROLE_INVALID: 422,
          CONFLICT_VERSION: 409, VALIDATION_FAILED: 422, REQUEST_MALFORMED: 400,
        };
        if (typeof code === "string" && Object.hasOwn(expected, code) && expected[code] === response.status) {
          throw new ProjectMemberPatchError(code === "VALIDATION_FAILED" || code === "REQUEST_MALFORMED"
            ? "PROJECT_MEMBER_PATCH_INVALID_INPUT" : code as ProjectMemberPatchErrorCode);
        }
        throw new ProjectMemberPatchError("PROJECT_MEMBER_PATCH_UNCERTAIN");
      }
      const member = parseProjectMember(payload.data);
      const expectedVersion = version(request.before.etag);
      const actualVersion = version(member.etag);
      if (member.member_id !== request.before.member_id
        || member.user.user_id !== request.before.user.user_id
        || member.state !== request.before.state
        || member.effective_at !== request.before.effective_at
        || member.ended_at !== request.before.ended_at
        || member.role !== (input.role ?? request.before.role)
        || member.department.department_id !== (input.department_id ?? request.before.department.department_id)
        || expectedVersion === null || actualVersion === null
        || actualVersion !== expectedVersion + (request.changed ? 1 : 0)
        || response.headers.get("etag") !== member.etag) {
        throw new ProjectMemberPatchError("PROJECT_MEMBER_PATCH_UNCERTAIN");
      }
      return member;
    } catch (failure) {
      if (failure instanceof ProjectMemberPatchError) throw failure;
      if (failure instanceof ProjectMemberReadError) {
        throw new ProjectMemberPatchError("PROJECT_MEMBER_PATCH_UNCERTAIN");
      }
      throw new ProjectMemberPatchError("PROJECT_MEMBER_PATCH_UNCERTAIN");
    }
  }
}
