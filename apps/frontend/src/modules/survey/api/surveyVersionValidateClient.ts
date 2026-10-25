/** Current-input Survey validation report; this command never approves or submits a version. */
import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";
import type { SurveyVersionView, SurveyVersionState } from "./surveyReadClient";

export type SurveyValidationIssue = "CONTENT_FINGERPRINT_MISMATCH" | "COUNT_MISMATCH" | "QUESTION_RULE_INVALID"
  | "CONDITION_RULE_INVALID" | "CONDITION_REFERENCE_INVALID" | "CONDITION_CYCLE" | "SOURCE_UNAVAILABLE"
  | "TARGET_DEPARTMENT_UNAVAILABLE";
export interface SurveyVersionValidationReport {
  readonly audit_event_id: string; readonly survey_id: string; readonly survey_version_id: string;
  readonly project_id: string; readonly version_no: number; readonly state: SurveyVersionState;
  readonly question_count: number; readonly option_count: number; readonly source_count: number;
  readonly target_department_count: number; readonly conditional_question_count: number;
  readonly valid: boolean; readonly blocking_issues: readonly SurveyValidationIssue[];
  readonly warnings: readonly string[]; readonly checked_at: string;
}
const codes = ["CONTENT_FINGERPRINT_MISMATCH", "COUNT_MISMATCH", "QUESTION_RULE_INVALID", "CONDITION_RULE_INVALID",
  "CONDITION_REFERENCE_INVALID", "CONDITION_CYCLE", "SOURCE_UNAVAILABLE", "TARGET_DEPARTMENT_UNAVAILABLE"] as const;
const errors = {
  SURVEY_VALIDATE_INVALID: "请重新读取调研版本后校验。", SURVEY_VALIDATE_UNCERTAIN: "校验结果无法确认；请保留原操作号并核对审计。",
  AUTH_RELOGIN_REQUIRED: "请重新登录。", AUTH_CLIENT_BUSY: "会话正在处理其他操作。",
  AUTH_SESSION_EXPIRED: "会话已失效。", AUTH_CSRF_INVALID: "登录状态已变化。",
  LICENSE_OPERATION_DENIED: "当前许可不允许校验。", RESOURCE_NOT_FOUND: "版本不存在或无权校验。",
  VALIDATION_FAILED: "当前版本不满足校验条件。", CONFLICT_IDEMPOTENCY: "操作号与原校验目标冲突。",
  CONFLICT_VERSION: "版本已变化，请刷新。", CONFLICT_STATE: "当前状态不可校验。",
  PROJECT_ARCHIVED: "项目已归档。", SYSTEM_UNAVAILABLE: "校验服务暂不可用，请核对审计。",
} as const;
export type SurveyVersionValidateErrorCode = keyof typeof errors;
export class SurveyVersionValidateError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: SurveyVersionValidateErrorCode) {
    super(errors[code]); this.name = "SurveyVersionValidateError"; this.uncertain = code === "SURVEY_VALIDATE_UNCERTAIN";
  }
}
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const stamp = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/;
function record(value: unknown): value is Record<string, unknown> { return typeof value === "object" && value !== null && !Array.isArray(value); }
function exact(value: Record<string, unknown>, fields: readonly string[]): boolean {
  return Object.keys(value).length === fields.length && fields.every(field => Object.hasOwn(value, field));
}
function id(value: unknown): value is string { return typeof value === "string" && uuid.test(value)
  && value !== "00000000-0000-0000-0000-000000000000"; }
function count(value: unknown): boolean { return typeof value === "number" && Number.isSafeInteger(value) && value >= 0; }
function uncertain(): never { throw new SurveyVersionValidateError("SURVEY_VALIDATE_UNCERTAIN"); }

export class SurveyVersionValidateClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) throw new SurveyVersionValidateError("SURVEY_VALIDATE_INVALID");
  }
  async validate(version: SurveyVersionView, key: string): Promise<SurveyVersionValidationReport> {
    if (!version || version.state !== "DRAFT" || !id(version.project_id) || !id(version.survey_id)
      || !id(version.survey_version_id) || !Number.isSafeInteger(version.version_no) || version.version_no < 1
      || typeof key !== "string" || !/^[\x20-\x7e]{16,128}$/.test(key)) {
      throw new SurveyVersionValidateError("SURVEY_VALIDATE_INVALID");
    }
    let response: Response;
    try { response = await this.session.postProjectSurveyVersionValidate(version.project_id, version.survey_id,
      version.survey_version_id, key); }
    catch (failure) {
      if (failure instanceof SessionClientError && (failure.code === "AUTH_RELOGIN_REQUIRED" || failure.code === "AUTH_CLIENT_BUSY"))
        throw new SurveyVersionValidateError(failure.code);
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
        if (typeof code === "string" && statuses[code] === response.status && code in errors)
          throw new SurveyVersionValidateError(code as SurveyVersionValidateErrorCode);
        uncertain();
      }
      if (!exact(payload, ["data", "trace_id"]) || !record(payload.data)) uncertain();
      const data = payload.data;
      const fields = ["audit_event_id", "survey_id", "survey_version_id", "project_id", "version_no", "state",
        "question_count", "option_count", "source_count", "target_department_count", "conditional_question_count",
        "valid", "blocking_issues", "warnings", "checked_at"];
      if (!exact(data, fields) || !id(data.audit_event_id) || data.survey_id !== version.survey_id
        || data.survey_version_id !== version.survey_version_id || data.project_id !== version.project_id
        || data.version_no !== version.version_no || data.state !== version.state
        || data.question_count !== version.declared_question_count || data.option_count !== version.declared_option_count
        || data.source_count !== version.declared_source_count
        || data.target_department_count !== version.declared_target_department_count
        || !count(data.conditional_question_count) || typeof data.valid !== "boolean"
        || !Array.isArray(data.blocking_issues) || data.blocking_issues.length > codes.length
        || data.blocking_issues.some((issue: unknown, index: number) => !codes.includes(issue as SurveyValidationIssue)
          || index > 0 && codes.indexOf(issue as SurveyValidationIssue) <= codes.indexOf((data.blocking_issues as unknown[])[index - 1] as SurveyValidationIssue))
        || data.valid !== (data.blocking_issues.length === 0) || !Array.isArray(data.warnings) || data.warnings.length !== 0
        || typeof data.checked_at !== "string" || !stamp.test(data.checked_at) || !Number.isFinite(Date.parse(data.checked_at))
        || !/(?:^|,)\s*no-store\s*(?:,|$)/i.test(response.headers.get("cache-control") ?? "")) uncertain();
      return Object.freeze({ ...data, blocking_issues: Object.freeze([...data.blocking_issues]), warnings: Object.freeze([]) }) as unknown as SurveyVersionValidationReport;
    } catch (failure) {
      if (failure instanceof SurveyVersionValidateError) throw failure;
      return uncertain();
    }
  }
}
