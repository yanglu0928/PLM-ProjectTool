/** Frozen PlanVersion create, current-snapshot validation, and atomic review submission. */
import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";

export interface PlanVersionCreated {
  readonly plan_version_id: string; readonly plan_id: string; readonly project_id: string;
  readonly version_no: number; readonly version_state: "DRAFT"; readonly created_at: string;
}
export interface PlanVersionValidation {
  readonly valid: boolean; readonly blocking_issues: readonly string[]; readonly warnings: readonly string[];
  readonly coverage_summary: Readonly<Record<string, number>>; readonly checked_at: string;
}
export interface PlanVersionReviewSubmission {
  readonly review_id: string; readonly review_round_id: string; readonly subject_type: "PLN-02";
  readonly project_id: string; readonly plan_id: string; readonly plan_version_id: string;
  readonly policy_ref: "PLAN_VERSION_ALL_V1"; readonly reviewer_ids: readonly string[];
  readonly state: "IN_REVIEW"; readonly round_no: 1; readonly review_etag: '"v1"';
  readonly submitted_by: string; readonly submitted_at: string;
}
const messages = {
  PLAN_VERSION_WRITE_INVALID: "计划版本、内容或操作号无效。",
  PLAN_VERSION_WRITE_UNCERTAIN: "操作结果无法确认；请保留原操作号和内容，重新读取或按原操作重试。",
  AUTH_RELOGIN_REQUIRED: "请重新登录后再操作。", AUTH_CLIENT_BUSY: "账户正在处理其他操作，请稍候。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。", AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许此计划版本操作。", RESOURCE_NOT_FOUND: "计划版本不存在或无权操作。",
  PROJECT_ARCHIVED: "项目已归档，不可修改。", VALIDATION_FAILED: "计划版本内容或送审请求不符合要求。",
  CONFLICT_IDEMPOTENCY: "原操作号已用于不同内容，请核对历史。", SYSTEM_UNAVAILABLE: "服务暂不可用；请保留原操作号。",
  BUSINESS_REVIEW_NOT_ELIGIBLE: "当前批准来源或追溯已变化，请重新核查。",
  REVIEW_REVIEWER_INELIGIBLE: "所选评审人资格已变化，请刷新候选人。",
  REVIEW_SUBJECT_LOCKED: "计划版本已在评审中，请刷新详情。", CONFLICT_VERSION: "计划版本已变化，请刷新详情。",
} as const;
export type PlanVersionWriteErrorCode = keyof typeof messages;
export class PlanVersionWriteError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: PlanVersionWriteErrorCode) {
    super(messages[code]); this.name = "PlanVersionWriteError";
    this.uncertain = code === "PLAN_VERSION_WRITE_UNCERTAIN" || code === "SYSTEM_UNAVAILABLE";
  }
}
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const stamp = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/;
const draftFields = ["approved_solution_refs", "wbs_items", "dependencies", "milestones", "calendar_ref", "exclusions"] as const;
const coverageFields = ["requirement_total", "requirement_mapped", "requirement_excluded", "requirement_uncovered",
  "solution_total", "solution_mapped", "solution_excluded", "solution_uncovered"] as const;
const submissionFields = ["review_id", "review_round_id", "subject_type", "project_id", "plan_id", "plan_version_id",
  "policy_ref", "reviewer_ids", "state", "round_no", "review_etag", "submitted_by", "submitted_at"] as const;
const statuses: Readonly<Record<string, number>> = { AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403,
  LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404, PROJECT_ARCHIVED: 409, CONFLICT_IDEMPOTENCY: 409,
  CONFLICT_VERSION: 409, REVIEW_SUBJECT_LOCKED: 409, VALIDATION_FAILED: 422,
  BUSINESS_REVIEW_NOT_ELIGIBLE: 422, REVIEW_REVIEWER_INELIGIBLE: 422, SYSTEM_UNAVAILABLE: 503 };
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function exact(value: Record<string, unknown>, fields: readonly string[]): boolean {
  return Object.keys(value).length === fields.length && fields.every(field => Object.hasOwn(value, field));
}
function id(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value) && value !== "00000000-0000-0000-0000-000000000000";
}
function instant(value: unknown): value is string {
  return typeof value === "string" && stamp.test(value) && Number.isFinite(Date.parse(value));
}
function invalid(): never { throw new PlanVersionWriteError("PLAN_VERSION_WRITE_INVALID"); }
function uncertain(): never { throw new PlanVersionWriteError("PLAN_VERSION_WRITE_UNCERTAIN"); }
function keyValid(key: unknown): key is string { return typeof key === "string" && /^[\x20-\x7e]{16,128}$/.test(key); }
function authorized(session: SessionClient, projectId: string, managerOnly = false): boolean {
  const view = session.view;
  return !!view && !view.password_change_required && session.canSubmit
    && view.authorized_projects.some(item => item.project_id === projectId
      && (managerOnly ? item.role === "PROJECT_MANAGER"
        : item.role === "PROJECT_MANAGER" || item.role === "IMPLEMENTATION_MEMBER"));
}
function parseEnvelope(payload: unknown, response: Response): Record<string, unknown> {
  if (!record(payload) || !id(payload.trace_id) || response.headers.get("x-trace-id") !== payload.trace_id
    || response.headers.get("cache-control") !== "no-store" || !exact(payload, ["data", "trace_id"])
    || !record(payload.data)) uncertain();
  return payload.data;
}
function raiseFailure(payload: unknown, response: Response): never {
  if (!record(payload) || !record(payload.error) || typeof payload.error.code !== "string"
    || statuses[payload.error.code] !== response.status) uncertain();
  throw new PlanVersionWriteError(payload.error.code as PlanVersionWriteErrorCode);
}
async function payload(response: Response): Promise<unknown> {
  if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") uncertain();
  try { return await response.json(); } catch { return uncertain(); }
}

