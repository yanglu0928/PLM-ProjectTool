import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";
import { parseProjectDepartment, ProjectDepartmentReadError,
  type ProjectDepartmentView } from "./projectDepartmentReadClient";

export interface ProjectDepartmentPatchInput {
  readonly code?: string;
  readonly name?: string;
}

const messages = {
  PROJECT_DEPARTMENT_PATCH_INVALID_INPUT: "请检查当前部门、编号和名称。",
  AUTH_RELOGIN_REQUIRED: "修改部门前请重新登录。",
  AUTH_CLIENT_BUSY: "正在处理会话操作，请稍候。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许修改部门。",
  RESOURCE_NOT_FOUND: "部门不存在或当前账户无权修改。",
  PROJECT_ARCHIVED: "项目已归档，无法修改部门。",
  CONFLICT_VERSION: "部门信息已变化，请重新读取后再决定。",
  CONFLICT_STATE: "部门已停用，无法普通修改。",
  CONFLICT_DUPLICATE: "部门编号已存在。",
  PROJECT_DEPARTMENT_PATCH_UNCERTAIN: "部门修改结果无法确认。请重新读取部门历史，勿直接重试。",
} as const;
export type ProjectDepartmentPatchErrorCode = keyof typeof messages;
export class ProjectDepartmentPatchError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: ProjectDepartmentPatchErrorCode) {
    super(messages[code]); this.name = "ProjectDepartmentPatchError";
    this.uncertain = code === "PROJECT_DEPARTMENT_PATCH_UNCERTAIN";
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
  const value = Number(etag.slice(2, -1));
  return Number.isSafeInteger(value) && value < Number.MAX_SAFE_INTEGER ? value : null;
}
function normalized(value: unknown, max: number): string {
  if (typeof value !== "string") throw new ProjectDepartmentPatchError("PROJECT_DEPARTMENT_PATCH_INVALID_INPUT");
  const result = value.normalize("NFKC").trim();
  if (result.length < 1 || result.length > max || /\p{C}/u.test(result)) {
    throw new ProjectDepartmentPatchError("PROJECT_DEPARTMENT_PATCH_INVALID_INPUT");
  }
  return result;
}
function prepare(projectId: string, before: ProjectDepartmentView, input: ProjectDepartmentPatchInput) {
  if (!identifier(projectId) || !record(input) || Object.keys(input).length === 0
    || Object.keys(input).some((key) => key !== "code" && key !== "name")) {
    throw new ProjectDepartmentPatchError("PROJECT_DEPARTMENT_PATCH_INVALID_INPUT");
  }
  let current: ProjectDepartmentView;
  try { current = parseProjectDepartment(before); }
  catch { throw new ProjectDepartmentPatchError("PROJECT_DEPARTMENT_PATCH_INVALID_INPUT"); }
  if (current.state !== "ACTIVE" || version(current.etag) === null
    || (input.code === undefined && input.name === undefined)) {
    throw new ProjectDepartmentPatchError("PROJECT_DEPARTMENT_PATCH_INVALID_INPUT");
  }
  const code = input.code === undefined ? undefined : normalized(input.code, 64);
  const name = input.name === undefined ? undefined : normalized(input.name, 255);
  const body = JSON.stringify({ ...(code === undefined ? {} : { code }),
    ...(name === undefined ? {} : { name }) });
  return { before: current, body, code, name,
    changed: (code !== undefined && code !== current.code) || (name !== undefined && name !== current.name) };
}

/** A non-idempotent PATCH success is bound to the request, not a substitute for a fresh history read. */
export class ProjectDepartmentPatchClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) {
      throw new ProjectDepartmentPatchError("PROJECT_DEPARTMENT_PATCH_INVALID_INPUT");
    }
  }

  async patch(projectId: string, before: ProjectDepartmentView,
    input: ProjectDepartmentPatchInput): Promise<ProjectDepartmentView> {
    const request = prepare(projectId, before, input);
    let response: Response;
    try {
      response = await this.session.patchProjectDepartment(
        projectId, request.before.department_id, request.before.etag, request.body,
      );
    } catch (failure) {
      if (failure instanceof SessionClientError && failure.code === "AUTH_RELOGIN_REQUIRED") {
        throw new ProjectDepartmentPatchError("AUTH_RELOGIN_REQUIRED");
      }
      if (failure instanceof SessionClientError && failure.code === "AUTH_CLIENT_BUSY") {
        throw new ProjectDepartmentPatchError("AUTH_CLIENT_BUSY");
      }
      throw new ProjectDepartmentPatchError("PROJECT_DEPARTMENT_PATCH_UNCERTAIN");
    }
    try {
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
        throw new ProjectDepartmentPatchError("PROJECT_DEPARTMENT_PATCH_UNCERTAIN");
      }
      const payload: unknown = await response.json();
      if (!record(payload) || !identifier(payload.trace_id)) {
        throw new ProjectDepartmentPatchError("PROJECT_DEPARTMENT_PATCH_UNCERTAIN");
      }
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const expected: Record<string, number> = {
          AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403, LICENSE_OPERATION_DENIED: 403,
          RESOURCE_NOT_FOUND: 404, PROJECT_ARCHIVED: 409, CONFLICT_VERSION: 409,
          CONFLICT_STATE: 409, CONFLICT_DUPLICATE: 409, VALIDATION_FAILED: 422,
          REQUEST_MALFORMED: 400,
        };
        if (typeof code === "string" && Object.hasOwn(expected, code) && response.status === expected[code]) {
          throw new ProjectDepartmentPatchError(code === "VALIDATION_FAILED" || code === "REQUEST_MALFORMED"
            ? "PROJECT_DEPARTMENT_PATCH_INVALID_INPUT" : code as ProjectDepartmentPatchErrorCode);
        }
        throw new ProjectDepartmentPatchError("PROJECT_DEPARTMENT_PATCH_UNCERTAIN");
      }
      const department = parseProjectDepartment(payload.data);
      const priorVersion = version(request.before.etag);
      if (department.department_id !== request.before.department_id
        || department.created_at !== request.before.created_at || department.state !== "ACTIVE"
        || department.code !== (request.code ?? request.before.code)
        || department.name !== (request.name ?? request.before.name)
        || priorVersion === null || version(department.etag) !== priorVersion + (request.changed ? 1 : 0)
        || response.headers.get("etag") !== department.etag) {
        throw new ProjectDepartmentPatchError("PROJECT_DEPARTMENT_PATCH_UNCERTAIN");
      }
      return department;
    } catch (failure) {
      if (failure instanceof ProjectDepartmentPatchError) throw failure;
      if (failure instanceof ProjectDepartmentReadError) {
        throw new ProjectDepartmentPatchError("PROJECT_DEPARTMENT_PATCH_UNCERTAIN");
      }
      throw new ProjectDepartmentPatchError("PROJECT_DEPARTMENT_PATCH_UNCERTAIN");
    }
  }
}
