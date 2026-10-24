/** CR-CAP-005 exact GLOBAL CAP-01 Review transport; never PROJECT fallback. */
import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";
import { parseItem, parseVersion, type CapabilityItem,
  type CapabilityVersion, type CapabilityPage } from "./capabilityReadClient";

export type GlobalReviewDecisionKind = "APPROVE" | "RETURN";
export type GlobalReviewState = "IN_REVIEW" | "APPROVED" | "RETURNED";
export interface GlobalReviewDecision { readonly decision_id: string; readonly reviewer_id: string;
  readonly decision: GlobalReviewDecisionKind; readonly comment: string | null; readonly decided_at: string }
export interface GlobalCapabilityReview { readonly review_id: string; readonly subject_type: "CAP-01";
  readonly baseline_id: string; readonly baseline_version_id: string; readonly policy_ref: "DEPLOYMENT_ALL_V1";
  readonly review_round_id: string; readonly round_no: 1; readonly reviewer_ids: readonly string[];
  readonly decisions: readonly GlobalReviewDecision[]; readonly state: GlobalReviewState;
  readonly review_etag: string; readonly round_etag: string;
  readonly submitted_by: string; readonly submitted_at: string }
export interface GlobalReviewDecisionReceipt { readonly review_id: string; readonly review_round_id: string;
  readonly baseline_version_id: string; readonly actor_id: string; readonly decision: GlobalReviewDecisionKind;
  readonly decision_id: string; readonly state: GlobalReviewState; readonly review_etag: string;
  readonly round_etag: string; readonly occurred_at: string; readonly event_id: string }

const messages = {
  CAP_GLOBAL_REVIEW_INVALID: "评审、版本或决定信息无效。",
  CAP_GLOBAL_REVIEW_UNCERTAIN: "决定结果无法确认；请保留原决定和操作号，核对评审及审计记录。",
  AUTH_RELOGIN_REQUIRED: "请重新登录后处理评审。", AUTH_CLIENT_BUSY: "会话正在处理其他操作。",
  AUTH_SESSION_EXPIRED: "会话已失效。", AUTH_CSRF_INVALID: "登录状态已变化。",
  LICENSE_OPERATION_DENIED: "当前许可不允许处理评审。",
  RESOURCE_NOT_FOUND: "评审不存在或当前账户无权处理。",
  VALIDATION_FAILED: "请求或当前评审不符合要求。", REVIEW_COMMENT_REQUIRED: "退回时必须填写明确意见。",
  REVIEW_DECISION_EXISTS: "你已完成本轮决定。", CONFLICT_IDEMPOTENCY: "原操作号与决定不一致，已停止重试。",
  CONFLICT_STATE: "评审状态已变化，请刷新。", CONFLICT_VERSION: "版本状态已变化，请刷新。",
  SYSTEM_UNAVAILABLE: "评审服务暂不可用；请保留原操作号。",
} as const;
export type GlobalReviewErrorCode = keyof typeof messages;
export class GlobalReviewError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: GlobalReviewErrorCode) {
    super(messages[code]); this.name = "GlobalReviewError";
    this.uncertain = code === "CAP_GLOBAL_REVIEW_UNCERTAIN" || code === "SYSTEM_UNAVAILABLE";
  }
}
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const id = (v: unknown): v is string => typeof v === "string" && uuid.test(v)
  && v !== "00000000-0000-0000-0000-000000000000";
const etag = /^"v(0|[1-9]\d*)"$/;
const cursorPattern = /^[A-Za-z0-9_-]{1,512}\.[A-Za-z0-9_-]{43}$/;
const stamp = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/;
const instant = (v: unknown): v is string => typeof v === "string" && stamp.test(v) && Number.isFinite(Date.parse(v));
const record = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const exact = (v: Record<string, unknown>, names: readonly string[]) =>
  Object.keys(v).length === names.length && names.every(name => Object.hasOwn(v, name));
