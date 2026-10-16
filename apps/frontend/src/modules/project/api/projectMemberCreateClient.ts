import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";
import { parseProjectMember, ProjectMemberReadError, type ProjectMemberView } from "./projectMemberReadClient";

export interface ProjectMemberCreateInput {
  readonly user_id: string;
  readonly role: ProjectMemberView["role"];
  readonly department_id: string;
  readonly effective_at?: string;
}

const messages = {
  PROJECT_MEMBER_CREATE_INVALID_INPUT: "请检查目标用户、成员角色、部门和生效时间。",
  AUTH_RELOGIN_REQUIRED: "提交成员前请重新登录。",
  AUTH_CLIENT_BUSY: "正在处理会话操作，请稍候。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许创建项目成员。",
  RESOURCE_NOT_FOUND: "项目不存在或当前账户无权添加成员。",
  PROJECT_ARCHIVED: "项目已归档，无法添加成员。",
  PROJECT_ROLE_INVALID: "目标用户、角色或部门不符合要求。",
  PROJECT_USER_ALREADY_ASSIGNED: "目标用户已属于其他项目。",
  CONFLICT_IDEMPOTENCY: "原操作记录与本次输入不一致，已停止重试。",
  PROJECT_MEMBER_CREATE_UNCERTAIN: "成员创建结果无法确认。请勿使用新操作标识重复创建。",
} as const;
export type ProjectMemberCreateErrorCode = keyof typeof messages;

export class ProjectMemberCreateError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: ProjectMemberCreateErrorCode) {
    super(messages[code]);
    this.name = "ProjectMemberCreateError";
    this.uncertain = code === "PROJECT_MEMBER_CREATE_UNCERTAIN";
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
function instant(value: unknown): value is string {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/.test(value)) return false;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) && new Date(parsed).toISOString().slice(0, 19) === value.slice(0, 19);
}
function sameInstant(left: string, right: string): boolean {
  const parts = (value: string) => {
    const [whole, fraction = ""] = value.slice(0, -1).split(".");
    return `${whole}.${fraction.padEnd(6, "0")}`;
  };
  return parts(left) === parts(right);
}
function request(projectId: string, input: ProjectMemberCreateInput, key: string): string {
  if (!identifier(projectId) || !record(input) || !identifier(input.user_id)
    || !roles.has(input.role) || !identifier(input.department_id)
    || (input.effective_at !== undefined && !instant(input.effective_at))
    || typeof key !== "string" || !/^[\x20-\x7e]{16,128}$/.test(key)) {
    throw new ProjectMemberCreateError("PROJECT_MEMBER_CREATE_INVALID_INPUT");
  }
  const body: Record<string, string> = {
    user_id: input.user_id, role: input.role, department_id: input.department_id,
  };
  if (input.effective_at !== undefined) body.effective_at = input.effective_at;
  return JSON.stringify(body);
}

export class ProjectMemberCreateClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) {
      throw new ProjectMemberCreateError("PROJECT_MEMBER_CREATE_INVALID_INPUT");
    }
  }

  async create(projectId: string, input: ProjectMemberCreateInput, key: string): Promise<ProjectMemberView> {
    const body = request(projectId, input, key);
    let response: Response;
    try {
      response = await this.session.postProjectMemberCreate(projectId, body, key);
    } catch (failure) {
      if (failure instanceof SessionClientError && failure.code === "AUTH_RELOGIN_REQUIRED") {
        throw new ProjectMemberCreateError("AUTH_RELOGIN_REQUIRED");
      }
      if (failure instanceof SessionClientError && failure.code === "AUTH_CLIENT_BUSY") {
        throw new ProjectMemberCreateError("AUTH_CLIENT_BUSY");
      }
      throw new ProjectMemberCreateError("PROJECT_MEMBER_CREATE_UNCERTAIN");
    }
    try {
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
        throw new ProjectMemberCreateError("PROJECT_MEMBER_CREATE_UNCERTAIN");
      }
      const payload: unknown = await response.json();
      if (!record(payload) || !identifier(payload.trace_id)) {
        throw new ProjectMemberCreateError("PROJECT_MEMBER_CREATE_UNCERTAIN");
      }
      if (response.status !== 201) {
        const code = record(payload.error) ? payload.error.code : null;
        const expected: Record<string, number> = {
          AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403, LICENSE_OPERATION_DENIED: 403,
          RESOURCE_NOT_FOUND: 404, PROJECT_ARCHIVED: 409, PROJECT_ROLE_INVALID: 422,
          PROJECT_USER_ALREADY_ASSIGNED: 409, CONFLICT_IDEMPOTENCY: 409,
          VALIDATION_FAILED: 422, REQUEST_MALFORMED: 400,
        };
        if (typeof code === "string" && Object.hasOwn(expected, code) && response.status === expected[code]) {
          throw new ProjectMemberCreateError(code === "VALIDATION_FAILED" || code === "REQUEST_MALFORMED"
            ? "PROJECT_MEMBER_CREATE_INVALID_INPUT" : code as ProjectMemberCreateErrorCode);
        }
        throw new ProjectMemberCreateError("PROJECT_MEMBER_CREATE_UNCERTAIN");
      }
      const member = parseProjectMember(payload.data);
      if (member.user.user_id !== input.user_id || member.role !== input.role
        || member.department.department_id !== input.department_id
        || member.state !== "ACTIVE" || member.ended_at !== null || member.etag !== '"v0"'
        || (input.effective_at !== undefined && !sameInstant(member.effective_at, input.effective_at))
        || response.headers.get("etag") !== member.etag
        || response.headers.get("location") !== `/api/v1/projects/${projectId}/members/${member.member_id}`) {
        throw new ProjectMemberCreateError("PROJECT_MEMBER_CREATE_UNCERTAIN");
      }
      return member;
    } catch (failure) {
      if (failure instanceof ProjectMemberCreateError) throw failure;
      if (failure instanceof ProjectMemberReadError) throw new ProjectMemberCreateError("PROJECT_MEMBER_CREATE_UNCERTAIN");
      throw new ProjectMemberCreateError("PROJECT_MEMBER_CREATE_UNCERTAIN");
    }
  }
}
