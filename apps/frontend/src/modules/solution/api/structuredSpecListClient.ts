/** SOL_SPEC_LIST fixed history summaries; use SOL_SPEC_GET for full content. */
import type { SpecType } from "./structuredSpecCreateClient";

export interface StructuredSpecSummary {
  readonly structured_solution_spec_id: string;
  readonly spec_series_id: string;
  readonly project_id: string;
  readonly spec_type: SpecType;
  readonly version_no: number;
  readonly version_state: "DRAFT" | "IN_REVIEW" | "APPROVED" | "RETURNED" | "SUPERSEDED" | "RESTRICTED";
  readonly content_fingerprint: string;
  readonly payload_fingerprint: string;
  readonly supersedes_version_ref: string | null;
  readonly review_ref: string | null;
  readonly review_round_ref: string | null;
  readonly created_by: string;
  readonly created_at: string;
}

export interface StructuredSpecPage {
  readonly items: readonly StructuredSpecSummary[];
  readonly next_cursor: string | null;
  readonly has_more: boolean;
}

const messages = {
  STRUCTURED_SPEC_LIST_INVALID: "项目或翻页参数无效。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许读取专项历史。",
  RESOURCE_NOT_FOUND: "项目不存在或无权查看专项历史。",
  STRUCTURED_SPEC_LIST_UNAVAILABLE: "暂时无法读取专项历史，请稍后重试。",
} as const;
export type StructuredSpecListErrorCode = keyof typeof messages;
export class StructuredSpecListError extends Error {
  constructor(readonly code: StructuredSpecListErrorCode) {
    super(messages[code]); this.name = "StructuredSpecListError";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const digest = /^[0-9a-f]{64}$/;
const cursor = /^[A-Za-z0-9_-]{1,4096}\.[A-Za-z0-9_-]{43}$/;
const stamp = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/;
const types = ["PROCESS_MODEL", "INTERFACE_SPEC", "MIGRATION_SPEC", "PERMISSION_DESIGN"];
const states = ["DRAFT", "IN_REVIEW", "APPROVED", "RETURNED", "SUPERSEDED", "RESTRICTED"];
const fields = ["structured_solution_spec_id", "spec_series_id", "project_id", "spec_type",
  "version_no", "version_state", "content_fingerprint", "payload_fingerprint",
  "supersedes_version_ref", "review_ref", "review_round_ref", "created_by", "created_at"] as const;

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function exact(value: Record<string, unknown>, keys: readonly string[]): boolean {
  return Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
}
function id(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value)
    && value !== "00000000-0000-0000-0000-000000000000";
}
function optionalId(value: unknown): value is string | null { return value === null || id(value); }
function instant(value: unknown): value is string {
  return typeof value === "string" && stamp.test(value) && Number.isFinite(Date.parse(value));
}
function fail(): never { throw new StructuredSpecListError("STRUCTURED_SPEC_LIST_UNAVAILABLE"); }

function parseSummary(value: unknown, project: string): StructuredSpecSummary {
  if (!record(value) || !exact(value, fields)
    || !id(value.structured_solution_spec_id) || !id(value.spec_series_id)
    || value.project_id !== project || !types.includes(value.spec_type as string)
    || typeof value.version_no !== "number" || !Number.isSafeInteger(value.version_no)
    || value.version_no < 1 || !states.includes(value.version_state as string)
    || typeof value.content_fingerprint !== "string" || !digest.test(value.content_fingerprint)
    || typeof value.payload_fingerprint !== "string" || !digest.test(value.payload_fingerprint)
    || !optionalId(value.supersedes_version_ref)
    || (value.supersedes_version_ref === null) !== (value.version_no === 1)
    || !optionalId(value.review_ref) || !optionalId(value.review_round_ref)
    || (value.review_ref === null) !== (value.review_round_ref === null)
    || !id(value.created_by) || !instant(value.created_at)) fail();
  return Object.freeze({ ...value }) as unknown as StructuredSpecSummary;
}

export function parseStructuredSpecPage(value: unknown, project: string, pageSize: number,
                                        previousCursor: string | null): StructuredSpecPage {
  if (!record(value) || !exact(value, ["items", "next_cursor", "has_more"])
    || !Array.isArray(value.items) || value.items.length > pageSize
    || typeof value.has_more !== "boolean"
    || value.has_more && (value.items.length === 0 || typeof value.next_cursor !== "string"
      || !cursor.test(value.next_cursor) || value.next_cursor === previousCursor)
    || !value.has_more && value.next_cursor !== null) fail();
  const items = value.items.map(item => parseSummary(item, project));
  if (items.some((item, index) => index > 0
    && items[index - 1]!.structured_solution_spec_id <= item.structured_solution_spec_id)) fail();
  return Object.freeze({ items: Object.freeze(items),
    next_cursor: value.next_cursor as string | null, has_more: value.has_more });
}

export class StructuredSpecListClient {
  constructor(private readonly fetcher: typeof fetch = (input, init) => fetch(input, init),
              private readonly timeoutMs = 10_000) {}

  async list(project: string, pageSize = 50,
             next: string | null = null): Promise<StructuredSpecPage> {
    if (!id(project) || !Number.isSafeInteger(pageSize) || pageSize < 1 || pageSize > 100
      || next !== null && !cursor.test(next)) {
      throw new StructuredSpecListError("STRUCTURED_SPEC_LIST_INVALID");
    }
    const params = new URLSearchParams({ page_size: String(pageSize) });
    if (next !== null) params.set("cursor", next);
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const response = await this.fetcher(
        `/api/v1/projects/${project}/structured-solution-specs?${params}`,
        { method: "GET", credentials: "same-origin", cache: "no-store", redirect: "error",
          headers: { Accept: "application/json" }, signal: controller.signal });
      if (controller.signal.aborted
        || response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json"
        || response.headers.get("cache-control") !== "no-store") fail();
      const body: unknown = await response.json();
      if (!record(body) || !id(body.trace_id)
        || response.headers.get("x-trace-id") !== body.trace_id) fail();
      if (response.status !== 200) {
        const code = record(body.error) ? body.error.code : null;
        const statuses: Readonly<Record<string, number>> = {
          AUTH_SESSION_EXPIRED: 401, LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404,
        };
        if (typeof code === "string" && statuses[code] === response.status) {
          throw new StructuredSpecListError(code as StructuredSpecListErrorCode);
        }
        fail();
      }
      if (!exact(body, ["data", "trace_id"]) || response.headers.has("etag")) fail();
      return parseStructuredSpecPage(body.data, project, pageSize, next);
    } catch (error) {
      if (error instanceof StructuredSpecListError) throw error;
      return fail();
    } finally { clearTimeout(timer); }
  }
}
