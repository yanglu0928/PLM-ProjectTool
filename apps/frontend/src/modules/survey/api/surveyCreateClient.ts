/** Frozen PROJECT Survey Create; definition identity is not a customer finding. */
import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";

export interface SurveyCreateView {
  readonly survey_id: string;
  readonly project_id: string;
  readonly name: string;
  readonly state: "ACTIVE";
  readonly current_approved_version_ref: null;
  readonly created_at: string;
  readonly etag: '"v0"';
}

const messages = {
  SURVEY_CREATE_INVALID: "项目、调研名称或操作号无效。",
  SURVEY_CREATE_UNCERTAIN: "创建结果无法确认；请核对调研列表并保留原操作号。",
  AUTH_RELOGIN_REQUIRED: "请重新登录后再提交。",
  AUTH_CLIENT_BUSY: "会话正在处理其他操作，请稍候。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许创建调研定义。",
  RESOURCE_NOT_FOUND: "项目不存在或当前账户无权创建。",
  PROJECT_ARCHIVED: "项目已归档，不能创建调研定义。",
  VALIDATION_FAILED: "调研名称不符合要求。",
  CONFLICT_IDEMPOTENCY: "原操作号与当前内容冲突，请核对历史，不要生成新操作。",
  SYSTEM_UNAVAILABLE: "服务暂不可用；请保留原操作号并核对调研列表。",
} as const;
export type SurveyCreateErrorCode = keyof typeof messages;
export class SurveyCreateError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: SurveyCreateErrorCode) {
    super(messages[code]); this.name = "SurveyCreateError";
    this.uncertain = code === "SURVEY_CREATE_UNCERTAIN";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const stamp = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/;
const keyPattern = /^[\x20-\x7e]{16,128}$/;
function id(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value)
    && value !== "00000000-0000-0000-0000-000000000000";
}
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function exact(value: Record<string, unknown>, fields: readonly string[]): boolean {
  return Object.keys(value).length === fields.length && fields.every(field => Object.hasOwn(value, field));
}
function invalid(): never { throw new SurveyCreateError("SURVEY_CREATE_INVALID"); }
function uncertain(): never { throw new SurveyCreateError("SURVEY_CREATE_UNCERTAIN"); }
export function normalizeSurveyName(value: unknown): string {
  if (typeof value !== "string") invalid();
  const normalized = value.trim();
  if (!normalized || Array.from(normalized).length > 255 || /\p{C}/u.test(normalized)) invalid();
  return normalized;
}

export class SurveyCreateClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) invalid();
  }
  async create(projectId: string, name: string, key: string): Promise<SurveyCreateView> {
    if (!id(projectId) || typeof key !== "string" || !keyPattern.test(key)) invalid();
    const normalized = normalizeSurveyName(name);
    if (name !== normalized) invalid();
    const identity = this.session.view;
    if (!identity || identity.password_change_required || !this.session.canSubmit
      || !identity.authorized_projects.some(item => item.project_id === projectId
        && (item.role === "PROJECT_MANAGER" || item.role === "IMPLEMENTATION_MEMBER"))) {
      throw new SurveyCreateError("RESOURCE_NOT_FOUND");
    }
    let response: Response;
    try {
      response = await this.session.postProjectSurveyCreate(projectId,
        JSON.stringify({ name: normalized }), key);
    } catch (failure) {
      if (failure instanceof SessionClientError
        && (failure.code === "AUTH_RELOGIN_REQUIRED" || failure.code === "AUTH_CLIENT_BUSY")) {
        throw new SurveyCreateError(failure.code);
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
        const statuses: Readonly<Record<string, number>> = {
          AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403,
          LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404,
          PROJECT_ARCHIVED: 409, VALIDATION_FAILED: 422,
          CONFLICT_IDEMPOTENCY: 409, SYSTEM_UNAVAILABLE: 503,
        };
        if (typeof code === "string" && statuses[code] === response.status) {
          throw new SurveyCreateError(code as SurveyCreateErrorCode);
        }
        uncertain();
      }
      if (!exact(payload, ["data", "trace_id"]) || !record(payload.data)) uncertain();
      const value = payload.data;
      if (!exact(value, ["survey_id", "project_id", "name", "state",
        "current_approved_version_ref", "created_at", "etag"])
        || !id(value.survey_id) || value.project_id !== projectId
        || value.name !== normalized || value.state !== "ACTIVE"
        || value.current_approved_version_ref !== null
        || typeof value.created_at !== "string" || !stamp.test(value.created_at)
        || !Number.isFinite(Date.parse(value.created_at)) || value.etag !== '"v0"'
        || response.headers.get("etag") !== '"v0"'
        || response.headers.get("location") !== `/api/v1/projects/${projectId}/surveys/${value.survey_id}`) {
        uncertain();
      }
      return Object.freeze({ ...value }) as unknown as SurveyCreateView;
    } catch (failure) {
      if (failure instanceof SurveyCreateError) throw failure;
      return uncertain();
    }
  }
}
