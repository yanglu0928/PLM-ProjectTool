/** Fixed PlanVersion history reads. Snapshot references never imply current qualification. */
export type PlanVersionState = "DRAFT" | "IN_REVIEW" | "APPROVED" | "RETURNED" | "SUPERSEDED" | "RESTRICTED";
export interface PlanVersionSummary {
  readonly plan_version_id: string; readonly plan_id: string; readonly project_id: string;
  readonly version_no: number; readonly version_state: PlanVersionState; readonly created_by: string;
  readonly supersedes_version_ref: string | null; readonly review_ref: string | null;
  readonly review_round_ref: string | null; readonly created_at: string;
}
export interface PlanVersionDetail extends PlanVersionSummary {
  readonly calendar_ref: string | null;
  readonly approved_solution_refs: readonly unknown[];
  readonly wbs_items: readonly unknown[];
  readonly dependencies: readonly unknown[];
  readonly milestones: readonly unknown[];
  readonly exclusions: readonly unknown[];
}
export interface PlanVersionPage { readonly items: readonly PlanVersionSummary[]; readonly next_cursor: string | null; readonly has_more: boolean; }
const messages = { PLAN_VERSION_READ_INVALID: "项目、计划、版本或翻页参数无效。", AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许读取计划版本。", RESOURCE_NOT_FOUND: "计划版本不存在或无权查看。",
  PLAN_VERSION_READ_UNAVAILABLE: "暂时无法读取计划版本，请稍后重试。" } as const;
export type PlanVersionReadErrorCode = keyof typeof messages;
export class PlanVersionReadError extends Error {
  constructor(readonly code: PlanVersionReadErrorCode) { super(messages[code]); this.name = "PlanVersionReadError"; }
}
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const cursor = /^[A-Za-z0-9_-]{1,4096}\.[A-Za-z0-9_-]{43}$/;
const stamp = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/;
const calendarCode = /^[A-Z][A-Z0-9_]{0,127}$/;
const states = ["DRAFT", "IN_REVIEW", "APPROVED", "RETURNED", "SUPERSEDED", "RESTRICTED"];
const summaryKeys = ["plan_version_id", "plan_id", "project_id", "version_no", "version_state", "created_by",
  "supersedes_version_ref", "review_ref", "review_round_ref", "created_at"] as const;
const detailKeys = [...summaryKeys, "calendar_ref", "approved_solution_refs", "wbs_items", "dependencies", "milestones", "exclusions"] as const;
function record(v: unknown): v is Record<string, unknown> { return typeof v === "object" && v !== null && !Array.isArray(v); }
function exact(v: Record<string, unknown>, keys: readonly string[]) { return Object.keys(v).length === keys.length && keys.every(k => Object.hasOwn(v, k)); }
function id(v: unknown): v is string { return typeof v === "string" && uuid.test(v) && v !== "00000000-0000-0000-0000-000000000000"; }
function maybeId(v: unknown): v is string | null { return v === null || id(v); }
function fail(): never { throw new PlanVersionReadError("PLAN_VERSION_READ_UNAVAILABLE"); }
function instant(v: unknown): v is string { return typeof v === "string" && stamp.test(v) && Number.isFinite(Date.parse(v))
  && new Date(v).toISOString().slice(0, 19) === v.slice(0, 19); }
