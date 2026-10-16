import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";
import { parseProjectDepartment, ProjectDepartmentReadError,
  type ProjectDepartmentView } from "./projectDepartmentReadClient";

export interface ProjectDepartmentCreateInput {
  readonly code: string;
  readonly name: string;
}
export interface ProjectDepartmentCreateFirstReceipt {
  readonly first_result: ProjectDepartmentView;
  readonly is_current_state_proof: false;
}

const messages = {
  PROJECT_DEPARTMENT_CREATE_INVALID_INPUT: "请检查部门编号和名称。",
  AUTH_RELOGIN_REQUIRED: "创建部门前请重新登录。",
  AUTH_CLIENT_BUSY: "正在处理会话操作，请稍候。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许创建项目部门。",
  RESOURCE_NOT_FOUND: "项目不存在或当前账户无权创建部门。",
  PROJECT_ARCHIVED: "项目已归档，无法创建部门。",
  CONFLICT_DUPLICATE: "部门编号已存在。",
  CONFLICT_IDEMPOTENCY: "原操作记录与本次输入不一致，已停止重试。",
  PROJECT_DEPARTMENT_CREATE_UNCERTAIN: "部门创建结果无法确认。请保留原输入和操作记录，勿生成新操作重复创建。",
} as const;
export type ProjectDepartmentCreateErrorCode = keyof typeof messages;
export class ProjectDepartmentCreateError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: ProjectDepartmentCreateErrorCode) {
    super(messages[code]); this.name = "ProjectDepartmentCreateError";
    this.uncertain = code === "PROJECT_DEPARTMENT_CREATE_UNCERTAIN";
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
function normalized(value: unknown, max: number): string {
  if (typeof value !== "string") throw new ProjectDepartmentCreateError("PROJECT_DEPARTMENT_CREATE_INVALID_INPUT");
  const result = value.normalize("NFKC").trim();
  if (result.length < 1 || result.length > max || /\p{C}/u.test(result)) {
    throw new ProjectDepartmentCreateError("PROJECT_DEPARTMENT_CREATE_INVALID_INPUT");
  }
  return result;
}
function request(projectId: string, input: ProjectDepartmentCreateInput, key: string) {
  if (!identifier(projectId) || !record(input) || typeof key !== "string"
    || !/^[\x20-\x7e]{16,128}$/.test(key)) {
    throw new ProjectDepartmentCreateError("PROJECT_DEPARTMENT_CREATE_INVALID_INPUT");
  }
  const code = normalized(input.code, 64);
  const name = normalized(input.name, 255);
  return { body: JSON.stringify({ code, name }), code, name };
}

/** A 201 can replay the immutable first response; the caller must re-read current history. */
export class ProjectDepartmentCreateClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) {
      throw new ProjectDepartmentCreateError("PROJECT_DEPARTMENT_CREATE_INVALID_INPUT");
    }
  }

  async create(projectId: string, input: ProjectDepartmentCreateInput,
    key: string): Promise<ProjectDepartmentCreateFirstReceipt> {
    const prepared = request(projectId, input, key);
    let response: Response;
    try {
      response = await this.session.postProjectDepartmentCreate(projectId, prepared.body, key);
    } catch (failure) {
      if (failure instanceof SessionClientError && failure.code === "AUTH_RELOGIN_REQUIRED") {
        throw new ProjectDepartmentCreateError("AUTH_RELOGIN_REQUIRED");
      }
      if (failure instanceof SessionClientError && failure.code === "AUTH_CLIENT_BUSY") {
        throw new ProjectDepartmentCreateError("AUTH_CLIENT_BUSY");
      }
      throw new ProjectDepartmentCreateError("PROJECT_DEPARTMENT_CREATE_UNCERTAIN");
    }
    try {
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
        throw new ProjectDepartmentCreateError("PROJECT_DEPARTMENT_CREATE_UNCERTAIN");
      }
      const payload: unknown = await response.json();
      if (!record(payload) || !identifier(payload.trace_id)) {
        throw new ProjectDepartmentCreateError("PROJECT_DEPARTMENT_CREATE_UNCERTAIN");
      }
      if (response.status !== 201) {
        const code = record(payload.error) ? payload.error.code : null;
        const expected: Record<string, number> = {
          AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403, LICENSE_OPERATION_DENIED: 403,
          RESOURCE_NOT_FOUND: 404, PROJECT_ARCHIVED: 409, CONFLICT_DUPLICATE: 409,
          CONFLICT_IDEMPOTENCY: 409, VALIDATION_FAILED: 422, REQUEST_MALFORMED: 400,
        };
        if (typeof code === "string" && Object.hasOwn(expected, code) && response.status === expected[code]) {
          throw new ProjectDepartmentCreateError(code === "VALIDATION_FAILED" || code === "REQUEST_MALFORMED"
            ? "PROJECT_DEPARTMENT_CREATE_INVALID_INPUT" : code as ProjectDepartmentCreateErrorCode);
        }
        throw new ProjectDepartmentCreateError("PROJECT_DEPARTMENT_CREATE_UNCERTAIN");
      }
      const department = parseProjectDepartment(payload.data);
      if (department.state !== "ACTIVE" || department.etag !== '"v0"'
        || department.code !== prepared.code || department.name !== prepared.name
        || response.headers.get("etag") !== department.etag
        || response.headers.get("location") !== `/api/v1/projects/${projectId}/departments/${department.department_id}`) {
        throw new ProjectDepartmentCreateError("PROJECT_DEPARTMENT_CREATE_UNCERTAIN");
      }
      return Object.freeze({ first_result: department, is_current_state_proof: false });
    } catch (failure) {
      if (failure instanceof ProjectDepartmentCreateError) throw failure;
      if (failure instanceof ProjectDepartmentReadError) {
        throw new ProjectDepartmentCreateError("PROJECT_DEPARTMENT_CREATE_UNCERTAIN");
      }
      throw new ProjectDepartmentCreateError("PROJECT_DEPARTMENT_CREATE_UNCERTAIN");
    }
  }
}
