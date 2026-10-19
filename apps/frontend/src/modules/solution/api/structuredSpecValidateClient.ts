/** Audited SOL-06 report transport; 200/valid/DRAFT never means approval. */
import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";
import type { SpecType } from "./structuredSpecCreateClient";

export type StructuredSpecValidationStatus = "PASS" | "FAIL" | "UNAVAILABLE";
export interface StructuredSpecValidationFacts {
  readonly integrity: StructuredSpecValidationStatus;
  readonly payload: StructuredSpecValidationStatus;
  readonly requirements: StructuredSpecValidationStatus;
  readonly sections: StructuredSpecValidationStatus;
  readonly evidence: StructuredSpecValidationStatus;
  readonly artifacts: StructuredSpecValidationStatus;
  readonly trace: StructuredSpecValidationStatus;
  readonly current_version: StructuredSpecValidationStatus;
}
export interface StructuredSpecTypeCheck {
  readonly code: string;
  readonly status: StructuredSpecValidationStatus;
}
export interface StructuredSpecValidationReport {
  readonly audit_event_id: string; readonly observation_trace_id: string;
  readonly project_id: string; readonly structured_solution_spec_id: string;
  readonly spec_series_id: string; readonly spec_type: SpecType;
  readonly version_no: number;
  readonly version_state: "DRAFT" | "IN_REVIEW" | "APPROVED" | "RETURNED" | "SUPERSEDED" | "RESTRICTED";
  readonly content_fingerprint: string; readonly payload_fingerprint: string;
  readonly requirement_count: number; readonly section_count: number;
  readonly evidence_count: number; readonly artifact_count: number;
  readonly facts: StructuredSpecValidationFacts;
  readonly type_checks: readonly StructuredSpecTypeCheck[];
  readonly valid: boolean; readonly ready_for_review: boolean;
  readonly issue_codes: readonly string[]; readonly observed_at: string;
}