function summary(v: unknown, project: string, plan: string, version?: string): PlanVersionSummary {
  if (!record(v) || !exact(v, version === undefined ? summaryKeys : detailKeys)
    || !id(v.plan_version_id) || version !== undefined && v.plan_version_id !== version
    || v.project_id !== project || v.plan_id !== plan || typeof v.version_no !== "number"
    || !Number.isSafeInteger(v.version_no) || v.version_no < 1 || !states.includes(v.version_state as string)
    || !id(v.created_by) || !maybeId(v.supersedes_version_ref) || !maybeId(v.review_ref)
    || !maybeId(v.review_round_ref) || (v.review_ref === null) !== (v.review_round_ref === null)
    || !instant(v.created_at)) fail();
  return Object.freeze(Object.fromEntries(summaryKeys.map(k => [k, v[k]]))) as unknown as PlanVersionSummary;
}
export function parsePlanVersionPage(v: unknown, project: string, plan: string, size: number, previous: string | null): PlanVersionPage {
  if (!record(v) || !exact(v, ["items", "next_cursor", "has_more"]) || !Array.isArray(v.items)
    || v.items.length > size || typeof v.has_more !== "boolean"
    || v.has_more && (v.items.length === 0 || typeof v.next_cursor !== "string" || !cursor.test(v.next_cursor) || v.next_cursor === previous)
    || !v.has_more && v.next_cursor !== null) fail();
  const items = v.items.map(item => summary(item, project, plan));
  if (items.some((item, i) => i > 0 && items[i - 1]!.version_no <= item.version_no)) fail();
  return Object.freeze({ items: Object.freeze(items), next_cursor: v.next_cursor as string | null, has_more: v.has_more });
}
export function parsePlanVersionDetail(v: unknown, project: string, plan: string, version: string): PlanVersionDetail {
  const base = summary(v, project, plan, version);
  if (!record(v) || !(v.calendar_ref === null || typeof v.calendar_ref === "string" && calendarCode.test(v.calendar_ref))
    || !Array.isArray(v.approved_solution_refs) || !v.approved_solution_refs.every(record)
    || !Array.isArray(v.wbs_items) || !v.wbs_items.every(record)
    || !Array.isArray(v.dependencies) || !v.dependencies.every(record)
    || !Array.isArray(v.milestones) || !v.milestones.every(record)
    || !Array.isArray(v.exclusions) || !v.exclusions.every(record)) fail();
  return Object.freeze({ ...base, calendar_ref: v.calendar_ref,
    approved_solution_refs: Object.freeze([...v.approved_solution_refs]), wbs_items: Object.freeze([...v.wbs_items]),
    dependencies: Object.freeze([...v.dependencies]), milestones: Object.freeze([...v.milestones]),
    exclusions: Object.freeze([...v.exclusions]) });
}
export class PlanVersionReadClient {
  constructor(private readonly fetcher: typeof fetch = fetch, private readonly timeoutMs = 10_000) {}
  async list(project: string, plan: string, size = 50, next: string | null = null): Promise<PlanVersionPage> {
    if (!id(project) || !id(plan) || !Number.isSafeInteger(size) || size < 1 || size > 100 || next !== null && !cursor.test(next))
      throw new PlanVersionReadError("PLAN_VERSION_READ_INVALID");
    const params = new URLSearchParams({ page_size: String(size) }); if (next) params.set("cursor", next);
    return parsePlanVersionPage(await this.get(`/api/v1/projects/${project}/plans/${plan}/versions?${params}`), project, plan, size, next);
  }
  async detail(project: string, plan: string, version: string): Promise<PlanVersionDetail> {
    if (!id(project) || !id(plan) || !id(version)) throw new PlanVersionReadError("PLAN_VERSION_READ_INVALID");
    return parsePlanVersionDetail(await this.get(`/api/v1/projects/${project}/plans/${plan}/versions/${version}`), project, plan, version);
  }
  private async get(path: string): Promise<unknown> {
    const controller = new AbortController(); const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      // Native Window.fetch rejects when invoked with the client instance as its receiver.
      const fetcher = this.fetcher;
      const response = await fetcher(path, { method: "GET", credentials: "same-origin", cache: "no-store", redirect: "error",
        headers: { Accept: "application/json" }, signal: controller.signal });
      if (controller.signal.aborted || response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json"
        || response.headers.get("cache-control") !== "no-store") fail();
      const payload: unknown = await response.json();
      if (!record(payload) || !id(payload.trace_id) || response.headers.get("x-trace-id") !== payload.trace_id) fail();
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const expected: Readonly<Record<string, number>> = { AUTH_SESSION_EXPIRED: 401, LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404 };
        if (typeof code === "string" && expected[code] === response.status) throw new PlanVersionReadError(code as PlanVersionReadErrorCode);
        fail();
      }
      if (!exact(payload, ["data", "trace_id"]) || response.headers.has("etag")) fail(); return payload.data;
    } catch (e) { if (e instanceof PlanVersionReadError) throw e; return fail(); } finally { clearTimeout(timer); }
  }
}
