/** Frozen HND_VERSION_SUBMIT_REVIEW; IN_REVIEW is never an approval. */
import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";
import type { HandoverAnalysisVersionView } from "./handoverReadClient";

export interface HandoverReviewSubmission {
  readonly review_id: string; readonly review_round_id: string; readonly subject_type: "HND-02";
  readonly project_id: string; readonly handover_analysis_id: string;
  readonly handover_analysis_version_id: string; readonly policy_ref: "HANDOVER_ALL_V1";
  readonly reviewer_ids: readonly string[]; readonly state: "IN_REVIEW";
  readonly round_no: 1; readonly review_etag: '"v1"';
  readonly submitted_by: string; readonly submitted_at: string;
}
const messages = {
  HND_REVIEW_INVALID: "交接版本、客户确认人或操作号无效。",
  HND_REVIEW_UNCERTAIN: "送审结果无法确认；请保留原操作号和确认人，核对评审记录。",
  AUTH_RELOGIN_REQUIRED: "请重新登录后送审。", AUTH_CLIENT_BUSY: "会话正在处理其他操作。",
  AUTH_SESSION_EXPIRED: "会话已失效。", AUTH_CSRF_INVALID: "登录状态已变化。",
  LICENSE_OPERATION_DENIED: "当前许可不允许送审。", RESOURCE_NOT_FOUND: "版本不存在或无权送审。",
  VALIDATION_FAILED: "送审请求不符合合同。", BUSINESS_REVIEW_NOT_ELIGIBLE: "当前来源或问题不满足送审条件。",
  REVIEW_REVIEWER_INELIGIBLE: "客户确认人资格已变化，请刷新成员。",
  REVIEW_SUBJECT_LOCKED: "交接版本已在评审中，请刷新详情。",
  CONFLICT_IDEMPOTENCY: "原操作号与送审内容冲突，请核对评审历史。",
  CONFLICT_VERSION: "交接版本已变化，请刷新详情。", PROJECT_ARCHIVED: "项目已归档。",
  SYSTEM_UNAVAILABLE: "送审服务暂不可用；请保留原操作号。",
} as const;
export type HandoverSubmitReviewErrorCode = keyof typeof messages;
export class HandoverSubmitReviewError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: HandoverSubmitReviewErrorCode) {
    super(messages[code]); this.name = "HandoverSubmitReviewError";
    this.uncertain = code === "HND_REVIEW_UNCERTAIN" || code === "SYSTEM_UNAVAILABLE";
  }
}
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const fields = ["review_id", "review_round_id", "subject_type", "project_id",
  "handover_analysis_id", "handover_analysis_version_id", "policy_ref", "reviewer_ids",
  "state", "round_no", "review_etag", "submitted_by", "submitted_at"] as const;
const statuses: Readonly<Record<string, number>> = {
  AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403, LICENSE_OPERATION_DENIED: 403,
  RESOURCE_NOT_FOUND: 404, VALIDATION_FAILED: 422, BUSINESS_REVIEW_NOT_ELIGIBLE: 422,
  REVIEW_REVIEWER_INELIGIBLE: 422, REVIEW_SUBJECT_LOCKED: 409,
  CONFLICT_IDEMPOTENCY: 409, CONFLICT_VERSION: 409, PROJECT_ARCHIVED: 409,
  SYSTEM_UNAVAILABLE: 503,
};
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function exact(value: Record<string, unknown>, names: readonly string[]) {
  return Object.keys(value).length === names.length && names.every(name => Object.hasOwn(value, name));
}
function id(value: unknown): value is string { return typeof value === "string" && uuid.test(value)
  && value !== "00000000-0000-0000-0000-000000000000"; }
function instant(value: unknown): value is string {
  return typeof value === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/.test(value)
    && Number.isFinite(Date.parse(value));
}
function fail(code: HandoverSubmitReviewErrorCode = "HND_REVIEW_UNCERTAIN"): never {
  throw new HandoverSubmitReviewError(code);
}
export class HandoverVersionSubmitReviewClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) fail("HND_REVIEW_INVALID");
  }
  async submit(version: HandoverAnalysisVersionView, reviewerIds: readonly string[],
    key: string): Promise<HandoverReviewSubmission> {
    if (!record(version) || !id(version.project_id) || !id(version.handover_analysis_id)
      || !id(version.handover_analysis_version_id) || version.state !== "DRAFT"
      || version.review_ref !== null || version.review_round_ref !== null
      || !Array.isArray(reviewerIds) || reviewerIds.length < 1 || reviewerIds.length > 32
      || reviewerIds.some(value => !id(value)) || new Set(reviewerIds).size !== reviewerIds.length
      || typeof key !== "string" || !/^[\x20-\x7e]{16,128}$/.test(key)) fail("HND_REVIEW_INVALID");
    const actor = this.session.view;
    if (!actor || actor.password_change_required || !this.session.canSubmit
      || !actor.authorized_projects.some(project => project.project_id === version.project_id
        && project.role === "PROJECT_MANAGER")) fail("HND_REVIEW_INVALID");
    const selected = Object.freeze([...reviewerIds].sort());
    const body = JSON.stringify({ reviewer_ids: selected, policy_ref: "HANDOVER_ALL_V1",
      due_at: null, submission_note: null });
    let response: Response;
    try { response = await this.session.postProjectHandoverVersionSubmitReview(
      version.project_id, version.handover_analysis_id, version.handover_analysis_version_id,
      body, key); }
    catch (failure) {
      if (failure instanceof SessionClientError && (failure.code === "AUTH_RELOGIN_REQUIRED"
        || failure.code === "AUTH_CLIENT_BUSY")) fail(failure.code);
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
        if (typeof code === "string" && statuses[code] === response.status) {
          throw new HandoverSubmitReviewError(code as HandoverSubmitReviewErrorCode);
        }
        fail();
      }
      if (!exact(payload, ["data", "trace_id"]) || !record(payload.data)
        || !exact(payload.data, fields)) fail();
      const data = payload.data;
      if (!id(data.review_id) || !id(data.review_round_id) || data.subject_type !== "HND-02"
        || data.project_id !== version.project_id || data.handover_analysis_id !== version.handover_analysis_id
        || data.handover_analysis_version_id !== version.handover_analysis_version_id
        || data.policy_ref !== "HANDOVER_ALL_V1" || !Array.isArray(data.reviewer_ids)
        || data.reviewer_ids.length !== selected.length
        || data.reviewer_ids.some((value, index) => value !== selected[index])
        || data.state !== "IN_REVIEW" || data.round_no !== 1 || data.review_etag !== '"v1"'
        || response.headers.get("etag") !== data.review_etag
        || data.submitted_by !== actor.user.user_id || !instant(data.submitted_at)) fail();
      return Object.freeze({ ...data,
        reviewer_ids: Object.freeze([...data.reviewer_ids]) }) as unknown as HandoverReviewSubmission;
    } catch (failure) {
      if (failure instanceof HandoverSubmitReviewError) throw failure;
      return fail();
    }
  }
}