export class PlanVersionWriteClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) invalid();
  }

  async create(projectId: string, planId: string, draft: Readonly<Record<string, unknown>>,
    key: string): Promise<PlanVersionCreated> {
    if (!id(projectId) || !id(planId) || !record(draft) || !exact(draft, draftFields) || !keyValid(key)
      || !authorized(this.session, projectId)) invalid();
    let body: string;
    try { body = JSON.stringify(draft); } catch { return invalid(); }
    if (!body || new TextEncoder().encode(body).length > 8 * 1024 * 1024) invalid();
    let response: Response;
    try { response = await this.session.postProjectPlanVersionCreate(projectId, planId, body, key); }
    catch (error) {
      if (error instanceof SessionClientError && (error.code === "AUTH_RELOGIN_REQUIRED" || error.code === "AUTH_CLIENT_BUSY")) {
        throw new PlanVersionWriteError(error.code);
      }
      return uncertain();
    }
    const raw = await payload(response);
    if (response.status !== 201) raiseFailure(raw, response);
    const data = parseEnvelope(raw, response);
    const location = `/api/v1/projects/${projectId}/plans/${planId}/versions/${String(data.plan_version_id)}`;
    if (!exact(data, ["plan_version_id", "plan_id", "project_id", "version_no", "version_state", "created_at"])
      || !id(data.plan_version_id) || data.plan_id !== planId || data.project_id !== projectId
      || !Number.isSafeInteger(data.version_no) || (data.version_no as number) < 1 || data.version_state !== "DRAFT"
      || !instant(data.created_at) || response.headers.get("location") !== location) uncertain();
    return Object.freeze({ ...data }) as unknown as PlanVersionCreated;
  }

  async validate(projectId: string, planId: string, versionId: string, key: string): Promise<PlanVersionValidation> {
    if (!id(projectId) || !id(planId) || !id(versionId) || !keyValid(key)
      || !authorized(this.session, projectId)) invalid();
    let response: Response;
    try { response = await this.session.postProjectPlanVersionValidate(projectId, planId, versionId, key); }
    catch (error) {
      if (error instanceof SessionClientError && (error.code === "AUTH_RELOGIN_REQUIRED" || error.code === "AUTH_CLIENT_BUSY")) {
        throw new PlanVersionWriteError(error.code);
      }
      return uncertain();
    }
    const raw = await payload(response);
    if (response.status !== 200) raiseFailure(raw, response);
    const data = parseEnvelope(raw, response);
    const coverage = data.coverage_summary;
    const issues = data.blocking_issues;
    const warnings = data.warnings;
    if (!exact(data, ["valid", "blocking_issues", "warnings", "coverage_summary", "checked_at"])
      || typeof data.valid !== "boolean" || !Array.isArray(issues)
      || issues.some(value => typeof value !== "string" || !value)
      || issues.some((value, index) => index > 0 && issues[index - 1]! >= value)
      || data.valid !== (issues.length === 0) || !Array.isArray(warnings)
      || warnings.some(value => typeof value !== "string" || !value) || !record(coverage)
      || !exact(coverage, coverageFields) || coverageFields.some(field => !Number.isSafeInteger(coverage[field])
        || (coverage[field] as number) < 0) || !instant(data.checked_at)) uncertain();
    return Object.freeze({ ...data, blocking_issues: Object.freeze([...issues]),
      warnings: Object.freeze([...warnings]), coverage_summary: Object.freeze({ ...coverage }) }) as unknown as PlanVersionValidation;
  }

  async submitReview(projectId: string, planId: string, versionId: string,
    reviewerIds: readonly string[], key: string): Promise<PlanVersionReviewSubmission> {
    if (!id(projectId) || !id(planId) || !id(versionId) || !Array.isArray(reviewerIds)
      || reviewerIds.length < 1 || reviewerIds.length > 32 || reviewerIds.some(value => !id(value))
      || new Set(reviewerIds).size !== reviewerIds.length || !keyValid(key)
      || !authorized(this.session, projectId, true)) invalid();
    const selected = Object.freeze([...reviewerIds].sort());
    const body = JSON.stringify({ reviewer_ids: selected, policy_ref: "PLAN_VERSION_ALL_V1",
      due_at: null, submission_note: null });
    let response: Response;
    try { response = await this.session.postProjectPlanVersionSubmitReview(projectId, planId, versionId, body, key); }
    catch (error) {
      if (error instanceof SessionClientError && (error.code === "AUTH_RELOGIN_REQUIRED" || error.code === "AUTH_CLIENT_BUSY")) {
        throw new PlanVersionWriteError(error.code);
      }
      return uncertain();
    }
    const raw = await payload(response);
    if (response.status !== 201) raiseFailure(raw, response);
    const data = parseEnvelope(raw, response);
    if (!exact(data, submissionFields) || !id(data.review_id) || !id(data.review_round_id)
      || data.subject_type !== "PLN-02" || data.project_id !== projectId || data.plan_id !== planId
      || data.plan_version_id !== versionId || data.policy_ref !== "PLAN_VERSION_ALL_V1"
      || !Array.isArray(data.reviewer_ids) || data.reviewer_ids.length !== selected.length
      || data.reviewer_ids.some((value, index) => value !== selected[index]) || data.state !== "IN_REVIEW"
      || data.round_no !== 1 || data.review_etag !== '"v1"' || response.headers.get("etag") !== '"v1"'
      || data.submitted_by !== this.session.view?.user.user_id || !instant(data.submitted_at)) uncertain();
    return Object.freeze({ ...data, reviewer_ids: Object.freeze([...data.reviewer_ids]) }) as unknown as PlanVersionReviewSubmission;
  }
}