const detailFields = ["review_id", "subject_type", "baseline_id", "baseline_version_id", "policy_ref",
  "review_round_id", "round_no", "reviewer_ids", "decisions", "state", "review_etag", "round_etag",
  "submitted_by", "submitted_at"] as const;
const decisionFields = ["decision_id", "reviewer_id", "decision", "comment", "decided_at"] as const;
const receiptFields = ["review_id", "review_round_id", "baseline_version_id", "actor_id", "decision",
  "decision_id", "state", "review_etag", "round_etag", "occurred_at", "event_id"] as const;
const statuses: Readonly<Record<string, number>> = {
  AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403, LICENSE_OPERATION_DENIED: 403,
  RESOURCE_NOT_FOUND: 404, VALIDATION_FAILED: 422, REVIEW_COMMENT_REQUIRED: 422,
  REVIEW_DECISION_EXISTS: 409, CONFLICT_IDEMPOTENCY: 409, CONFLICT_STATE: 409,
  CONFLICT_VERSION: 409, SYSTEM_UNAVAILABLE: 503,
};
function fail(code: GlobalReviewErrorCode = "CAP_GLOBAL_REVIEW_UNCERTAIN"): never { throw new GlobalReviewError(code); }
async function body(response: Response): Promise<Record<string, unknown>> {
  if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json"
    || response.headers.get("cache-control") !== "no-store") fail();
  const payload: unknown = await response.json();
  if (!record(payload) || !id(payload.trace_id) || response.headers.get("x-trace-id") !== payload.trace_id) fail();
  return payload;
}
function checkError(payload: Record<string, unknown>, status: number): never {
  const code = record(payload.error) ? payload.error.code : null;
  if (typeof code === "string" && statuses[code] === status) fail(code as GlobalReviewErrorCode);
  return fail();
}
function parseDetail(raw: unknown, reviewId: string, baselineId: string, versionId: string): GlobalCapabilityReview {
  if (!record(raw) || !exact(raw, detailFields) || raw.review_id !== reviewId
    || raw.subject_type !== "CAP-01" || raw.baseline_id !== baselineId
    || raw.baseline_version_id !== versionId || raw.policy_ref !== "DEPLOYMENT_ALL_V1"
    || !id(raw.review_round_id) || raw.round_no !== 1
    || !Array.isArray(raw.reviewer_ids) || raw.reviewer_ids.length < 1 || raw.reviewer_ids.length > 32
    || raw.reviewer_ids.some(value => !id(value)) || new Set(raw.reviewer_ids).size !== raw.reviewer_ids.length
    || !Array.isArray(raw.decisions) || raw.decisions.length > raw.reviewer_ids.length
    || !["IN_REVIEW", "APPROVED", "RETURNED"].includes(String(raw.state))
    || !etag.test(String(raw.review_etag)) || !etag.test(String(raw.round_etag))
    || !id(raw.submitted_by) || !instant(raw.submitted_at)) fail();
  const decided = new Set<string>();
  for (const item of raw.decisions) {
    if (!record(item) || !exact(item, decisionFields) || !id(item.decision_id)
      || !id(item.reviewer_id) || !raw.reviewer_ids.includes(item.reviewer_id)
      || decided.has(item.reviewer_id) || !["APPROVE", "RETURN"].includes(String(item.decision))
      || item.comment !== null && typeof item.comment !== "string"
      || item.decision === "RETURN" && !(item.comment as string)?.trim()
      || !instant(item.decided_at)) fail();
    decided.add(item.reviewer_id);
  }
  if (raw.state === "APPROVED" && (decided.size !== raw.reviewer_ids.length
    || raw.decisions.some(item => item.decision !== "APPROVE"))) fail();
  if (raw.state === "RETURNED" && !raw.decisions.some(item => item.decision === "RETURN")) fail();
  if (raw.state === "IN_REVIEW" && (decided.size === raw.reviewer_ids.length
    || raw.decisions.some(item => item.decision === "RETURN"))) fail();
  return Object.freeze({ ...raw, reviewer_ids: Object.freeze([...raw.reviewer_ids]),
    decisions: Object.freeze(raw.decisions.map(item => Object.freeze({ ...item }))) }) as unknown as GlobalCapabilityReview;
}

