/** Frozen SOL_SPEC_SUBMIT_REVIEW transport; a 201 receipt is not approval. */
import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";

export interface StructuredSpecReviewSubmission {
  readonly review_id: string;
  readonly review_round_id: string;
  readonly subject_type: "SOL-06";
  readonly project_id: string;
  readonly spec_series_id: string;
  readonly structured_solution_spec_id: string;
  readonly policy_ref: "STRUCTURED_SPEC_ALL_V1";
  readonly reviewer_ids: readonly string[];
  readonly state: "IN_REVIEW";
  readonly round_no: 1;
  readonly review_etag: '"v1"';
  readonly submitted_by: string;
  readonly submitted_at: string;
}

const messages = {
  STRUCTURED_SPEC_SUBMIT_INVALID: "送审版本、评审人或原操作号无效。",
  STRUCTURED_SPEC_SUBMIT_UNCERTAIN: "送审结果无法确认；请保留原评审人和操作号，核对评审记录后再重试。",
  AUTH_RELOGIN_REQUIRED: "请重新登录后再送审。",
  AUTH_CLIENT_BUSY: "账户正在处理其他操作，请稍候。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许提交结构化专项评审。",
  RESOURCE_NOT_FOUND: "专项版本不存在，或当前账户无权送审。",
  PROJECT_ARCHIVED: "项目已归档，不能提交评审。",
  VALIDATION_FAILED: "送审请求不符合冻结合同。",
  BUSINESS_REVIEW_NOT_ELIGIBLE: "当前专项事实不再满足送审条件，请重新验证。",
  REVIEW_REVIEWER_INELIGIBLE: "所选评审人不再具备当前项目评审资格，请刷新成员。",
  REVIEW_SUBJECT_LOCKED: "专项已进入评审或被其他操作锁定，请刷新详情。",
  CONFLICT_IDEMPOTENCY: "原操作号与送审内容不一致，已停止重试。",
  CONFLICT_VERSION: "专项版本状态已变化，请刷新详情。",
  SYSTEM_UNAVAILABLE: "送审服务暂不可用；请保留原操作号并核对评审记录。",
} as const;
export type StructuredSpecSubmitErrorCode = keyof typeof messages;
export class StructuredSpecSubmitReviewError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: StructuredSpecSubmitErrorCode) {
    super(messages[code]); this.name = "StructuredSpecSubmitReviewError";
    this.uncertain = code === "STRUCTURED_SPEC_SUBMIT_UNCERTAIN" || code === "SYSTEM_UNAVAILABLE";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const fields = ["review_id", "review_round_id", "subject_type", "project_id", "spec_series_id",
  "structured_solution_spec_id", "policy_ref", "reviewer_ids", "state", "round_no",
  "review_etag", "submitted_by", "submitted_at"] as const;
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
function instant(value: unknown): value is string {
  return typeof value === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/.test(value)
    && Number.isFinite(Date.parse(value));
}
function fail(code: StructuredSpecSubmitErrorCode = "STRUCTURED_SPEC_SUBMIT_UNCERTAIN"): never {
  throw new StructuredSpecSubmitReviewError(code);
}
function reviewers(values: readonly string[]): readonly string[] {
  if (!Array.isArray(values) || values.length < 1 || values.length > 32 || values.some(value => !id(value))
    || new Set(values).size !== values.length) fail("STRUCTURED_SPEC_SUBMIT_INVALID");
  return Object.freeze([...values].sort());
}

export class StructuredSpecSubmitReviewClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) fail("STRUCTURED_SPEC_SUBMIT_INVALID");
  }

  async submit(project: string, spec: string, series: string, reviewerIds: readonly string[],
    key: string): Promise<StructuredSpecReviewSubmission> {
    if (!id(project) || !id(spec) || !id(series) || typeof key !== "string"
      || !/^[\x20-\x7e]{16,128}$/.test(key)) fail("STRUCTURED_SPEC_SUBMIT_INVALID");
    const view = this.session.view;
    if (!view || view.password_change_required || !this.session.canSubmit
      || !view.authorized_projects.some(item => item.project_id === project && item.role === "PROJECT_MANAGER")) {
      fail("STRUCTURED_SPEC_SUBMIT_INVALID");
    }
    const selected = reviewers(reviewerIds);
    const body = JSON.stringify({ reviewer_ids: selected, policy_ref: "STRUCTURED_SPEC_ALL_V1",
      due_at: null, submission_note: null });
    let response: Response;
    try { response = await this.session.postProjectStructuredSpecSubmitReview(project, spec, body, key); }
    catch (failure) {
      if (failure instanceof SessionClientError
        && (failure.code === "AUTH_RELOGIN_REQUIRED" || failure.code === "AUTH_CLIENT_BUSY")) {
        throw new StructuredSpecSubmitReviewError(failure.code);
      }
      return fail();
    }
    try {
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json"
        || response.headers.get("cache-control") !== "no-store") fail();
      const payload: unknown = await response.json();
      if (!record(payload) || !id(payload.trace_id)
        || response.headers.get("x-trace-id") !== payload.trace_id) fail();
      if (response.status !== 201) {
        const code = record(payload.error) ? payload.error.code : null;
        const statuses: Readonly<Record<string, number>> = {
          AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403, LICENSE_OPERATION_DENIED: 403,
          RESOURCE_NOT_FOUND: 404, PROJECT_ARCHIVED: 409, VALIDATION_FAILED: 422,
          BUSINESS_REVIEW_NOT_ELIGIBLE: 422, REVIEW_REVIEWER_INELIGIBLE: 422,
          REVIEW_SUBJECT_LOCKED: 409, CONFLICT_IDEMPOTENCY: 409, CONFLICT_VERSION: 409,
          SYSTEM_UNAVAILABLE: 503,
        };
        if (typeof code === "string" && statuses[code] === response.status) {
          throw new StructuredSpecSubmitReviewError(code as StructuredSpecSubmitErrorCode);
        }
        fail();
      }
      if (!exact(payload, ["data", "trace_id"]) || !record(payload.data)
        || !exact(payload.data, fields)) fail();
      const data = payload.data;
      if (!id(data.review_id) || !id(data.review_round_id) || data.subject_type !== "SOL-06"
        || data.project_id !== project || data.spec_series_id !== series
        || data.structured_solution_spec_id !== spec || data.policy_ref !== "STRUCTURED_SPEC_ALL_V1"
        || !Array.isArray(data.reviewer_ids) || data.reviewer_ids.length !== selected.length
        || data.reviewer_ids.some((value, index) => value !== selected[index])
        || data.state !== "IN_REVIEW" || data.round_no !== 1 || data.review_etag !== '"v1"'
        || response.headers.get("etag") !== data.review_etag
        || data.submitted_by !== view.user.user_id || !instant(data.submitted_at)) fail();
      return Object.freeze({ ...data, reviewer_ids: Object.freeze([...data.reviewer_ids]) }) as unknown as StructuredSpecReviewSubmission;
    } catch (failure) {
      if (failure instanceof StructuredSpecSubmitReviewError) throw failure;
      return fail();
    }
  }
}
