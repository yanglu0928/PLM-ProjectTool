/** Frozen SOL_SECTION_CREATE transport; uncertain outcome retains the original operation key. */
import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";
import type { SectionSummary } from "./sectionReadClient";

const messages = {
  SECTION_CREATE_INVALID: "项目、目录、章节键或操作号无效。",
  SECTION_CREATE_UNCERTAIN: "创建结果无法确认；请保留原操作号，勿换号重试。",
  AUTH_RELOGIN_REQUIRED: "请重新登录。",
  AUTH_CLIENT_BUSY: "账户操作进行中，请稍候。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许创建章节。",
  RESOURCE_NOT_FOUND: "项目或目录不存在，或无权访问。",
  PROJECT_ARCHIVED: "项目已归档，不可创建章节。",
  VALIDATION_FAILED: "章节键不符合要求。",
  CONFLICT_IDEMPOTENCY: "操作号已用于不同内容；请核对历史。",
  CONFLICT_DUPLICATE: "章节键已存在；请核对目录章节。",
  SYSTEM_UNAVAILABLE: "服务暂不可用，请核对原操作。",
} as const;
export type SectionCreateErrorCode = keyof typeof messages;
export class SectionCreateError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: SectionCreateErrorCode) {
    super(messages[code]); this.name = "SectionCreateError";
    this.uncertain = code === "SECTION_CREATE_UNCERTAIN";
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
function invalid(): never { throw new SectionCreateError("SECTION_CREATE_INVALID"); }
function uncertain(): never { throw new SectionCreateError("SECTION_CREATE_UNCERTAIN"); }
export function normalizeSectionKey(value: unknown): string {
  if (typeof value !== "string") invalid();
  const result = value.normalize("NFKC").trim();
  if (result.length < 1 || result.length > 128 || /\p{C}/u.test(result)) invalid();
  return result;
}

export class SectionCreateClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) invalid();
  }
  async create(projectId: string, outlineId: string, sectionKey: string,
               operationKey: string): Promise<SectionSummary> {
    if (!id(projectId) || !id(outlineId)
      || typeof operationKey !== "string" || !/^[\x20-\x7e]{16,128}$/.test(operationKey)
      || sectionKey !== normalizeSectionKey(sectionKey)) invalid();
    const view = this.session.view;
    if (!view || view.password_change_required || !this.session.canSubmit
      || !view.authorized_projects.some(item => item.project_id === projectId
        && (item.role === "PROJECT_MANAGER" || item.role === "IMPLEMENTATION_MEMBER"))) invalid();
    let response: Response;
    try { response = await this.session.postProjectSectionCreate(projectId,
      JSON.stringify({ solution_outline_id: outlineId, section_key: sectionKey }), operationKey); }
    catch (failure) {
      if (failure instanceof SessionClientError
        && (failure.code === "AUTH_RELOGIN_REQUIRED" || failure.code === "AUTH_CLIENT_BUSY")) {
        throw new SectionCreateError(failure.code);
      }
      return uncertain();
    }
    try {
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json"
        || response.headers.get("cache-control") !== "no-store") uncertain();
      const payload: unknown = await response.json();
      if (!record(payload) || !id(payload.trace_id)
        || response.headers.get("x-trace-id") !== payload.trace_id) uncertain();
      if (response.status !== 201) {
        const code = record(payload.error) ? payload.error.code : null;
        const statuses: Readonly<Record<string, number>> = { AUTH_SESSION_EXPIRED: 401,
          AUTH_CSRF_INVALID: 403, LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404,
          PROJECT_ARCHIVED: 409, VALIDATION_FAILED: 422, CONFLICT_IDEMPOTENCY: 409,
          CONFLICT_DUPLICATE: 409, SYSTEM_UNAVAILABLE: 503 };
        if (typeof code === "string" && statuses[code] === response.status) {
          throw new SectionCreateError(code as SectionCreateErrorCode);
        }
        uncertain();
      }
      if (!exact(payload, ["data", "trace_id"]) || !record(payload.data)) uncertain();
      const value = payload.data;
      if (!exact(value, ["solution_section_id", "solution_outline_id", "project_id", "section_key",
        "section_state", "current_approved_version_ref", "created_at", "etag"])
        || !id(value.solution_section_id) || value.solution_outline_id !== outlineId
        || value.project_id !== projectId || value.section_key !== sectionKey
        || value.section_state !== "ACTIVE" || value.current_approved_version_ref !== null
        || typeof value.created_at !== "string" || !stamp.test(value.created_at)
        || !Number.isFinite(Date.parse(value.created_at)) || value.etag !== '"v0"'
        || response.headers.get("etag") !== '"v0"'
        || response.headers.get("location")
          !== `/api/v1/projects/${projectId}/solution-sections/${value.solution_section_id}`) uncertain();
      return Object.freeze({ ...value }) as unknown as SectionSummary;
    } catch (failure) {
      if (failure instanceof SectionCreateError) throw failure;
      return uncertain();
    }
  }
}
