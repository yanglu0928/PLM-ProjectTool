/** Audited SectionVersion report transport; 200 is not approval or Review readiness. */
import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";

export type ValidationStatus = "PASS" | "FAIL" | "UNAVAILABLE";
export interface SectionVersionValidationFacts {
  readonly integrity: ValidationStatus;
  readonly content: ValidationStatus;
  readonly requirements: ValidationStatus;
  readonly evidence: ValidationStatus;
  readonly trace: ValidationStatus;
  readonly spec: ValidationStatus;
}
export interface SectionVersionValidationReport {
  readonly audit_event_id: string;
  readonly observation_trace_id: string;
  readonly project_id: string;
  readonly solution_section_id: string;
  readonly solution_section_version_id: string;
  readonly version_no: number;
  readonly version_state: "DRAFT" | "IN_REVIEW" | "APPROVED" | "RETURNED" | "SUPERSEDED" | "RESTRICTED";
  readonly content_fingerprint: string;
  readonly requirement_count: number;
  readonly evidence_count: number;
  readonly facts: SectionVersionValidationFacts;
  readonly valid: boolean;
  readonly ready_for_review: boolean;
  readonly issue_codes: readonly string[];
  readonly observed_at: string;
}

const messages = {
  SECTION_VERSION_VALIDATE_INVALID: "项目、章节、版本或操作号无效。",
  SECTION_VERSION_VALIDATE_UNCERTAIN: "验证结果无法确认；请保留原操作号，勿换号重试。",
  AUTH_RELOGIN_REQUIRED: "请重新登录。",
  AUTH_CLIENT_BUSY: "账户操作进行中，请稍候。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许验证章节版本。",
  RESOURCE_NOT_FOUND: "章节版本不存在，或无权访问。",
  PROJECT_ARCHIVED: "项目已归档，不可验证章节版本。",
  VALIDATION_FAILED: "验证请求不符合要求。",
  CONFLICT_IDEMPOTENCY: "操作号已用于其他章节版本；请核对原操作。",
  SYSTEM_UNAVAILABLE: "验证服务暂不可用；请保留原操作号。",
} as const;
export type SectionVersionValidateErrorCode = keyof typeof messages;
export class SectionVersionValidateError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: SectionVersionValidateErrorCode) {
    super(messages[code]); this.name = "SectionVersionValidateError";
    this.uncertain = code === "SECTION_VERSION_VALIDATE_UNCERTAIN"
      || code === "SYSTEM_UNAVAILABLE";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const digest = /^[0-9a-f]{64}$/;
const instant = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/;
const dimensions = ["integrity", "content", "requirements", "evidence", "trace", "spec"] as const;
const issueNames = ["FIXED_VERSION", "CONTENT_SOURCE", "REQUIREMENT_SOURCE",
  "EVIDENCE_SOURCE", "TRACE_COVERAGE", "STRUCTURED_SPEC"] as const;
const states = ["DRAFT", "IN_REVIEW", "APPROVED", "RETURNED", "SUPERSEDED", "RESTRICTED"] as const;
const fields = ["audit_event_id", "observation_trace_id", "project_id",
  "solution_section_id", "solution_section_version_id", "version_no", "version_state",
  "content_fingerprint", "requirement_count", "evidence_count", "facts", "valid",
  "ready_for_review", "issue_codes", "observed_at"] as const;
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function exact(value: Record<string, unknown>, names: readonly string[]): boolean {
  return Object.keys(value).length === names.length && names.every(name => Object.hasOwn(value, name));
}
function id(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value)
    && value !== "00000000-0000-0000-0000-000000000000";
}
function count(value: unknown, max: number): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0 && value <= max;
}
function date(value: unknown): value is string {
  return typeof value === "string" && instant.test(value) && Number.isFinite(Date.parse(value))
    && new Date(value).toISOString().slice(0, 19) === value.slice(0, 19);
}
function uncertain(): never { throw new SectionVersionValidateError("SECTION_VERSION_VALIDATE_UNCERTAIN"); }
function invalid(): never { throw new SectionVersionValidateError("SECTION_VERSION_VALIDATE_INVALID"); }

