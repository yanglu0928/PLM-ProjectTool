/** SOL-03 OutlineVersion customer Review submission; 201 is not approval. */
import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";

export interface OutlineReviewSubmission {
  readonly review_id: string; readonly review_round_id: string;
  readonly subject_type: "SOL-03"; readonly project_id: string;
  readonly solution_outline_id: string; readonly solution_outline_version_id: string;
  readonly policy_ref: "SOLUTION_OUTLINE_ALL_V1"; readonly reviewer_ids: readonly string[];
  readonly state: "IN_REVIEW"; readonly round_no: 1; readonly review_etag: '"v1"';
  readonly submitted_by: string; readonly submitted_at: string;
}
const messages = {
  OUTLINE_REVIEW_INVALID: "方案大纲版本、客户确认人或操作号无效。",
  OUTLINE_REVIEW_UNCERTAIN: "送审结果无法确认；请保留原操作号与确认人，核对评审记录。",
  AUTH_RELOGIN_REQUIRED: "请重新登录后再送审。",
  AUTH_CLIENT_BUSY: "账户正在处理其他操作，请稍候。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许方案大纲送审。",
  RESOURCE_NOT_FOUND: "方案大纲版本不存在或无权送审。",
  PROJECT_ARCHIVED: "项目已归档，不可送审。",
  VALIDATION_FAILED: "送审请求不符合合同。",
  BUSINESS_REVIEW_NOT_ELIGIBLE: "当前方案来源或追溯已变化，请重新核查。",
  REVIEW_REVIEWER_INELIGIBLE: "客户确认人资格已变化，请刷新成员。",
  REVIEW_SUBJECT_LOCKED: "方案大纲已在评审中，请刷新详情。",
  CONFLICT_IDEMPOTENCY: "原操作号已用于其他内容，请核对评审记录。",
  CONFLICT_VERSION: "方案大纲版本已变化，请刷新详情。",
  SYSTEM_UNAVAILABLE: "送审服务暂不可用；请保留原操作号。",
} as const;
export type OutlineReviewSubmitErrorCode = keyof typeof messages;
export class OutlineReviewSubmitError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: OutlineReviewSubmitErrorCode) {
    super(messages[code]); this.name = "OutlineReviewSubmitError";
    this.uncertain = code === "OUTLINE_REVIEW_UNCERTAIN" || code === "SYSTEM_UNAVAILABLE";
  }
}
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const fields = ["review_id", "review_round_id", "subject_type", "project_id",
  "solution_outline_id", "solution_outline_version_id", "policy_ref", "reviewer_ids",
  "state", "round_no", "review_etag", "submitted_by", "submitted_at"] as const;
const statuses: Readonly<Record<string, number>> = {
  AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403, LICENSE_OPERATION_DENIED: 403,
  RESOURCE_NOT_FOUND: 404, PROJECT_ARCHIVED: 409, VALIDATION_FAILED: 422,
  BUSINESS_REVIEW_NOT_ELIGIBLE: 422, REVIEW_REVIEWER_INELIGIBLE: 422,
  REVIEW_SUBJECT_LOCKED: 409, CONFLICT_IDEMPOTENCY: 409,
  CONFLICT_VERSION: 409, SYSTEM_UNAVAILABLE: 503,
};
function record(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}
function exact(v: Record<string, unknown>, names: readonly string[]) {
  return Object.keys(v).length === names.length && names.every(name => Object.hasOwn(v, name));
}
function id(v: unknown): v is string {
  return typeof v === "string" && uuid.test(v) && v !== "00000000-0000-0000-0000-000000000000";
}
function instant(v: unknown): v is string {
  return typeof v === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/.test(v)
    && Number.isFinite(Date.parse(v));
}
function fail(code: OutlineReviewSubmitErrorCode = "OUTLINE_REVIEW_UNCERTAIN"): never {
  throw new OutlineReviewSubmitError(code);
}
export class OutlineVersionSubmitReviewClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) fail("OUTLINE_REVIEW_INVALID");
  }
  async submit(project: string, outline: string, version: string,
    reviewerIds: readonly string[], key: string): Promise<OutlineReviewSubmission> {
    if (![project, outline, version].every(id) || !Array.isArray(reviewerIds)
      || reviewerIds.length < 1 || reviewerIds.length > 32
      || reviewerIds.some(value => !id(value))
      || new Set(reviewerIds).size !== reviewerIds.length
      || typeof key !== "string" || !/^[\x20-\x7e]{16,128}$/.test(key)) {
      fail("OUTLINE_REVIEW_INVALID");
    }
    const view = this.session.view;
    if (!view || view.password_change_required || !this.session.canSubmit
      || !view.authorized_projects.some(item => item.project_id === project
        && item.role === "PROJECT_MANAGER")) fail("OUTLINE_REVIEW_INVALID");
    const selected = Object.freeze([...reviewerIds].sort());
    const body = JSON.stringify({ reviewer_ids: selected,
      policy_ref: "SOLUTION_OUTLINE_ALL_V1", due_at: null, submission_note: null });
    let response: Response;
    try {
      response = await this.session.postProjectOutlineVersionSubmitReview(
        project, outline, version, body, key);
    } catch (error) {
      if (error instanceof SessionClientError
        && (error.code === "AUTH_RELOGIN_REQUIRED" || error.code === "AUTH_CLIENT_BUSY")) {
        throw new OutlineReviewSubmitError(error.code);
      }
      return fail();
    }
    try {
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase()
        !== "application/json" || response.headers.get("cache-control") !== "no-store") fail();
      const payload: unknown = await response.json();
      if (!record(payload) || !id(payload.trace_id)
        || response.headers.get("x-trace-id") !== payload.trace_id) fail();
      if (response.status !== 201) {
        const code = record(payload.error) ? payload.error.code : null;
        if (typeof code === "string" && statuses[code] === response.status) {
          throw new OutlineReviewSubmitError(code as OutlineReviewSubmitErrorCode);
        }
        fail();
      }
      if (!exact(payload, ["data", "trace_id"]) || !record(payload.data)
        || !exact(payload.data, fields)) fail();
      const data = payload.data;
      if (!id(data.review_id) || !id(data.review_round_id)
        || data.subject_type !== "SOL-03" || data.project_id !== project
        || data.solution_outline_id !== outline
        || data.solution_outline_version_id !== version
        || data.policy_ref !== "SOLUTION_OUTLINE_ALL_V1"
        || !Array.isArray(data.reviewer_ids)
        || data.reviewer_ids.length !== selected.length
        || data.reviewer_ids.some((value, index) => value !== selected[index])
        || data.state !== "IN_REVIEW" || data.round_no !== 1
        || data.review_etag !== '"v1"'
        || response.headers.get("etag") !== data.review_etag
        || data.submitted_by !== view.user.user_id || !instant(data.submitted_at)) fail();
      return Object.freeze({ ...data,
        reviewer_ids: Object.freeze([...data.reviewer_ids]) }) as unknown as OutlineReviewSubmission;
    } catch (error) {
      if (error instanceof OutlineReviewSubmitError) throw error;
      return fail();
    }
  }
}
