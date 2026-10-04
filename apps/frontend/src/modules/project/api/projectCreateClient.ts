import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";
import { parseProject, ProjectReadError, type ProjectView } from "./projectReadClient";

export interface ProjectCreateInput {
  readonly code: string;
  readonly name: string;
  readonly initial_manager_user_id: string;
  readonly department?: Readonly<{ code: string; name: string }>;
}

const messages = {
  PROJECT_CREATE_INVALID_INPUT: "请检查项目、负责人和部门信息。",
  AUTH_RELOGIN_REQUIRED: "提交项目前请重新登录。",
  AUTH_CLIENT_BUSY: "正在处理会话操作，请稍候。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许创建项目。",
  RESOURCE_NOT_FOUND: "当前账户无权创建项目。",
  PROJECT_ROLE_INVALID: "首位项目负责人不符合要求。",
  PROJECT_USER_ALREADY_ASSIGNED: "首位负责人已属于其他项目。",
  CONFLICT_DUPLICATE: "项目编号已存在。",
  CONFLICT_IDEMPOTENCY: "原操作记录与本次输入不一致，已停止重试。",
  PROJECT_CREATE_UNCERTAIN: "项目创建结果无法确认。请勿使用新操作标识重复创建。",
} as const;
export type ProjectCreateErrorCode = keyof typeof messages;

export class ProjectCreateError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: ProjectCreateErrorCode) {
    super(messages[code]);
    this.name = "ProjectCreateError";
    this.uncertain = code === "PROJECT_CREATE_UNCERTAIN";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function identifier(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value) && value !== "00000000-0000-0000-0000-000000000000";
}
function normalized(value: unknown, max: number): string {
  if (typeof value !== "string") throw new ProjectCreateError("PROJECT_CREATE_INVALID_INPUT");
  const result = value.normalize("NFKC").trim();
  if (result.length < 1 || result.length > max || /\p{C}/u.test(result)) {
    throw new ProjectCreateError("PROJECT_CREATE_INVALID_INPUT");
  }
  return result;
}
function request(input: ProjectCreateInput): { body: string; code: string; name: string } {
  if (!record(input) || !identifier(input.initial_manager_user_id)) {
    throw new ProjectCreateError("PROJECT_CREATE_INVALID_INPUT");
  }
  const code = normalized(input.code, 64);
  const name = normalized(input.name, 255);
  const body: Record<string, unknown> = { code, name,
    initial_manager_user_id: input.initial_manager_user_id };
  if (input.department !== undefined) {
    if (!record(input.department)) throw new ProjectCreateError("PROJECT_CREATE_INVALID_INPUT");
    body.department = { code: normalized(input.department.code, 64),
      name: normalized(input.department.name, 255) };
  }
  return { body: JSON.stringify(body), code, name };
}

export class ProjectCreateClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) throw new ProjectCreateError("PROJECT_CREATE_INVALID_INPUT");
  }

  async create(input: ProjectCreateInput, idempotencyKey: string): Promise<ProjectView> {
    const prepared = request(input);
    if (typeof idempotencyKey !== "string" || !/^[\x20-\x7e]{16,128}$/.test(idempotencyKey)) {
      throw new ProjectCreateError("PROJECT_CREATE_INVALID_INPUT");
    }
    let response: Response;
    try {
      response = await this.session.postProjectCreate(prepared.body, idempotencyKey);
    } catch (failure) {
      if (failure instanceof SessionClientError && failure.code === "AUTH_RELOGIN_REQUIRED") {
        throw new ProjectCreateError("AUTH_RELOGIN_REQUIRED");
      }
      if (failure instanceof SessionClientError && failure.code === "AUTH_CLIENT_BUSY") {
        throw new ProjectCreateError("AUTH_CLIENT_BUSY");
      }
      throw new ProjectCreateError("PROJECT_CREATE_UNCERTAIN");
    }
    try {
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
        throw new ProjectCreateError("PROJECT_CREATE_UNCERTAIN");
      }
      const payload: unknown = await response.json();
      if (!record(payload) || !identifier(payload.trace_id)) {
        throw new ProjectCreateError("PROJECT_CREATE_UNCERTAIN");
      }
      if (response.status !== 201) {
        const code = record(payload.error) ? payload.error.code : null;
        const expected: Record<string, number> = {
          AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403, LICENSE_OPERATION_DENIED: 403,
          RESOURCE_NOT_FOUND: 404, PROJECT_ROLE_INVALID: 422,
          PROJECT_USER_ALREADY_ASSIGNED: 409, CONFLICT_DUPLICATE: 409,
          CONFLICT_IDEMPOTENCY: 409, VALIDATION_FAILED: 422, REQUEST_MALFORMED: 400,
        };
        if (typeof code === "string" && Object.hasOwn(expected, code) && response.status === expected[code]) {
          throw new ProjectCreateError(code === "VALIDATION_FAILED" || code === "REQUEST_MALFORMED"
            ? "PROJECT_CREATE_INVALID_INPUT" : code as ProjectCreateErrorCode);
        }
        throw new ProjectCreateError("PROJECT_CREATE_UNCERTAIN");
      }
      const project = parseProject(payload.data);
      if (project.state !== "ACTIVE" || project.etag !== '"v0"'
        || project.code !== prepared.code || project.name !== prepared.name
        || response.headers.get("etag") !== project.etag
        || response.headers.get("location") !== `/api/v1/projects/${project.project_id}`) {
        throw new ProjectCreateError("PROJECT_CREATE_UNCERTAIN");
      }
      return project;
    } catch (failure) {
      if (failure instanceof ProjectCreateError) throw failure;
      if (failure instanceof ProjectReadError) throw new ProjectCreateError("PROJECT_CREATE_UNCERTAIN");
      throw new ProjectCreateError("PROJECT_CREATE_UNCERTAIN");
    }
  }
}