export class GlobalCapabilityReviewClient {
  constructor(private readonly session: SessionClient,
    private readonly fetcher: typeof fetch = (input, init) => fetch(input, init),
    private readonly timeoutMs = 10_000) {
    if (!(session instanceof SessionClient) || !Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 30_000)
      fail("CAP_GLOBAL_REVIEW_INVALID");
  }
  async read(reviewId: string, baselineId: string, versionId: string): Promise<GlobalCapabilityReview> {
    if (![reviewId, baselineId, versionId].every(id)) fail("CAP_GLOBAL_REVIEW_INVALID");
    const controller = new AbortController(); const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const response = await this.fetcher(`/api/v1/global/reviews/${reviewId}`, {
        method: "GET", credentials: "same-origin", cache: "no-store", redirect: "error",
        headers: { Accept: "application/json" }, signal: controller.signal,
      });
      if (controller.signal.aborted) fail();
      const payload = await body(response);
      if (response.status !== 200) checkError(payload, response.status);
      if (!exact(payload, ["data", "trace_id"]) || !record(payload.data)
        || response.headers.get("etag") !== payload.data.review_etag) fail();
      return parseDetail(payload.data, reviewId, baselineId, versionId);
    } catch (failure) { if (failure instanceof GlobalReviewError) throw failure; return fail(); }
    finally { clearTimeout(timer); }
  }
  async fixedVersion(review: GlobalCapabilityReview): Promise<CapabilityVersion> {
    const payload = await this.#readFixed(`/api/v1/global/reviews/${review.review_id}/fixed-version`);
    if (!exact(payload, ["data", "trace_id"]) || !record(payload.data)
      || !exact(payload.data, ["review_id", "review_round_id", "version", "review_etag"])
      || payload.data.review_id !== review.review_id
      || payload.data.review_round_id !== review.review_round_id
      || payload.data.review_etag !== review.review_etag) fail();
    let version: CapabilityVersion;
    try { version = parseVersion(payload.data.version, review.baseline_id); }
    catch { return fail(); }
    if (version.baseline_version_id !== review.baseline_version_id
      || version.review_ref !== review.review_id
      || version.review_round_ref !== review.review_round_id
      || version.state !== review.state) fail();
    return version;
  }
  async fixedItems(review: GlobalCapabilityReview, version: CapabilityVersion,
    cursor: string | null = null): Promise<CapabilityPage<CapabilityItem>> {
    if (version.baseline_id !== review.baseline_id
      || version.baseline_version_id !== review.baseline_version_id
      || version.review_ref !== review.review_id
      || version.review_round_ref !== review.review_round_id
      || cursor !== null && !cursorPattern.test(cursor)) fail("CAP_GLOBAL_REVIEW_INVALID");
    const path = `/api/v1/global/reviews/${review.review_id}/fixed-items?page_size=50`
      + (cursor === null ? "" : `&cursor=${encodeURIComponent(cursor)}`);
    const payload = await this.#readFixed(path);
    if (!exact(payload, ["data", "trace_id"]) || !record(payload.data)
      || !exact(payload.data, ["review_id", "review_round_id", "baseline_version_id",
        "items", "next_cursor", "has_more", "review_etag"])
      || payload.data.review_id !== review.review_id
      || payload.data.review_round_id !== review.review_round_id
      || payload.data.baseline_version_id !== version.baseline_version_id
      || payload.data.review_etag !== review.review_etag
      || !Array.isArray(payload.data.items) || payload.data.items.length > 50
      || typeof payload.data.has_more !== "boolean"
      || (payload.data.next_cursor === null) !== !payload.data.has_more
      || payload.data.has_more && (payload.data.items.length === 0
        || typeof payload.data.next_cursor !== "string"
        || !cursorPattern.test(payload.data.next_cursor))) fail();
    let items: CapabilityItem[];
    try { items = payload.data.items.map(value => parseItem(value, review.baseline_id, version.baseline_version_id)); }
    catch { return fail(); }
    if (items.some((value, index) => index > 0 && value.ordinal <= items[index - 1]!.ordinal)
      || new Set(items.map(value => value.capability_item_id)).size !== items.length) fail();
    return Object.freeze({ items: Object.freeze(items), next_cursor: payload.data.next_cursor,
      has_more: payload.data.has_more }) as CapabilityPage<CapabilityItem>;
  }
  async #readFixed(path: string): Promise<Record<string, unknown>> {
    const controller = new AbortController(); const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const response = await this.fetcher(path, {
        method: "GET", credentials: "same-origin", cache: "no-store", redirect: "error",
        headers: { Accept: "application/json" }, signal: controller.signal,
      });
      if (controller.signal.aborted) fail();
      const payload = await body(response);
      if (response.status !== 200) checkError(payload, response.status);
      if (!exact(payload, ["data", "trace_id"]) || !record(payload.data)
        || response.headers.get("etag") !== payload.data.review_etag) fail();
      return payload;
    } catch (failure) { if (failure instanceof GlobalReviewError) throw failure; return fail(); }
    finally { clearTimeout(timer); }
  }
  async decide(before: GlobalCapabilityReview, kind: GlobalReviewDecisionKind,
    comment: string | null, key: string, allowReplay = false): Promise<GlobalReviewDecisionReceipt> {
    const actor = this.session.view?.user.user_id;
    if (!actor || !this.session.canSubmit || this.session.view?.password_change_required
      || !before.reviewer_ids.includes(actor)
      || !allowReplay && (before.state !== "IN_REVIEW"
        || before.decisions.some(value => value.reviewer_id === actor))
      || !["APPROVE", "RETURN"].includes(kind) || kind === "APPROVE" && comment !== null
      || kind === "RETURN" && (typeof comment !== "string" || !comment.trim())
      || typeof key !== "string" || !/^[\x20-\x7e]{16,128}$/.test(key)) fail("CAP_GLOBAL_REVIEW_INVALID");
    let response: Response;
    try {
      response = await this.session.postGlobalCapabilityReviewDecision(before.review_id,
        before.review_round_id, JSON.stringify({ decision: kind, comment: kind === "RETURN" ? comment!.trim() : null }), key);
    } catch (failure) {
      if (failure instanceof SessionClientError && ["AUTH_RELOGIN_REQUIRED", "AUTH_CLIENT_BUSY"].includes(failure.code))
        fail(failure.code as GlobalReviewErrorCode);
      return fail();
    }
    try {
      const payload = await body(response);
      if (response.status !== 200) checkError(payload, response.status);
      if (!exact(payload, ["data", "trace_id"]) || !record(payload.data) || !exact(payload.data, receiptFields)) fail();
      const data = payload.data;
      if (data.review_id !== before.review_id || data.review_round_id !== before.review_round_id
        || data.baseline_version_id !== before.baseline_version_id || data.actor_id !== actor
        || data.decision !== kind || !id(data.decision_id) || !["IN_REVIEW", "APPROVED", "RETURNED"].includes(String(data.state))
        || !etag.test(String(data.review_etag)) || !etag.test(String(data.round_etag))
        || !instant(data.occurred_at) || !id(data.event_id)
        || response.headers.get("etag") !== data.review_etag) fail();
      return Object.freeze({ ...data }) as unknown as GlobalReviewDecisionReceipt;
    } catch (failure) { if (failure instanceof GlobalReviewError) throw failure; return fail(); }
  }
}
