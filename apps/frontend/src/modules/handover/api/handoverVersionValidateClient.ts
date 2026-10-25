/** Frozen Handover validation: current-input report, never an approval or customer decision. */
import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";
import type { HandoverAnalysisVersionView, HandoverVersionState } from "./handoverReadClient";

export type HandoverValidationIssue = "CONTENT_FINGERPRINT_MISMATCH" | "SOURCE_UNAVAILABLE"
  | "EVIDENCE_UNAVAILABLE" | "CAPABILITY_UNAVAILABLE" | "AI_PROVENANCE_UNAVAILABLE"
  | "INPUT_GUIDANCE_INCOMPLETE" | "ACTION_ITEM_REQUIRED";
export interface HandoverVersionValidationReport {
  readonly audit_event_id: string; readonly handover_analysis_id: string;
  readonly handover_analysis_version_id: string; readonly project_id: string;
  readonly version_no: number; readonly state: HandoverVersionState;
  readonly item_count: number; readonly source_count: number; readonly evidence_count: number;
  readonly capability_ref_count: number; readonly ai_task_count: number;
  readonly valid: boolean; readonly blocking_issues: readonly HandoverValidationIssue[];
  readonly warnings: readonly string[]; readonly checked_at: string;
}
const messages = {
  HND_VALIDATE_INVALID: "请重新读取交接版本后校验。",
  HND_VALIDATE_UNCERTAIN: "校验结果无法确认；请保留原操作号并核对审计。",
  AUTH_RELOGIN_REQUIRED: "请重新登录。", AUTH_CLIENT_BUSY: "会话正在处理其他操作。",
  AUTH_SESSION_EXPIRED: "会话已失效。", AUTH_CSRF_INVALID: "登录状态已变化。",
  LICENSE_OPERATION_DENIED: "当前许可不允许校验。", RESOURCE_NOT_FOUND: "版本不存在或无权校验。",
  VALIDATION_FAILED: "当前版本不满足校验条件。", CONFLICT_IDEMPOTENCY: "操作号与原校验目标冲突。",
  CONFLICT_VERSION: "版本已变化，请刷新。", CONFLICT_STATE: "当前状态不可校验。",
  PROJECT_ARCHIVED: "项目已归档。", SYSTEM_UNAVAILABLE: "校验服务暂不可用，请核对审计。",
} as const;
export type HandoverVersionValidateErrorCode = keyof typeof messages;
export class HandoverVersionValidateError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: HandoverVersionValidateErrorCode) {
    super(messages[code]); this.name = "HandoverVersionValidateError";
    this.uncertain = code === "HND_VALIDATE_UNCERTAIN";
  }
}
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const keyPattern = /^[\x20-\x7e]{16,128}$/;
const stamp = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/;
const states = ["DRAFT", "IN_REVIEW", "APPROVED", "RETURNED", "SUPERSEDED", "RESTRICTED"];
const issues: readonly HandoverValidationIssue[] = ["CONTENT_FINGERPRINT_MISMATCH", "SOURCE_UNAVAILABLE",
  "EVIDENCE_UNAVAILABLE", "CAPABILITY_UNAVAILABLE", "AI_PROVENANCE_UNAVAILABLE",
  "INPUT_GUIDANCE_INCOMPLETE", "ACTION_ITEM_REQUIRED"];
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function exact(value: Record<string, unknown>, fields: readonly string[]): boolean {
  return Object.keys(value).length === fields.length && fields.every(field => Object.hasOwn(value, field));
}
function id(value: unknown): value is string { return typeof value === "string" && uuid.test(value)
  && value !== "00000000-0000-0000-0000-000000000000"; }
function count(value: unknown, min = 0): boolean { return Number.isSafeInteger(value) && Number(value) >= min; }
function uncertain(): never { throw new HandoverVersionValidateError("HND_VALIDATE_UNCERTAIN"); }

