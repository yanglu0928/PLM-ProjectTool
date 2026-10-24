import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";
import type { CapabilityVersion } from "./capabilityReadClient";

export interface CapabilityValidationReport {
  readonly audit_event_id: string; readonly baseline_id: string; readonly baseline_version_id: string;
  readonly version_no: number; readonly state: "DRAFT"; readonly source_collection_ref: string;
  readonly content_fingerprint: string; readonly item_count: number;
  readonly document_ref_count: number; readonly evidence_ref_count: number;
  readonly valid: boolean; readonly blocking_issues: readonly ("SOURCE_UNAVAILABLE" | "EVIDENCE_UNAVAILABLE")[];
  readonly warnings: readonly string[]; readonly checked_at: string;
}
const messages = {
  CAP_VALIDATE_INVALID: "请重新读取 DRAFT 版本后校验。",
  CAP_VALIDATE_UNCERTAIN: "校验结果无法确认；请保留原操作号并核对审计。",
  AUTH_RELOGIN_REQUIRED: "请重新登录。", AUTH_CLIENT_BUSY: "会话正在处理其他操作。",
  AUTH_SESSION_EXPIRED: "会话已失效。", AUTH_CSRF_INVALID: "登录状态已变化。",
  LICENSE_OPERATION_DENIED: "当前许可不允许校验。", RESOURCE_NOT_FOUND: "版本不存在或无权校验。",
  VALIDATION_FAILED: "当前版本不满足校验条件。", CONFLICT_IDEMPOTENCY: "操作号与原校验目标冲突。",
  CONFLICT_VERSION: "版本已变化，请刷新。", CONFLICT_STATE: "当前状态不可校验。",
  SYSTEM_UNAVAILABLE: "校验服务暂不可用，请核对审计。",
} as const;
export type CapabilityValidateErrorCode = keyof typeof messages;
export class CapabilityValidateError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: CapabilityValidateErrorCode) {
    super(messages[code]); this.name = "CapabilityValidateError";
    this.uncertain = code === "CAP_VALIDATE_UNCERTAIN";
  }
}
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const stamp = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/;
const keyPattern = /^[\x20-\x7e]{16,128}$/;
function id(value: unknown): value is string { return typeof value === "string" && uuid.test(value)
  && value !== "00000000-0000-0000-0000-000000000000"; }
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function exact(value: Record<string, unknown>, fields: readonly string[]): boolean {
  return Object.keys(value).length === fields.length && fields.every(field => Object.hasOwn(value, field));
}
function count(value: unknown, minimum = 0): boolean {
  return Number.isSafeInteger(value) && Number(value) >= minimum;
}
function uncertain(): never { throw new CapabilityValidateError("CAP_VALIDATE_UNCERTAIN"); }
export class CapabilityVersionValidateClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) throw new CapabilityValidateError("CAP_VALIDATE_INVALID");
  }
  async validate(version: CapabilityVersion, key: string): Promise<CapabilityValidationReport> {
    if (!record(version) || !id(version.baseline_id) || !id(version.baseline_version_id)
      || version.state !== "DRAFT" || !count(version.version_no, 1)
      || typeof version.source_collection_ref !== "string"
      || !/^sha256:[0-9a-f]{64}$/.test(version.source_collection_ref)
      || typeof version.content_fingerprint !== "string"
      || !/^[0-9a-f]{64}$/.test(version.content_fingerprint)
      || typeof key !== "string" || !keyPattern.test(key)) {
      throw new CapabilityValidateError("CAP_VALIDATE_INVALID");
    }
    const identity = this.session.view;
    if (!identity || identity.password_change_required || !this.session.canSubmit
      || identity.deployment_role !== "DEPLOYMENT_ADMIN") {
      throw new CapabilityValidateError("RESOURCE_NOT_FOUND");
    }
    let response: Response;
    try { response = await this.session.postGlobalCapabilityVersionValidate(
      version.baseline_id, version.baseline_version_id, key); }
    catch (failure) {
      if (failure instanceof SessionClientError && (failure.code === "AUTH_RELOGIN_REQUIRED"
        || failure.code === "AUTH_CLIENT_BUSY")) throw new CapabilityValidateError(failure.code);
      return uncertain();
    }
    try {
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") uncertain();
      const payload: unknown = await response.json();
      if (!record(payload) || !id(payload.trace_id)) uncertain();
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const statuses: Record<string, number> = { AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403,
          LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404, VALIDATION_FAILED: 422,
          CONFLICT_IDEMPOTENCY: 409, CONFLICT_VERSION: 409, CONFLICT_STATE: 409,
          SYSTEM_UNAVAILABLE: 503 };
        if (typeof code === "string" && statuses[code] === response.status) {
          throw new CapabilityValidateError(code as CapabilityValidateErrorCode);
        }
        uncertain();
      }
      if (!exact(payload, ["data", "trace_id"]) || !record(payload.data)) uncertain();
      const data = payload.data;
      if (!exact(data, ["audit_event_id", "baseline_id", "baseline_version_id", "version_no",
        "state", "source_collection_ref", "content_fingerprint", "item_count", "document_ref_count",
        "evidence_ref_count", "valid", "blocking_issues", "warnings", "checked_at"])
        || !id(data.audit_event_id) || data.baseline_id !== version.baseline_id
        || data.baseline_version_id !== version.baseline_version_id
        || data.version_no !== version.version_no || data.state !== "DRAFT"
        || data.source_collection_ref !== version.source_collection_ref
        || data.content_fingerprint !== version.content_fingerprint
        || !count(data.item_count, 1) || !count(data.document_ref_count, 1)
        || !count(data.evidence_ref_count, 1) || typeof data.valid !== "boolean"
        || !Array.isArray(data.blocking_issues) || data.blocking_issues.length > 2
        || data.blocking_issues.some(issue => !["SOURCE_UNAVAILABLE", "EVIDENCE_UNAVAILABLE"].includes(String(issue)))
        || new Set(data.blocking_issues).size !== data.blocking_issues.length
        || data.valid !== (data.blocking_issues.length === 0)
        || !Array.isArray(data.warnings) || data.warnings.length !== 0
        || typeof data.checked_at !== "string" || !stamp.test(data.checked_at)
        || !Number.isFinite(Date.parse(data.checked_at))
        || !/(?:^|,)\s*no-store\s*(?:,|$)/i.test(response.headers.get("cache-control") ?? "")) uncertain();
      return Object.freeze({ ...data,
        blocking_issues: Object.freeze([...data.blocking_issues]),
        warnings: Object.freeze([]) }) as unknown as CapabilityValidationReport;
    } catch (failure) {
      if (failure instanceof CapabilityValidateError) throw failure;
      return uncertain();
    }
  }
}
