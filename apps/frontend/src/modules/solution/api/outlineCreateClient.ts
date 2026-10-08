/** Frozen SOL_OUTLINE_CREATE transport; an uncertain response must retain its original key. */
import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";
import type { OutlineSummary } from "./outlineReadClient";

const messages = {
  OUTLINE_CREATE_INVALID: "项目、目录名称或操作号无效。",
  OUTLINE_CREATE_UNCERTAIN: "创建结果无法确认；请保留原操作号，勿换号重试。",
  AUTH_RELOGIN_REQUIRED: "请重新登录。",
  AUTH_CLIENT_BUSY: "账户操作进行中，请稍候。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许创建目录。",
  RESOURCE_NOT_FOUND: "项目不存在或无权访问。",
  PROJECT_ARCHIVED: "项目已归档，不可创建目录。",
  VALIDATION_FAILED: "目录名称不符合要求。",
  CONFLICT_IDEMPOTENCY: "操作号已用于不同内容；请核对历史。",
  SYSTEM_UNAVAILABLE: "服务暂不可用，请核对原操作。",
} as const;
export type OutlineCreateErrorCode = keyof typeof messages;
export class OutlineCreateError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: OutlineCreateErrorCode) {
    super(messages[code]); this.name = "OutlineCreateError";
    this.uncertain = code === "OUTLINE_CREATE_UNCERTAIN";
  }
}
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const stamp = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/;
function id(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value) && value !== "00000000-0000-0000-0000-000000000000";
}
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function exact(value: Record<string, unknown>, keys: readonly string[]): boolean {
  return Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
}
function invalid(): never { throw new OutlineCreateError("OUTLINE_CREATE_INVALID"); }
function uncertain(): never { throw new OutlineCreateError("OUTLINE_CREATE_UNCERTAIN"); }
export function normalizeOutlineName(value: unknown): string {
  if (typeof value !== "string") invalid();
  const result = value.normalize("NFKC").trim();
  if (result.length < 1 || result.length > 500 || /\p{C}/u.test(result)) invalid();
  return result;
}

export class OutlineCreateClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) invalid();
  }
  async create(projectId: string, name: string, key: string): Promise<OutlineSummary> {
    if (!id(projectId) || typeof key !== "string" || !/^[\x20-\x7e]{16,128}$/.test(key)
      || name !== normalizeOutlineName(name)) invalid();
    const view = this.session.view;
    if (!view || view.password_change_required || !this.session.canSubmit
      || !view.authorized_projects.some(item => item.project_id === projectId
        && (item.role === "PROJECT_MANAGER" || item.role === "IMPLEMENTATION_MEMBER"))) invalid();
    let response: Response;
    try { response = await this.session.postProjectOutlineCreate(projectId, JSON.stringify({ name }), key); }
    catch (failure) {
      if (failure instanceof SessionClientError
        && (failure.code === "AUTH_RELOGIN_REQUIRED" || failure.code === "AUTH_CLIENT_BUSY")) {
        throw new OutlineCreateError(failure.code);
      }
      return uncertain();
    }
    try {
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") uncertain();
      const payload: unknown = await response.json();
      if (!record(payload) || !id(payload.trace_id)) uncertain();
      if (response.status !== 201) {
        const code = record(payload.error) ? payload.error.code : null;
        const statuses: Readonly<Record<string, number>> = { AUTH_SESSION_EXPIRED: 401,
          AUTH_CSRF_INVALID: 403, LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404,
          PROJECT_ARCHIVED: 409, VALIDATION_FAILED: 422, CONFLICT_IDEMPOTENCY: 409,
          SYSTEM_UNAVAILABLE: 503 };
        if (typeof code === "string" && statuses[code] === response.status) {
          throw new OutlineCreateError(code as OutlineCreateErrorCode);
        }
        uncertain();
      }
      if (!exact(payload, ["data", "trace_id"]) || !record(payload.data)) uncertain();
      const value = payload.data;
      if (!exact(value, ["solution_outline_id", "project_id", "name", "outline_state",
        "current_approved_version_ref", "created_at", "etag"])
        || !id(value.solution_outline_id) || value.project_id !== projectId || value.name !== name
        || value.outline_state !== "ACTIVE" || value.current_approved_version_ref !== null
        || typeof value.created_at !== "string" || !stamp.test(value.created_at)
        || !Number.isFinite(Date.parse(value.created_at)) || value.etag !== '"v0"'
        || response.headers.get("etag") !== '"v0"'
        || response.headers.get("location") !== `/api/v1/projects/${projectId}/solution-outlines/${value.solution_outline_id}`
        || response.headers.get("x-trace-id") !== payload.trace_id) uncertain();
      return Object.freeze({ ...value }) as unknown as OutlineSummary;
    } catch (failure) {
      if (failure instanceof OutlineCreateError) throw failure;
      return uncertain();
    }
  }
}
