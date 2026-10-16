/** Frozen six-field GLOBAL Reference Create; current proof remains server-owned. */
import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";
import type { DeidentificationSources } from "./referenceDeidentificationClient";

export interface GlobalReferenceCreateInput extends DeidentificationSources {
  readonly name: string;
}
export interface GlobalReferenceCreated {
  readonly reference_solution_id: string;
  readonly reference_version_id: string;
  readonly scope: "GLOBAL";
  readonly project_id: null;
  readonly name: string;
  readonly eligibility_state: "REFERENCE_ONLY";
  readonly version_state: "DRAFT";
  readonly created_by: string;
  readonly created_at: string;
  readonly etag: '"v0"';
}
const messages = {
  REFERENCE_CREATE_INVALID: "参考方案名称或固定来源无效。",
  REFERENCE_CREATE_UNCERTAIN: "创建结果不确定；请保留原操作号，不要换号重试。",
  AUTH_RELOGIN_REQUIRED: "请重新登录。",
  AUTH_CLIENT_BUSY: "账户操作进行中，请稍候。",
  AUTH_SESSION_EXPIRED: "登录已失效，请重新登录。",
  AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许创建。",
  RESOURCE_NOT_FOUND: "来源或人工确认不存在、已失效，或无权访问。",
  VALIDATION_FAILED: "请求字段不符合合同。",
  CONFLICT_IDEMPOTENCY: "操作号已用于不同内容；请核对历史。",
  SYSTEM_UNAVAILABLE: "当前来源或服务不可用，请重新核验。",
} as const;
export type GlobalReferenceCreateErrorCode = keyof typeof messages;
export class GlobalReferenceCreateError extends Error {
  constructor(readonly code: GlobalReferenceCreateErrorCode) {
    super(messages[code]); this.name = "GlobalReferenceCreateError";
  }
}
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const instant = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/;
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function exact(value: Record<string, unknown>, fields: readonly string[]): boolean {
  return Object.keys(value).length === fields.length && fields.every(field => Object.hasOwn(value, field));
}
function id(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value) && value !== "00000000-0000-0000-0000-000000000000";
}
function invalid(): never { throw new GlobalReferenceCreateError("REFERENCE_CREATE_INVALID"); }
function uncertain(): never { throw new GlobalReferenceCreateError("REFERENCE_CREATE_UNCERTAIN"); }
function valid(input: GlobalReferenceCreateInput): boolean {
  return record(input) && exact(input, ["name", "document_version_ids", "evidence_ids",
    "source_project_class", "deidentification_class", "applicability"])
    && typeof input.name === "string" && input.name === input.name.trim()
    && input.name === input.name.normalize("NFC") && input.name.length > 0 && input.name.length <= 255
    && !/[\x00-\x1f]/.test(input.name)
    && Array.isArray(input.document_version_ids) && input.document_version_ids.length >= 1
    && input.document_version_ids.length <= 100 && input.document_version_ids.every(id)
    && new Set(input.document_version_ids).size === input.document_version_ids.length
    && Array.isArray(input.evidence_ids) && input.evidence_ids.length <= 500
    && input.evidence_ids.every(id) && new Set(input.evidence_ids).size === input.evidence_ids.length
    && typeof input.source_project_class === "string" && !!input.source_project_class
    && input.source_project_class.length <= 128 && input.source_project_class === input.source_project_class.trim()
    && typeof input.deidentification_class === "string" && !!input.deidentification_class
    && input.deidentification_class.length <= 128 && input.deidentification_class === input.deidentification_class.trim()
    && record(input.applicability);
}
export class GlobalReferenceCreateClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) invalid();
  }
  async create(input: GlobalReferenceCreateInput, key: string): Promise<GlobalReferenceCreated> {
    if (!valid(input) || typeof key !== "string" || !/^[\x20-\x7e]{16,128}$/.test(key)) invalid();
    if (!this.session.view || this.session.view.password_change_required
      || this.session.view.deployment_role !== "DEPLOYMENT_ADMIN") invalid();
    let body: string;
    try { body = JSON.stringify(input); }
    catch { return invalid(); }
    if (new TextEncoder().encode(body).length > 128 * 1024) invalid();
    let response: Response;
    try { response = await this.session.postGlobalReferenceCreate(body, key); }
    catch (failure) {
      if (failure instanceof SessionClientError
        && ["AUTH_RELOGIN_REQUIRED", "AUTH_CLIENT_BUSY"].includes(failure.code)) {
        throw new GlobalReferenceCreateError(failure.code as GlobalReferenceCreateErrorCode);
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
          VALIDATION_FAILED: 422, CONFLICT_IDEMPOTENCY: 409,
          SYSTEM_UNAVAILABLE: 503,
        };
        if (typeof code === "string" && statuses[code] === response.status) {
          throw new GlobalReferenceCreateError(code as GlobalReferenceCreateErrorCode);
        }
        uncertain();
      }
      if (!exact(payload, ["data", "trace_id"]) || !record(payload.data)) uncertain();
      const value = payload.data;
      if (!exact(value, ["reference_solution_id", "reference_version_id", "scope", "project_id",
        "name", "eligibility_state", "version_state", "created_by", "created_at", "etag"])
        || !id(value.reference_solution_id) || !id(value.reference_version_id)
        || value.scope !== "GLOBAL" || value.project_id !== null || value.name !== input.name
        || value.eligibility_state !== "REFERENCE_ONLY" || value.version_state !== "DRAFT"
        || !id(value.created_by) || typeof value.created_at !== "string"
        || !instant.test(value.created_at) || !Number.isFinite(Date.parse(value.created_at))
        || value.etag !== '"v0"' || response.headers.get("etag") !== '"v0"'
        || response.headers.get("location") !== `/api/v1/global/reference-solutions/${value.reference_solution_id}`
        || response.headers.get("x-trace-id") !== payload.trace_id) uncertain();
      return Object.freeze({ ...value }) as unknown as GlobalReferenceCreated;
    } catch (failure) {
      if (failure instanceof GlobalReferenceCreateError) throw failure;
      return uncertain();
    }
  }
}
