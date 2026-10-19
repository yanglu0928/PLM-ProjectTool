/** Frozen REVIEW_LIST summaries; pending assignment is actor-only, not authority. */
export type ReviewListMode = "all" | "my_pending";
export interface ReviewListAssignment { readonly assignment_id: string; readonly state: "PENDING" | "DECIDED";
  readonly decision: "APPROVE" | "RETURN" | null; readonly decided_at: string | null }
export interface ReviewListRound { readonly review_round_id: string; readonly round_no: number;
  readonly subject_version_ref: string; readonly started_at: string;
  readonly my_assignment: ReviewListAssignment | null }
export interface ReviewListItem { readonly review_id: string; readonly project_id: string;
  readonly subject_ref: Readonly<{ resource_type: string; resource_id: string }>;
  readonly policy_code: string; readonly state: "DRAFT" | "IN_REVIEW" | "APPROVED" | "RETURNED" | "WITHDRAWN";
  readonly created_by: string; readonly created_at: string; readonly etag: string;
  readonly active_round: ReviewListRound | null }
export interface ReviewListPage { readonly items: readonly ReviewListItem[];
  readonly next_cursor: string | null; readonly has_more: boolean }

const messages = {
  REVIEW_LIST_INVALID: "项目或翻页参数无效。", AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许读取评审。", RESOURCE_NOT_FOUND: "项目不存在或无权查看评审。",
  REVIEW_LIST_UNAVAILABLE: "暂时无法读取评审待办，请刷新重试。",
} as const;
export type ReviewListErrorCode = keyof typeof messages;
export class ReviewListError extends Error {
  constructor(readonly code: ReviewListErrorCode) { super(messages[code]); this.name = "ReviewListError"; }
}
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const cursorShape = /^r1\.[A-Za-z0-9_-]{1,1536}$/;
const stamp = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/;
const etag = /^"v(0|[1-9]\d*)"$/;
const subjectCode = /^[A-Z][A-Z0-9_-]{0,63}$/;
const policyCode = /^[A-Z][A-Z0-9_]{0,63}$/;
const states = ["DRAFT", "IN_REVIEW", "APPROVED", "RETURNED", "WITHDRAWN"];
const itemFields = ["review_id", "project_id", "subject_ref", "policy_code", "state",
  "created_by", "created_at", "etag", "active_round"];
const roundFields = ["review_round_id", "round_no", "subject_version_ref", "started_at", "my_assignment"];
const assignmentFields = ["assignment_id", "state", "decision", "decided_at"];
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
function unavailable(): never { throw new ReviewListError("REVIEW_LIST_UNAVAILABLE"); }
function assignment(value: unknown): ReviewListAssignment | null {
  if (value === null) return null;
  if (!record(value) || !exact(value, assignmentFields) || !id(value.assignment_id)
    || !["PENDING", "DECIDED"].includes(String(value.state))
    || value.state === "PENDING" && (value.decision !== null || value.decided_at !== null)
    || value.state === "DECIDED" && (!["APPROVE", "RETURN"].includes(String(value.decision))
      || !instant(value.decided_at))) unavailable();
  return Object.freeze({ ...value }) as unknown as ReviewListAssignment;
}
function round(value: unknown): ReviewListRound | null {
  if (value === null) return null;
  if (!record(value) || !exact(value, roundFields) || !id(value.review_round_id)
    || !Number.isSafeInteger(value.round_no) || Number(value.round_no) < 1
    || !id(value.subject_version_ref) || !instant(value.started_at)) unavailable();
  return Object.freeze({ ...value, my_assignment: assignment(value.my_assignment) }) as unknown as ReviewListRound;
}
function item(value: unknown, project: string, mode: ReviewListMode): ReviewListItem {
  if (!record(value) || !exact(value, itemFields) || !id(value.review_id)
    || value.project_id !== project || !record(value.subject_ref)
    || !exact(value.subject_ref, ["resource_type", "resource_id"])
    || typeof value.subject_ref.resource_type !== "string"
    || !subjectCode.test(value.subject_ref.resource_type) || !id(value.subject_ref.resource_id)
    || typeof value.policy_code !== "string" || !policyCode.test(value.policy_code)
    || !states.includes(String(value.state)) || !id(value.created_by)
    || !instant(value.created_at) || typeof value.etag !== "string" || !etag.test(value.etag)) unavailable();
  const active = round(value.active_round);
  if ((value.state === "IN_REVIEW") !== (active !== null)
    || mode === "my_pending" && active?.my_assignment?.state !== "PENDING") unavailable();
  return Object.freeze({ ...value, subject_ref: Object.freeze({ ...value.subject_ref }),
    active_round: active }) as unknown as ReviewListItem;
}
export function parseReviewListPage(value: unknown, project: string, mode: ReviewListMode,
                                    size: number, previousCursor: string | null): ReviewListPage {
  if (!record(value) || !exact(value, ["items", "next_cursor", "has_more"])
    || !Array.isArray(value.items) || value.items.length > size || typeof value.has_more !== "boolean"
    || value.has_more && (typeof value.next_cursor !== "string" || !cursorShape.test(value.next_cursor)
      || value.next_cursor === previousCursor)
    || !value.has_more && value.next_cursor !== null) unavailable();
  const items = value.items.map(entry => item(entry, project, mode));
  const seen = new Set<string>();
  for (const entry of items) {
    if (seen.has(entry.review_id)) unavailable();
    seen.add(entry.review_id);
  }
  return Object.freeze({ items: Object.freeze(items), next_cursor: value.next_cursor,
    has_more: value.has_more }) as ReviewListPage;
}

export class ProjectReviewListClient {
  constructor(private readonly fetcher: typeof fetch = (input, init) => fetch(input, init),
              private readonly timeoutMs = 10_000) {}

  async list(project: string, mode: ReviewListMode = "my_pending", size = 50,
             next: string | null = null): Promise<ReviewListPage> {
    if (!id(project) || !["all", "my_pending"].includes(mode) || !Number.isSafeInteger(size)
      || size < 1 || size > 200 || next !== null && !cursorShape.test(next)) {
      throw new ReviewListError("REVIEW_LIST_INVALID");
    }
    const params = new URLSearchParams({ view: mode, page_size: String(size) });
    if (next !== null) params.set("cursor", next);
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const response = await this.fetcher(`/api/v1/projects/${project}/reviews?${params}`,
        { method: "GET", credentials: "same-origin", cache: "no-store", redirect: "error",
          headers: { Accept: "application/json" }, signal: controller.signal });
      if (controller.signal.aborted || response.headers.get("content-type")?.split(";")[0].trim().toLowerCase()
        !== "application/json" || response.headers.get("cache-control") !== "no-store") unavailable();
      const body: unknown = await response.json();
      if (!record(body) || !id(body.trace_id) || response.headers.get("x-trace-id") !== body.trace_id) unavailable();
      if (response.status !== 200) {
        const code = record(body.error) ? body.error.code : null;
        const known: Record<string, number> = { AUTH_SESSION_EXPIRED: 401,
          LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404 };
        if (typeof code === "string" && known[code] === response.status) {
          throw new ReviewListError(code as ReviewListErrorCode);
        }
        unavailable();
      }
      if (!exact(body, ["data", "trace_id"]) || response.headers.has("etag")) unavailable();
      return parseReviewListPage(body.data, project, mode, size, next);
    } catch (failure) {
      if (failure instanceof ReviewListError) throw failure;
      return unavailable();
    } finally { clearTimeout(timer); }
  }
}
