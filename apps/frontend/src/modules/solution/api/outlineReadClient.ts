/** SolutionOutline identity reads never imply an approved formal solution. */
export interface OutlineSummary {
  readonly solution_outline_id: string; readonly project_id: string;
  readonly name: string; readonly outline_state: "ACTIVE" | "ARCHIVED";
  readonly current_approved_version_ref: string | null;
  readonly created_at: string; readonly etag: string;
}
export interface OutlineCurrent extends OutlineSummary { readonly created_by: string }
export interface OutlinePage {
  readonly items: readonly OutlineSummary[]; readonly next_cursor: string | null;
  readonly has_more: boolean;
}

const messages = {
  OUTLINE_INVALID_INPUT: "项目、方案目录或翻页参数无效。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许读取方案目录。",
  RESOURCE_NOT_FOUND: "方案目录不存在或无权查看。",
  OUTLINE_UNAVAILABLE: "暂时无法读取方案目录，请稍后重试。",
} as const;
export type OutlineReadErrorCode = keyof typeof messages;
export class OutlineReadError extends Error {
  constructor(readonly code: OutlineReadErrorCode) {
    super(messages[code]); this.name = "OutlineReadError";
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
function fail(): never { throw new OutlineReadError("OUTLINE_UNAVAILABLE"); }
const summaryFields = ["solution_outline_id", "project_id", "name", "outline_state",
  "current_approved_version_ref", "created_at", "etag"] as const;
const detailFields = [...summaryFields, "created_by"] as const;

function summary(value: unknown, projectId: string, outlineId?: string,
                 detail = false): OutlineSummary {
  if (!record(value) || !exact(value, detail ? detailFields : summaryFields)
    || !id(value.solution_outline_id)
    || outlineId !== undefined && value.solution_outline_id !== outlineId
    || value.project_id !== projectId || !label(value.name)
    || !["ACTIVE", "ARCHIVED"].includes(value.outline_state as string)
    || value.current_approved_version_ref !== null && !id(value.current_approved_version_ref)
    || !instant(value.created_at)
    || typeof value.etag !== "string" || !etag.test(value.etag)) fail();
  return Object.freeze({
    solution_outline_id: value.solution_outline_id as string,
    project_id: projectId, name: value.name as string,
    outline_state: value.outline_state as OutlineSummary["outline_state"],
    current_approved_version_ref: value.current_approved_version_ref as string | null,
    created_at: value.created_at as string, etag: value.etag as string,
  });
}

export function parseOutlineCurrent(value: unknown, projectId: string,
                                    outlineId: string): OutlineCurrent {
  const base = summary(value, projectId, outlineId, true);
  if (!record(value) || !id(value.created_by)) fail();
  return Object.freeze({ ...base, created_by: value.created_by });
}

export function parseOutlinePage(value: unknown, projectId: string, pageSize: number,
                                 previousCursor: string | null = null): OutlinePage {
  if (!record(value) || !exact(value, ["items", "next_cursor", "has_more"])
    || !Array.isArray(value.items) || value.items.length > pageSize
    || typeof value.has_more !== "boolean"
    || value.has_more && (value.items.length === 0 || typeof value.next_cursor !== "string"
      || !cursor.test(value.next_cursor) || value.next_cursor === previousCursor)
    || !value.has_more && value.next_cursor !== null) fail();
  const items = value.items.map(item => summary(item, projectId));
  if (items.some((item, index) => index > 0
    && items[index - 1]!.solution_outline_id >= item.solution_outline_id)) fail();
  return Object.freeze({ items: Object.freeze(items), next_cursor: value.next_cursor as string | null,
    has_more: value.has_more });
}

export class OutlineReadClient {
  constructor(private readonly fetcher: typeof fetch = fetch,
              private readonly timeoutMs = 10_000) {}

  async list(projectId: string, pageSize = 50, next: string | null = null): Promise<OutlinePage> {
    if (!id(projectId) || !Number.isSafeInteger(pageSize) || pageSize < 1 || pageSize > 100
      || next !== null && !cursor.test(next)) throw new OutlineReadError("OUTLINE_INVALID_INPUT");
    const params = new URLSearchParams({ page_size: String(pageSize) });
    if (next !== null) params.set("cursor", next);
    return parseOutlinePage(await this.get(`/api/v1/projects/${projectId}/solution-outlines?${params}`),
      projectId, pageSize, next);
  }

  async current(projectId: string, outlineId: string): Promise<OutlineCurrent> {
    if (!id(projectId) || !id(outlineId)) throw new OutlineReadError("OUTLINE_INVALID_INPUT");
    const path = `/api/v1/projects/${projectId}/solution-outlines/${outlineId}`;
    const { data, etag: header } = await this.get(path, true) as { data: unknown; etag: string };
    const result = parseOutlineCurrent(data, projectId, outlineId);
    if (header !== result.etag) fail();
    return result;
  }

  private async get(path: string, requireEtag = false): Promise<unknown> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const fetcher = this.fetcher;
      const response = await fetcher(path, { method: "GET", credentials: "same-origin", cache: "no-store",
        redirect: "error", headers: { Accept: "application/json" }, signal: controller.signal });
      if (controller.signal.aborted
        || response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") fail();
      const payload: unknown = await response.json();
      if (!record(payload) || !id(payload.trace_id)) fail();
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const statuses: Readonly<Record<string, number>> = { AUTH_SESSION_EXPIRED: 401,
          LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404 };
        if (typeof code === "string" && statuses[code] === response.status) {
          throw new OutlineReadError(code as OutlineReadErrorCode);
        }
        fail();
      }
      if (!exact(payload, ["data", "trace_id"])) fail();
      if (!requireEtag) return payload.data;
      const header = response.headers.get("etag");
      if (header === null || !etag.test(header)) fail();
      return { data: payload.data, etag: header };
    } catch (error) {
      if (error instanceof OutlineReadError) throw error;
      return fail();
    } finally { clearTimeout(timer); }
  }
}
