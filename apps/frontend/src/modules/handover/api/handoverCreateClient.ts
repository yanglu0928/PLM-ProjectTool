/** Frozen Handover Analysis create; source references remain metadata-only. */
import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";

export interface HandoverCreateSource {
  readonly document_id: string;
  readonly document_version_id: string;
}
export interface HandoverCreateInput {
  readonly analysis_purpose: string;
  readonly source_documents: readonly HandoverCreateSource[];
}
export interface HandoverCreateView {
  readonly handover_analysis_id: string;
  readonly project_id: string;
  readonly analysis_purpose: string;
  readonly source_set_ref: string;
  readonly state: "ACTIVE";
  readonly current_approved_version_ref: null;
  readonly created_at: string;
  readonly etag: '"v0"';
}

const messages = {
  HANDOVER_CREATE_INVALID: "项目、交接目的或固定来源无效。",
  HANDOVER_CREATE_UNCERTAIN: "创建结果无法确认；请核对交接列表，并保留原操作号。",
  AUTH_RELOGIN_REQUIRED: "请重新登录后再提交。",
  AUTH_CLIENT_BUSY: "会话正在处理其他操作，请稍候。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许创建交接分析。",
  RESOURCE_NOT_FOUND: "项目不存在或当前账户无权创建。",
  PROJECT_ARCHIVED: "项目已归档，不能创建交接分析。",
  HANDOVER_SOURCE_REQUIRED: "所选文档固定版本已不可用，请重新核对项目文档。",
  VALIDATION_FAILED: "交接目的或固定来源不符合要求。",
  CONFLICT_IDEMPOTENCY: "原操作号与当前内容冲突，请核对历史，不要生成新操作。",
  SYSTEM_UNAVAILABLE: "服务暂不可用；请保留原操作并核对交接列表。",
} as const;
export type HandoverCreateErrorCode = keyof typeof messages;
export class HandoverCreateError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: HandoverCreateErrorCode) {
    super(messages[code]); this.name = "HandoverCreateError";
    this.uncertain = code === "HANDOVER_CREATE_UNCERTAIN";
  }
}
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const stamp = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/;
const sourceSet = /^sha256:[0-9a-f]{64}$/;
const keyPattern = /^[\x20-\x7e]{16,128}$/;
function id(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value) && value !== "00000000-0000-0000-0000-000000000000";
}
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function exact(value: Record<string, unknown>, fields: readonly string[]): boolean {
  return Object.keys(value).length === fields.length && fields.every(field => Object.hasOwn(value, field));
}
function invalid(): never { throw new HandoverCreateError("HANDOVER_CREATE_INVALID"); }
function uncertain(): never { throw new HandoverCreateError("HANDOVER_CREATE_UNCERTAIN"); }
export function normalizeHandoverPurpose(value: unknown): string {
  if (typeof value !== "string") invalid();
  const normalized = value.normalize("NFKC").trim();
  if (!normalized || normalized.length > 255 || /\p{C}/u.test(normalized)) invalid();
  return normalized;
}
export function normalizeHandoverSources(value: unknown): readonly HandoverCreateSource[] {
  if (!Array.isArray(value) || value.length < 1 || value.length > 500) invalid();
  const sources = value.map(item => {
    if (!record(item) || !exact(item, ["document_id", "document_version_id"])
      || !id(item.document_id) || !id(item.document_version_id)) invalid();
    return Object.freeze({ document_id: item.document_id, document_version_id: item.document_version_id });
  });
  if (new Set(sources.map(item => item.document_id)).size !== sources.length
    || new Set(sources.map(item => item.document_version_id)).size !== sources.length) invalid();
  return Object.freeze(sources.sort((a, b) => a.document_version_id.localeCompare(b.document_version_id)));
}

export class HandoverCreateClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) invalid();
  }
  async create(projectId: string, input: HandoverCreateInput, key: string): Promise<HandoverCreateView> {
    if (!id(projectId) || !record(input) || !exact(input, ["analysis_purpose", "source_documents"])
      || typeof key !== "string" || !keyPattern.test(key)) invalid();
    const purpose = normalizeHandoverPurpose(input.analysis_purpose);
    if (input.analysis_purpose !== purpose) invalid();
    const sources = normalizeHandoverSources(input.source_documents);
    const identity = this.session.view;
    if (!identity || identity.password_change_required || !this.session.canSubmit
      || !identity.authorized_projects.some(item => item.project_id === projectId
        && (item.role === "PROJECT_MANAGER" || item.role === "IMPLEMENTATION_MEMBER"))) {
      throw new HandoverCreateError("RESOURCE_NOT_FOUND");
    }
    let response: Response;
    try {
      response = await this.session.postProjectHandoverAnalysisCreate(projectId,
        JSON.stringify({ analysis_purpose: purpose, source_documents: sources }), key);
    } catch (failure) {
      if (failure instanceof SessionClientError
        && (failure.code === "AUTH_RELOGIN_REQUIRED" || failure.code === "AUTH_CLIENT_BUSY")) {
        throw new HandoverCreateError(failure.code);
      }
      return uncertain();
    }
    try {
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") uncertain();
      const payload: unknown = await response.json();
      if (!record(payload) || !id(payload.trace_id)) uncertain();
      if (response.status !== 201) {
        const code = record(payload.error) ? payload.error.code : null;
        const statuses: Readonly<Record<string, number>> = {
          AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403,
          LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404,
          PROJECT_ARCHIVED: 409, HANDOVER_SOURCE_REQUIRED: 422,
          VALIDATION_FAILED: 422, CONFLICT_IDEMPOTENCY: 409, SYSTEM_UNAVAILABLE: 503,
        };
        if (typeof code === "string" && statuses[code] === response.status) {
          throw new HandoverCreateError(code as HandoverCreateErrorCode);
        }
        uncertain();
      }
      if (!exact(payload, ["data", "trace_id"]) || !record(payload.data)) uncertain();
      const value = payload.data;
      if (!exact(value, ["handover_analysis_id", "project_id", "analysis_purpose",
        "source_set_ref", "state", "current_approved_version_ref", "created_at", "etag"])
        || !id(value.handover_analysis_id) || value.project_id !== projectId
        || value.analysis_purpose !== purpose || typeof value.source_set_ref !== "string"
        || !sourceSet.test(value.source_set_ref) || value.state !== "ACTIVE"
        || value.current_approved_version_ref !== null || typeof value.created_at !== "string"
        || !stamp.test(value.created_at) || !Number.isFinite(Date.parse(value.created_at))
        || value.etag !== '"v0"' || response.headers.get("etag") !== '"v0"'
        || response.headers.get("location") !== `/api/v1/projects/${projectId}/handover-analyses/${value.handover_analysis_id}`) {
        uncertain();
      }
      return Object.freeze({ ...value }) as unknown as HandoverCreateView;
    } catch (failure) {
      if (failure instanceof HandoverCreateError) throw failure;
      return uncertain();
    }
  }
}