export function parseSectionVersionValidationReport(value: unknown, project: string,
  section: string, version: string): SectionVersionValidationReport {
  if (!record(value) || !exact(value, fields)
    || !id(value.audit_event_id) || !id(value.observation_trace_id)
    || value.project_id !== project || value.solution_section_id !== section
    || value.solution_section_version_id !== version
    || !count(value.version_no, Number.MAX_SAFE_INTEGER) || value.version_no < 1
    || !states.includes(value.version_state as typeof states[number])
    || typeof value.content_fingerprint !== "string" || !digest.test(value.content_fingerprint)
    || !count(value.requirement_count, 500) || !count(value.evidence_count, 500)
    || !record(value.facts) || !exact(value.facts, dimensions)
    || typeof value.valid !== "boolean" || typeof value.ready_for_review !== "boolean"
    || !Array.isArray(value.issue_codes) || !date(value.observed_at)) uncertain();
  const facts = value.facts;
  if (!dimensions.every(name => ["PASS", "FAIL", "UNAVAILABLE"].includes(facts[name] as string))) uncertain();
  const expectedIssues = dimensions.flatMap((name, index) =>
    facts[name] === "PASS" ? [] : [`${issueNames[index]}_${facts[name]}`]);
  if (value.version_state !== "DRAFT") expectedIssues.unshift("VERSION_NOT_DRAFT");
  if (value.issue_codes.length !== expectedIssues.length
    || value.issue_codes.some((issue, index) => issue !== expectedIssues[index])) uncertain();
  const sourceValid = dimensions.slice(0, 4).every(name => facts[name] === "PASS");
  const ready = sourceValid && value.version_state === "DRAFT"
    && facts.trace === "PASS" && facts.spec === "PASS";
  if (value.valid !== sourceValid || value.ready_for_review !== ready) uncertain();
  return Object.freeze({ ...value,
    facts: Object.freeze({ ...facts }) as unknown as SectionVersionValidationFacts,
    issue_codes: Object.freeze([...value.issue_codes]) as readonly string[],
  }) as unknown as SectionVersionValidationReport;
}

export class SectionVersionValidateClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) invalid();
  }
  async validate(project: string, section: string, version: string,
    key: string): Promise<SectionVersionValidationReport> {
    if (!id(project) || !id(section) || !id(version)
      || typeof key !== "string" || !/^[\x20-\x7e]{16,128}$/.test(key)) invalid();
    const view = this.session.view;
    if (!view || view.password_change_required || !this.session.canSubmit
      || !view.authorized_projects.some(item => item.project_id === project
        && (item.role === "PROJECT_MANAGER" || item.role === "IMPLEMENTATION_MEMBER"))) invalid();
    let response: Response;
    try { response = await this.session.postProjectSectionVersionValidate(project, section, version, key); }
    catch (failure) {
      if (failure instanceof SessionClientError
        && (failure.code === "AUTH_RELOGIN_REQUIRED" || failure.code === "AUTH_CLIENT_BUSY")) {
        throw new SectionVersionValidateError(failure.code);
      }
      return uncertain();
    }
    try {
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json"
        || response.headers.get("cache-control") !== "no-store"
        || response.headers.has("etag")) uncertain();
      const payload: unknown = await response.json();
      if (!record(payload) || !id(payload.trace_id)
        || response.headers.get("x-trace-id") !== payload.trace_id) uncertain();
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const statuses: Readonly<Record<string, number>> = {
          AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403, LICENSE_OPERATION_DENIED: 403,
          RESOURCE_NOT_FOUND: 404, PROJECT_ARCHIVED: 409, VALIDATION_FAILED: 422,
          CONFLICT_IDEMPOTENCY: 409, SYSTEM_UNAVAILABLE: 503,
        };
        if (typeof code === "string" && statuses[code] === response.status) {
          throw new SectionVersionValidateError(code as SectionVersionValidateErrorCode);
        }
        uncertain();
      }
      if (!exact(payload, ["data", "trace_id"])) uncertain();
      return parseSectionVersionValidationReport(payload.data, project, section, version);
    } catch (failure) {
      if (failure instanceof SectionVersionValidateError) throw failure;
      return uncertain();
    }
  }
}
