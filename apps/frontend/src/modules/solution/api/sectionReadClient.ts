/** Section identity reads do not prove approved solution content or customer acceptance. */
export interface SectionSummary {
  readonly solution_section_id: string; readonly solution_outline_id: string;
  readonly project_id: string; readonly section_key: string;
  readonly section_state: "ACTIVE" | "ARCHIVED";
  readonly current_approved_version_ref: string | null;
  readonly created_at: string; readonly etag: string;
}
export interface SectionCurrent extends SectionSummary { readonly created_by: string }
export interface SectionPage {
  readonly items: readonly SectionSummary[]; readonly next_cursor: string | null;
  readonly has_more: boolean;
}

const messages = {
  SECTION_INVALID_INPUT: "项目、方案章节或翻页参数无效。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许读取方案章节。",
  RESOURCE_NOT_FOUND: "方案章节不存在或无权查看。",
  SECTION_UNAVAILABLE: "暂时无法读取方案章节，请稍后重试。",
} as const;
export type SectionReadErrorCode = keyof typeof messages;
export class SectionReadError extends Error {
  constructor(readonly code: SectionReadErrorCode) {
    super(messages[code]); this.name = "SectionReadError";
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
function key(value: unknown): value is string {
  return typeof value === "string" && value.length >= 1 && value.length <= 128
    && value.trim() === value && !/\p{C}/u.test(value);
}
function fail(): never { throw new SectionReadError("SECTION_UNAVAILABLE"); }
const summaryFields = ["solution_section_id", "solution_outline_id", "project_id", "section_key",
  "section_state", "current_approved_version_ref", "created_at", "etag"] as const;
const detailFields = [...summaryFields, "created_by"] as const;

function summary(value: unknown, projectId: string, sectionId?: string,
                 detail = false): SectionSummary {
  if (!record(value) || !exact(value, detail ? detailFields : summaryFields)
    || !id(value.solution_section_id)
    || sectionId !== undefined && value.solution_section_id !== sectionId
    || !id(value.solution_outline_id) || value.project_id !== projectId
    || !key(value.section_key) || !["ACTIVE", "ARCHIVED"].includes(value.section_state as string)
    || value.current_approved_version_ref !== null && !id(value.current_approved_version_ref)
    || !instant(value.created_at) || typeof value.etag !== "string" || !etag.test(value.etag)) fail();
  return Object.freeze({
    solution_section_id: value.solution_section_id as string,
    solution_outline_id: value.solution_outline_id as string,
    project_id: projectId, section_key: value.section_key as string,
    section_state: value.section_state as SectionSummary["section_state"],
    current_approved_version_ref: value.current_approved_version_ref as string | null,
    created_at: value.created_at as string, etag: value.etag as string,
  });
}

export function parseSectionCurrent(value: unknown, projectId: string,
                                    sectionId: string): SectionCurrent {
  const base = summary(value, projectId, sectionId, true);
  if (!record(value) || !id(value.created_by)) fail();
  return Object.freeze({ ...base, created_by: value.created_by });
}

export function parseSectionPage(value: unknown, projectId: string, pageSize: number,
                                 previousCursor: string | null = null): SectionPage {
  if (!record(value) || !exact(value, ["items", "next_cursor", "has_more"])
    || !Array.isArray(value.items) || value.items.length > pageSize
    || typeof value.has_more !== "boolean"
    || value.has_more && (value.items.length === 0 || typeof value.next_cursor !== "string"
      || !cursor.test(value.next_cursor) || value.next_cursor === previousCursor)
    || !value.has_more && value.next_cursor !== null) fail();
  const items = value.items.map(item => summary(item, projectId));
  if (items.some((item, index) => index > 0
    && items[index - 1]!.solution_section_id >= item.solution_section_id)) fail();
  return Object.freeze({ items: Object.freeze(items), next_cursor: value.next_cursor as string | null,
    has_more: value.has_more });
}

export class SectionReadClient {
  constructor(private readonly fetcher: typeof fetch = fetch,
              private readonly timeoutMs = 10_000) {}

  async list(projectId: string, pageSize = 50, next: string | null = null): Promise<SectionPage> {
    if (!id(projectId) || !Number.isSafeInteger(pageSize) || pageSize < 1 || pageSize > 100
      || next !== null && !cursor.test(next)) throw new SectionReadError("SECTION_INVALID_INPUT");
    const params = new URLSearchParams({ page_size: String(pageSize) });
    if (next !== null) params.set("cursor", next);
    return parseSectionPage(await this.get(`/api/v1/projects/${projectId}/solution-sections?${params}`),
      projectId, pageSize, next);
  }

  async current(projectId: string, sectionId: string): Promise<SectionCurrent> {
    if (!id(projectId) || !id(sectionId)) throw new SectionReadError("SECTION_INVALID_INPUT");
    const { data, etag: header } = await this.get(
      `/api/v1/projects/${projectId}/solution-sections/${sectionId}`, true) as { data: unknown; etag: string };
    const result = parseSectionCurrent(data, projectId, sectionId);
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
        || response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json"
        || response.headers.get("cache-control") !== "no-store") fail();
      const payload: unknown = await response.json();
      if (!record(payload) || !id(payload.trace_id)
        || response.headers.get("x-trace-id") !== payload.trace_id) fail();
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const statuses: Readonly<Record<string, number>> = { AUTH_SESSION_EXPIRED: 401,
          LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404 };
        if (typeof code === "string" && statuses[code] === response.status) {
          throw new SectionReadError(code as SectionReadErrorCode);
        }
        fail();
      }
      if (!exact(payload, ["data", "trace_id"])) fail();
      if (!requireEtag) return payload.data;
      const header = response.headers.get("etag");
      if (header === null || !etag.test(header)) fail();
      return { data: payload.data, etag: header };
    } catch (error) {
      if (error instanceof SectionReadError) throw error;
      return fail();
    } finally { clearTimeout(timer); }
  }
}
