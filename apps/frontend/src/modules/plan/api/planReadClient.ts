/** Current Plan identity reads do not imply a version, WBS, approval or delivery. */
export interface PlanSummary {
  readonly plan_id: string; readonly project_id: string; readonly name: string;
  readonly plan_state: "ACTIVE" | "ARCHIVED";
  readonly current_approved_version_ref: null;
  readonly created_at: string; readonly etag: string;
}
export interface PlanCurrent extends PlanSummary { readonly created_by: string }
export interface PlanPage {
  readonly items: readonly PlanSummary[]; readonly next_cursor: string | null;
  readonly has_more: boolean;
}

const messages = {
  PLAN_INVALID_INPUT: "项目、实施计划或翻页参数无效。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许读取实施计划。",
  RESOURCE_NOT_FOUND: "实施计划不存在或无权查看。",
  PLAN_UNAVAILABLE: "暂时无法读取实施计划，请稍后重试。",
} as const;
export type PlanReadErrorCode = keyof typeof messages;
export class PlanReadError extends Error {
  constructor(readonly code: PlanReadErrorCode) {
    super(messages[code]); this.name = "PlanReadError";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const etag = /^"v(0|[1-9][0-9]*)"$/;
const cursor = /^[A-Za-z0-9_-]{1,512}\.[A-Za-z0-9_-]{43}$/;
const stamp = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/;
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
  return typeof value === "string" && stamp.test(value) && Number.isFinite(Date.parse(value))
    && new Date(value).toISOString().slice(0, 19) === value.slice(0, 19);
}
function label(value: unknown): value is string {
  return typeof value === "string" && value.length > 0 && value.length <= 500
    && value.trim() === value && !/\p{C}/u.test(value);
}
function orderKey(value: string): string {
  return value.slice(0, 19) + (value.length > 20 ? value.slice(20, -1).padEnd(6, "0") : "000000");
}
export function planFollows(previous: PlanSummary, next: PlanSummary): boolean {
  const earlier = orderKey(previous.created_at);
  const later = orderKey(next.created_at);
  return earlier > later || earlier === later && previous.plan_id > next.plan_id;
}
function fail(): never { throw new PlanReadError("PLAN_UNAVAILABLE"); }
const summaryFields = ["plan_id", "project_id", "name", "plan_state",
  "current_approved_version_ref", "created_at", "etag"] as const;
const detailFields = [...summaryFields, "created_by"] as const;

function summary(value: unknown, projectId: string, planId?: string,
                 detail = false): PlanSummary {
  if (!record(value) || !exact(value, detail ? detailFields : summaryFields)
    || !id(value.plan_id) || planId !== undefined && value.plan_id !== planId
    || value.project_id !== projectId || !label(value.name)
    || !["ACTIVE", "ARCHIVED"].includes(value.plan_state as string)
    || value.current_approved_version_ref !== null || !instant(value.created_at)
    || typeof value.etag !== "string" || !etag.test(value.etag)) fail();
  return Object.freeze({
    plan_id: value.plan_id as string, project_id: projectId, name: value.name as string,
    plan_state: value.plan_state as PlanSummary["plan_state"],
    current_approved_version_ref: null, created_at: value.created_at as string,
    etag: value.etag as string,
  });
}

export function parsePlanCurrent(value: unknown, projectId: string,
                                 planId: string): PlanCurrent {
  const base = summary(value, projectId, planId, true);
  if (!record(value) || !id(value.created_by)) fail();
  return Object.freeze({ ...base, created_by: value.created_by });
}

export function parsePlanPage(value: unknown, projectId: string, pageSize: number,
                              previousCursor: string | null = null): PlanPage {
  if (!record(value) || !exact(value, ["items", "next_cursor", "has_more"])
    || !Array.isArray(value.items) || value.items.length > pageSize
    || typeof value.has_more !== "boolean"
    || value.has_more && (value.items.length === 0 || typeof value.next_cursor !== "string"
      || !cursor.test(value.next_cursor) || value.next_cursor === previousCursor)
    || !value.has_more && value.next_cursor !== null) fail();
  const items = value.items.map(item => summary(item, projectId));
  if (items.some((item, index) => index > 0 && !planFollows(items[index - 1]!, item))) fail();
  return Object.freeze({ items: Object.freeze(items), next_cursor: value.next_cursor as string | null,
    has_more: value.has_more });
}

export class PlanReadClient {
  constructor(private readonly fetcher: typeof fetch = fetch,
              private readonly timeoutMs = 10_000) {}

  async list(projectId: string, pageSize = 50, next: string | null = null): Promise<PlanPage> {
    if (!id(projectId) || !Number.isSafeInteger(pageSize) || pageSize < 1 || pageSize > 200
      || next !== null && !cursor.test(next)) throw new PlanReadError("PLAN_INVALID_INPUT");
    const params = new URLSearchParams({ page_size: String(pageSize) });
    if (next !== null) params.set("cursor", next);
    return parsePlanPage(await this.get(`/api/v1/projects/${projectId}/plans?${params}`),
      projectId, pageSize, next);
  }

  async current(projectId: string, planId: string): Promise<PlanCurrent> {
    if (!id(projectId) || !id(planId)) throw new PlanReadError("PLAN_INVALID_INPUT");
    const { data, etag: header } = await this.get(
      `/api/v1/projects/${projectId}/plans/${planId}`, true) as { data: unknown; etag: string };
    const result = parsePlanCurrent(data, projectId, planId);
    if (header !== result.etag) fail();
    return result;
  }

  private async get(path: string, requireEtag = false): Promise<unknown> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const fetcher = this.fetcher;
      const response = await fetcher(path, { method: "GET", credentials: "same-origin",
        cache: "no-store", redirect: "error", headers: { Accept: "application/json" },
        signal: controller.signal });
      if (controller.signal.aborted
        || response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") fail();
      const payload: unknown = await response.json();
      if (!record(payload) || !id(payload.trace_id)) fail();
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const statuses: Readonly<Record<string, number>> = { AUTH_SESSION_EXPIRED: 401,
          LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404 };
        if (typeof code === "string" && statuses[code] === response.status) {
          throw new PlanReadError(code as PlanReadErrorCode);
        }
        fail();
      }
      if (!exact(payload, ["data", "trace_id"])) fail();
      if (!requireEtag) return payload.data;
      const header = response.headers.get("etag");
      if (header === null || !etag.test(header)) fail();
      return { data: payload.data, etag: header };
    } catch (error) {
      if (error instanceof PlanReadError) throw error;
      return fail();
    } finally { clearTimeout(timer); }
  }
}
