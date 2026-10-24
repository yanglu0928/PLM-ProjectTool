/** Frozen CAP_VERSION_SUBMIT_REVIEW; an IN_REVIEW receipt is never approval. */
import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";
import type { CapabilityVersion } from "./capabilityReadClient";

export interface CapabilityReviewSubmission {
  readonly review_id: string; readonly review_round_id: string; readonly subject_type: "CAP-01";
  readonly baseline_id: string; readonly baseline_version_id: string;
  readonly policy_ref: "DEPLOYMENT_ALL_V1"; readonly reviewer_ids: readonly string[];
  readonly state: "IN_REVIEW"; readonly round_no: 1; readonly review_etag: '"v1"';
  readonly submitted_by: string; readonly submitted_at: string;
}
const messages = {
  CAP_REVIEW_INVALID: "能力版本、评审人或操作号无效。",
  CAP_REVIEW_UNCERTAIN: "送审结果无法确认；请保留原操作号和评审人，核对评审与审计记录。",
  AUTH_RELOGIN_REQUIRED: "请重新登录后再送审。", AUTH_CLIENT_BUSY: "会话正在处理其他操作。",
  AUTH_SESSION_EXPIRED: "会话已失效。", AUTH_CSRF_INVALID: "登录状态已变化。",
  LICENSE_OPERATION_DENIED: "当前许可不允许送审。", RESOURCE_NOT_FOUND: "版本不存在或无权送审。",
  VALIDATION_FAILED: "送审请求或当前来源不符合要求。",
  BUSINESS_REVIEW_NOT_ELIGIBLE: "当前能力版本、来源或评审人资格不满足送审条件。",
  CONFLICT_IDEMPOTENCY: "原操作号与送审内容冲突，请核对评审历史。",
  CONFLICT_VERSION: "版本状态已变化，请刷新。",
  SYSTEM_UNAVAILABLE: "送审服务暂不可用；请保留原操作号。",
} as const;
export type CapabilityReviewSubmitErrorCode = keyof typeof messages;
export class CapabilityReviewSubmitError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: CapabilityReviewSubmitErrorCode) {
    super(messages[code]); this.name = "CapabilityReviewSubmitError";
    this.uncertain = code === "CAP_REVIEW_UNCERTAIN" || code === "SYSTEM_UNAVAILABLE";
  }
}
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const fields = ["review_id", "review_round_id", "subject_type", "baseline_id",
  "baseline_version_id", "policy_ref", "reviewer_ids", "state", "round_no",
  "review_etag", "submitted_by", "submitted_at"] as const;
const statuses: Readonly<Record<string, number>> = {
  AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403, LICENSE_OPERATION_DENIED: 403,
  RESOURCE_NOT_FOUND: 404, VALIDATION_FAILED: 422, BUSINESS_REVIEW_NOT_ELIGIBLE: 422,
  CONFLICT_IDEMPOTENCY: 409, CONFLICT_VERSION: 409, SYSTEM_UNAVAILABLE: 503,
};
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function exact(value: Record<string, unknown>, names: readonly string[]): boolean {
  return Object.keys(value).length === names.length && names.every(name => Object.hasOwn(value, name));
}
function id(value: unknown): value is string { return typeof value === "string" && uuid.test(value)
  && value !== "00000000-0000-0000-0000-000000000000"; }
function instant(value: unknown): value is string {
  return typeof value === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/.test(value)
    && Number.isFinite(Date.parse(value));
}
function fail(code: CapabilityReviewSubmitErrorCode = "CAP_REVIEW_UNCERTAIN"): never {
  throw new CapabilityReviewSubmitError(code);
}
export class CapabilityVersionSubmitReviewClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) fail("CAP_REVIEW_INVALID");
  }
  async submit(version: CapabilityVersion, reviewerIds: readonly string[], key: string): Promise<CapabilityReviewSubmission> {
    if (!record(version) || !id(version.baseline_id) || !id(version.baseline_version_id)
      || version.state !== "DRAFT" || version.review_ref !== null || version.review_round_ref !== null
      || !Array.isArray(reviewerIds) || reviewerIds.length < 1 || reviewerIds.length > 32
      || reviewerIds.some(value => !id(value)) || new Set(reviewerIds).size !== reviewerIds.length
      || typeof key !== "string" || !/^[\x20-\x7e]{16,128}$/.test(key)) fail("CAP_REVIEW_INVALID");
    const actor = this.session.view;
    if (!actor || actor.password_change_required || !this.session.canSubmit
      || actor.deployment_role !== "DEPLOYMENT_ADMIN") fail("CAP_REVIEW_INVALID");
    const selected = Object.freeze([...reviewerIds].sort());
    const body = JSON.stringify({ reviewer_ids: selected, policy_ref: "DEPLOYMENT_ALL_V1",
      due_at: null, submission_note: null });
    let response: Response;
    try { response = await this.session.postGlobalCapabilityVersionSubmitReview(
      version.baseline_id, version.baseline_version_id, body, key); }
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
          throw new CapabilityReviewSubmitError(code as CapabilityReviewSubmitErrorCode);
        }
        fail();
      }
      if (!exact(payload, ["data", "trace_id"]) || !record(payload.data)
        || !exact(payload.data, fields)) fail();
      const data = payload.data;
      if (!id(data.review_id) || !id(data.review_round_id) || data.subject_type !== "CAP-01"
        || data.baseline_id !== version.baseline_id || data.baseline_version_id !== version.baseline_version_id
        || data.policy_ref !== "DEPLOYMENT_ALL_V1" || !Array.isArray(data.reviewer_ids)
        || data.reviewer_ids.length !== selected.length
        || data.reviewer_ids.some((value, index) => value !== selected[index])
        || data.state !== "IN_REVIEW" || data.round_no !== 1 || data.review_etag !== '"v1"'
        || response.headers.get("etag") !== data.review_etag
        || data.submitted_by !== actor.user.user_id || !instant(data.submitted_at)) fail();
      return Object.freeze({ ...data,
        reviewer_ids: Object.freeze([...data.reviewer_ids]) }) as unknown as CapabilityReviewSubmission;
    } catch (failure) {
      if (failure instanceof CapabilityReviewSubmitError) throw failure;
      return fail();
    }
  }
}