const messages = {
  STRUCTURED_SPEC_VALIDATE_INVALID: "项目、专项版本或操作号无效。",
  STRUCTURED_SPEC_VALIDATE_UNCERTAIN: "验证结果无法确认；请保留原操作号，勿换号重试。",
  AUTH_RELOGIN_REQUIRED: "请重新登录。", AUTH_CLIENT_BUSY: "账户操作进行中，请稍候。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许验证结构化专项。",
  RESOURCE_NOT_FOUND: "专项版本不存在，或无权访问。",
  PROJECT_ARCHIVED: "项目已归档，不可验证专项版本。",
  VALIDATION_FAILED: "验证请求不符合要求。",
  CONFLICT_IDEMPOTENCY: "操作号已用于其他专项版本；请核对原操作。",
  SYSTEM_UNAVAILABLE: "验证服务暂不可用；请保留原操作号。",
} as const;
export type StructuredSpecValidateErrorCode = keyof typeof messages;
export class StructuredSpecValidateError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: StructuredSpecValidateErrorCode) {
    super(messages[code]); this.name = "StructuredSpecValidateError";
    this.uncertain = code === "STRUCTURED_SPEC_VALIDATE_UNCERTAIN" || code === "SYSTEM_UNAVAILABLE";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const digest = /^[0-9a-f]{64}$/;
const instant = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/;
const statuses = ["PASS", "FAIL", "UNAVAILABLE"] as const;
const dimensions = ["integrity", "payload", "requirements", "sections", "evidence",
  "artifacts", "trace", "current_version"] as const;
const issueNames = ["FIXED_VERSION", "PAYLOAD_STRUCTURE", "REQUIREMENT_SOURCE", "SECTION_SOURCE",
  "EVIDENCE_SOURCE", "ARTIFACT_SOURCE", "TRACE_COVERAGE", "CURRENT_VERSION"] as const;
const checks: Readonly<Record<SpecType, readonly string[]>> = {
  PROCESS_MODEL: ["GRAPH_STRUCTURE", "ROLE_DECLARATION", "INPUT_OUTPUT_DECLARATION"],
  INTERFACE_SPEC: ["BOUNDARY_MAPPING", "OWNERSHIP_RUNTIME_DECLARATION", "AUTHENTICATION_DECLARATION"],
  MIGRATION_SPEC: ["SCOPE_MAPPING", "TRIAL_PLAN", "RECONCILIATION_PLAN", "ROLLBACK_PLAN", "ACCEPTANCE_CRITERIA"],
  PERMISSION_DESIGN: ["MATRIX_DEFAULT_DENY", "SCOPE_DECLARATION", "DUTY_CONFLICT_DECLARATION"],
};
const legacyChecks: Readonly<Record<SpecType, readonly string[]>> = {
  PROCESS_MODEL: ["GRAPH_STRUCTURE", "ROLE_TRACEABILITY", "INPUT_OUTPUT_TRACEABILITY"],
  INTERFACE_SPEC: ["BOUNDARY_MAPPING", "OWNERSHIP_RUNTIME", "AUTHENTICATION_CONTROL"],
  MIGRATION_SPEC: ["SCOPE_MAPPING", "TRIAL_EXECUTION", "RECONCILIATION_PROOF", "ROLLBACK_PROOF", "ACCEPTANCE_PROOF"],
  PERMISSION_DESIGN: ["MATRIX_DEFAULT_DENY", "SCOPE_CONTROL", "DUTY_CONFLICT_REVIEW"],
};
const states = ["DRAFT", "IN_REVIEW", "APPROVED", "RETURNED", "SUPERSEDED", "RESTRICTED"] as const;
const fields = ["audit_event_id", "observation_trace_id", "project_id", "structured_solution_spec_id",
  "spec_series_id", "spec_type", "version_no", "version_state", "content_fingerprint",
  "payload_fingerprint", "requirement_count", "section_count", "evidence_count", "artifact_count",
  "facts", "type_checks", "valid", "ready_for_review", "issue_codes", "observed_at"] as const;
function record(value: unknown): value is Record<string, unknown> { return typeof value === "object" && value !== null && !Array.isArray(value); }
function exact(value: Record<string, unknown>, names: readonly string[]): boolean { return Object.keys(value).length === names.length && names.every(name => Object.hasOwn(value, name)); }
function id(value: unknown): value is string { return typeof value === "string" && uuid.test(value) && value !== "00000000-0000-0000-0000-000000000000"; }
function count(value: unknown, minimum = 0): value is number { return typeof value === "number" && Number.isSafeInteger(value) && value >= minimum && value <= 500; }
function date(value: unknown): value is string { return typeof value === "string" && instant.test(value) && Number.isFinite(Date.parse(value)); }
function uncertain(): never { throw new StructuredSpecValidateError("STRUCTURED_SPEC_VALIDATE_UNCERTAIN"); }
function invalid(): never { throw new StructuredSpecValidateError("STRUCTURED_SPEC_VALIDATE_INVALID"); }

export function parseStructuredSpecValidationReport(value: unknown, project: string,
  spec: string): StructuredSpecValidationReport {
  if (!record(value) || !exact(value, fields) || !id(value.audit_event_id)
    || !id(value.observation_trace_id) || value.project_id !== project
    || value.structured_solution_spec_id !== spec || !id(value.spec_series_id)
    || !Object.hasOwn(checks, value.spec_type as PropertyKey)
    || typeof value.version_no !== "number" || !Number.isSafeInteger(value.version_no) || value.version_no < 1
    || !states.includes(value.version_state as typeof states[number])
    || typeof value.content_fingerprint !== "string" || !digest.test(value.content_fingerprint)
    || typeof value.payload_fingerprint !== "string" || !digest.test(value.payload_fingerprint)
    || !count(value.requirement_count, 1) || !count(value.section_count, 1)
    || !count(value.evidence_count) || !count(value.artifact_count)
    || !record(value.facts) || !exact(value.facts, dimensions)
    || !Array.isArray(value.type_checks) || typeof value.valid !== "boolean"
    || typeof value.ready_for_review !== "boolean" || !Array.isArray(value.issue_codes)
    || !date(value.observed_at)) uncertain();
  const facts = value.facts;
  const typeChecks: unknown[] = value.type_checks;
  if (!dimensions.every(name => statuses.includes(facts[name] as typeof statuses[number]))) uncertain();
  const specType = value.spec_type as SpecType;
  const expectedChecks = [checks[specType], legacyChecks[specType]].find(candidate =>
    typeChecks.length === candidate.length && typeChecks.every((item, index) =>
      record(item) && exact(item, ["code", "status"]) && item.code === candidate[index]
        && statuses.includes(item.status as typeof statuses[number])));
  if (!expectedChecks) uncertain();
  const expectedIssues = dimensions.flatMap((name, index) => facts[name] === "PASS" ? [] : [`${issueNames[index]}_${facts[name]}`]);
  if (value.version_state !== "DRAFT") expectedIssues.unshift("VERSION_NOT_DRAFT");
  for (const item of typeChecks as Record<string, unknown>[]) if (item.status !== "PASS") expectedIssues.push(`${item.code}_${item.status}`);
  if (value.issue_codes.length !== expectedIssues.length || value.issue_codes.some((item, index) => item !== expectedIssues[index])) uncertain();
  const valid = dimensions.slice(0, 5).every(name => facts[name] === "PASS");
  const ready = valid && value.version_state === "DRAFT" && ["artifacts", "trace", "current_version"].every(name => facts[name] === "PASS")
    && (typeChecks as Record<string, unknown>[]).every(item => item.status === "PASS");
  if (value.valid !== valid || value.ready_for_review !== ready) uncertain();
  return Object.freeze({ ...value, facts: Object.freeze({ ...facts }),
    type_checks: Object.freeze((typeChecks as Record<string, unknown>[]).map(item => Object.freeze({ ...item }))),
    issue_codes: Object.freeze([...value.issue_codes]) }) as unknown as StructuredSpecValidationReport;
}

export class StructuredSpecValidateClient {
  constructor(private readonly session: SessionClient) { if (!(session instanceof SessionClient)) invalid(); }
  async validate(project: string, spec: string, key: string): Promise<StructuredSpecValidationReport> {
    if (!id(project) || !id(spec) || typeof key !== "string" || !/^[\x20-\x7e]{16,128}$/.test(key)) invalid();
    const view = this.session.view;
    if (!view || view.password_change_required || !this.session.canSubmit || !view.authorized_projects.some(item =>
      item.project_id === project && (item.role === "PROJECT_MANAGER" || item.role === "IMPLEMENTATION_MEMBER"))) invalid();
    let response: Response;
    try { response = await this.session.postProjectStructuredSpecValidate(project, spec, key); }
    catch (failure) {
      if (failure instanceof SessionClientError && (failure.code === "AUTH_RELOGIN_REQUIRED" || failure.code === "AUTH_CLIENT_BUSY")) throw new StructuredSpecValidateError(failure.code);
      return uncertain();
    }
    try {
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json"
        || response.headers.get("cache-control") !== "no-store" || response.headers.has("etag")) uncertain();
      const payload: unknown = await response.json();
      if (!record(payload) || !id(payload.trace_id) || response.headers.get("x-trace-id") !== payload.trace_id) uncertain();
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const statusMap: Readonly<Record<string, number>> = { AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403,
          LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404, PROJECT_ARCHIVED: 409,
          VALIDATION_FAILED: 422, CONFLICT_IDEMPOTENCY: 409, SYSTEM_UNAVAILABLE: 503 };
        if (typeof code === "string" && statusMap[code] === response.status) throw new StructuredSpecValidateError(code as StructuredSpecValidateErrorCode);
        uncertain();
      }
      if (!exact(payload, ["data", "trace_id"])) uncertain();
      return parseStructuredSpecValidationReport(payload.data, project, spec);
    } catch (failure) { if (failure instanceof StructuredSpecValidateError) throw failure; return uncertain(); }
  }
}