export class HandoverVersionValidateClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) throw new HandoverVersionValidateError("HND_VALIDATE_INVALID");
  }
  async validate(version: HandoverAnalysisVersionView, key: string): Promise<HandoverVersionValidationReport> {
    if (!record(version) || !id(version.project_id) || !id(version.handover_analysis_id)
      || !id(version.handover_analysis_version_id) || !count(version.version_no, 1)
      || !states.includes(version.state) || !count(version.declared_item_count, 1)
      || !count(version.declared_source_count, 1) || !count(version.declared_evidence_count)
      || !count(version.declared_capability_ref_count) || !count(version.declared_ai_task_count)
      || typeof key !== "string" || !keyPattern.test(key)) {
      throw new HandoverVersionValidateError("HND_VALIDATE_INVALID");
    }
    const identity = this.session.view;
    if (!identity || identity.password_change_required || !this.session.canSubmit
      || !identity.authorized_projects.some(project => project.project_id === version.project_id
        && (project.role === "PROJECT_MANAGER" || project.role === "IMPLEMENTATION_MEMBER"))) {
      throw new HandoverVersionValidateError("RESOURCE_NOT_FOUND");
    }
    let response: Response;
    try { response = await this.session.postProjectHandoverVersionValidate(
      version.project_id, version.handover_analysis_id, version.handover_analysis_version_id, key); }
    catch (failure) {
      if (failure instanceof SessionClientError && (failure.code === "AUTH_RELOGIN_REQUIRED"
        || failure.code === "AUTH_CLIENT_BUSY")) throw new HandoverVersionValidateError(failure.code);
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
          PROJECT_ARCHIVED: 409, SYSTEM_UNAVAILABLE: 503 };
        if (typeof code === "string" && statuses[code] === response.status) {
          throw new HandoverVersionValidateError(code as HandoverVersionValidateErrorCode);
        }
        uncertain();
      }
      if (!exact(payload, ["data", "trace_id"]) || !record(payload.data)) uncertain();
      const data = payload.data;
      if (!exact(data, ["audit_event_id", "handover_analysis_id", "handover_analysis_version_id",
        "project_id", "version_no", "state", "item_count", "source_count", "evidence_count",
        "capability_ref_count", "ai_task_count", "valid", "blocking_issues", "warnings", "checked_at"])
        || !id(data.audit_event_id) || data.handover_analysis_id !== version.handover_analysis_id
        || data.handover_analysis_version_id !== version.handover_analysis_version_id
        || data.project_id !== version.project_id || data.version_no !== version.version_no
        || data.state !== version.state || data.item_count !== version.declared_item_count
        || data.source_count !== version.declared_source_count
        || data.evidence_count !== version.declared_evidence_count
        || data.capability_ref_count !== version.declared_capability_ref_count
        || data.ai_task_count !== version.declared_ai_task_count || typeof data.valid !== "boolean"
        || !Array.isArray(data.blocking_issues) || data.blocking_issues.length > issues.length
        || data.blocking_issues.some((issue: unknown, index: number) => !issues.includes(issue as HandoverValidationIssue)
          || index > 0 && issues.indexOf(issue as HandoverValidationIssue)
            <= issues.indexOf((data.blocking_issues as unknown[])[index - 1] as HandoverValidationIssue))
        || data.valid !== (data.blocking_issues.length === 0)
        || !Array.isArray(data.warnings) || data.warnings.length !== 0
        || typeof data.checked_at !== "string" || !stamp.test(data.checked_at)
        || !Number.isFinite(Date.parse(data.checked_at))
        || !/(?:^|,)\s*no-store\s*(?:,|$)/i.test(response.headers.get("cache-control") ?? "")) uncertain();
      return Object.freeze({ ...data, blocking_issues: Object.freeze([...data.blocking_issues]),
        warnings: Object.freeze([]) }) as unknown as HandoverVersionValidationReport;
    } catch (failure) {
      if (failure instanceof HandoverVersionValidateError) throw failure;
      return uncertain();
    }
  }
}
