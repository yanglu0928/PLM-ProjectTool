/** Frozen Reference Revise five-field command; result ETag is an immutable lock snapshot. */
import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";
import type { DeidentificationSources } from "./referenceDeidentificationClient";

export type ReferenceReviseInput = DeidentificationSources;
export interface ReferenceRevised {
  readonly reference_solution_id: string;
  readonly reference_version_id: string;
  readonly scope: "PROJECT" | "GLOBAL";
  readonly project_id: string | null;
  readonly version_no: number;
  readonly version_state: "DRAFT";
  readonly supersedes_version_ref: string;
  readonly created_at: string;
  readonly etag: string;
}
const messages = {
  REFERENCE_REVISE_INVALID: "修订目标、来源、当前版本或操作号无效。",
  REFERENCE_REVISE_UNCERTAIN: "修订结果不确定；请保留原操作号和版本，不要换号重试。",
  AUTH_RELOGIN_REQUIRED: "请重新登录。",
  AUTH_CLIENT_BUSY: "账户操作进行中，请稍候。",
  AUTH_SESSION_EXPIRED: "登录已失效，请重新登录。",
  AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许修订。",
  RESOURCE_NOT_FOUND: "参考方案或来源不存在，或无权访问。",
  PROJECT_ARCHIVED: "项目已归档。",
  VALIDATION_FAILED: "固定来源不符合要求。",
  CONFLICT_VERSION: "当前版本已变化，请重新读取后再决定。",
  CONFLICT_IDEMPOTENCY: "操作号已用于不同内容；请核对历史。",
  SYSTEM_UNAVAILABLE: "服务暂不可用，请核对原操作。",
} as const;
export type ReferenceReviseErrorCode = keyof typeof messages;
export class ReferenceReviseClientError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: ReferenceReviseErrorCode) {
    super(messages[code]); this.name = "ReferenceReviseClientError";
    this.uncertain = code === "REFERENCE_REVISE_UNCERTAIN";
  }
}
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const etagPattern = /^"v(?:0|[1-9][0-9]*)"$/;
const instant = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/;
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function exact(value: Record<string, unknown>, keys: readonly string[]): boolean {
  return Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
}
function id(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value)
    && value !== "00000000-0000-0000-0000-000000000000";
}
function etag(value: unknown): value is string {
  return typeof value === "string" && etagPattern.test(value)
    && Number.isSafeInteger(Number(value.slice(2, -1)));
}
function invalid(): never { throw new ReferenceReviseClientError("REFERENCE_REVISE_INVALID"); }
function uncertain(): never { throw new ReferenceReviseClientError("REFERENCE_REVISE_UNCERTAIN"); }
function validInput(value: unknown): value is ReferenceReviseInput {
  return record(value) && exact(value, ["document_version_ids", "evidence_ids",
    "source_project_class", "deidentification_class", "applicability"])
    && Array.isArray(value.document_version_ids) && value.document_version_ids.length >= 1
    && value.document_version_ids.length <= 100 && value.document_version_ids.every(id)
    && new Set(value.document_version_ids).size === value.document_version_ids.length
    && Array.isArray(value.evidence_ids) && value.evidence_ids.length <= 500
    && value.evidence_ids.every(id) && new Set(value.evidence_ids).size === value.evidence_ids.length
    && typeof value.source_project_class === "string" && value.source_project_class.length > 0
    && value.source_project_class.length <= 128 && value.source_project_class === value.source_project_class.trim()
    && typeof value.deidentification_class === "string" && value.deidentification_class.length > 0
    && value.deidentification_class.length <= 128
    && value.deidentification_class === value.deidentification_class.trim()
    && record(value.applicability);
}

export class ReferenceReviseClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) invalid();
  }
  async revise(scope: "PROJECT" | "GLOBAL", referenceId: string, projectId: string | null,
    input: ReferenceReviseInput, currentEtag: string, operationKey: string): Promise<ReferenceRevised> {
    if (!id(referenceId) || (scope === "PROJECT" ? !id(projectId) : projectId !== null)
      || !["PROJECT", "GLOBAL"].includes(scope) || !validInput(input) || !etag(currentEtag)
      || typeof operationKey !== "string" || !/^[\x20-\x7e]{16,128}$/.test(operationKey)) invalid();
    const view = this.session.view;
    if (!view || view.password_change_required || !this.session.canSubmit
      || (scope === "GLOBAL" ? view.deployment_role !== "DEPLOYMENT_ADMIN"
        : !view.authorized_projects.some(item => item.project_id === projectId
          && (item.role === "PROJECT_MANAGER" || item.role === "IMPLEMENTATION_MEMBER")))) invalid();
    let body: string;
    try { body = JSON.stringify(input); } catch { return invalid(); }
    if (new TextEncoder().encode(body).length > 128 * 1024) invalid();
    let response: Response;
    try {
      response = await this.session.postReferenceRevise(
        scope, referenceId, projectId, body, currentEtag, operationKey);
    } catch (failure) {
      if (failure instanceof SessionClientError
        && (failure.code === "AUTH_RELOGIN_REQUIRED" || failure.code === "AUTH_CLIENT_BUSY")) {
        throw new ReferenceReviseClientError(failure.code);
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
          CONFLICT_VERSION: 409, CONFLICT_IDEMPOTENCY: 409,
          SYSTEM_UNAVAILABLE: 503,
        };
        if (typeof code === "string" && statuses[code] === response.status) {
          throw new ReferenceReviseClientError(code as ReferenceReviseErrorCode);
        }
        uncertain();
      }
      if (!exact(payload, ["data", "trace_id"]) || !record(payload.data)) uncertain();
      const value = payload.data;
      if (!exact(value, ["reference_solution_id", "reference_version_id", "scope",
        "project_id", "version_no", "version_state", "supersedes_version_ref", "created_at", "etag"])
        || value.reference_solution_id !== referenceId || !id(value.reference_version_id)
        || value.scope !== scope || value.project_id !== projectId
        || !Number.isSafeInteger(value.version_no) || (value.version_no as number) < 2
        || value.version_state !== "DRAFT" || !id(value.supersedes_version_ref)
        || value.supersedes_version_ref === value.reference_version_id
        || typeof value.created_at !== "string" || !instant.test(value.created_at)
        || !Number.isFinite(Date.parse(value.created_at))
        || !etag(value.etag) || response.headers.get("etag") !== value.etag) uncertain();
      return Object.freeze({ ...value }) as unknown as ReferenceRevised;
    } catch (failure) {
      if (failure instanceof ReferenceReviseClientError) throw failure;
      return uncertain();
    }
  }
}
