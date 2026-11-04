/** Strict same-origin read client for fixed OutputRequest history pages. */
export type OutputType = "DOCX" | "PPTX" | "PNG" | "JPEG";
export type OutputRequestState =
  | "REQUESTED" | "QUEUED" | "GENERATING" | "VALIDATING"
  | "SUCCEEDED" | "FAILED" | "CANCEL_REQUESTED" | "CANCELLED";

export interface OutputRequestSummary {
  readonly output_request_id: string;
  readonly project_id: string;
  readonly output_type: OutputType;
  readonly state: OutputRequestState;
  readonly requested_at: string;
  readonly completed_at: string | null;
}
export interface OutputRequestPage {
  readonly items: readonly OutputRequestSummary[];
  readonly next_cursor: string | null;
  readonly has_more: boolean;
}

const messages = {
  OUTPUT_INVALID_INPUT: "项目或翻页参数无效。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许查看输出请求。",
  RESOURCE_NOT_FOUND: "输出请求不存在或无权查看。",
  OUTPUT_UNAVAILABLE: "暂时无法读取输出请求，请稍后重试。",
} as const;
export type OutputRequestListErrorCode = keyof typeof messages;
export class OutputRequestListError extends Error {
  constructor(readonly code: OutputRequestListErrorCode) {
    super(messages[code]);
    this.name = "OutputRequestListError";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const cursor = /^[A-Za-z0-9_-]{1,1200}\.[A-Za-z0-9_-]{43}$/;
const fingerprint = /^[0-9a-f]{64}$/;
const etag = /^"v(0|[1-9][0-9]*)"$/;
const stamp = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/;
const fields = [
  "output_request_id", "project_id", "output_type", "template_version_ref",
  "source_version_refs", "output_policy_ref", "plugin_operation",
  "context_snapshot_ref", "context_fingerprint", "state", "job_ref",
  "execution_ref", "generation_no", "requested_at", "completed_at", "etag",
] as const;

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
function instant(value: unknown): value is string {
  if (typeof value !== "string" || !stamp.test(value)) return false;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed)
    && new Date(parsed).toISOString().slice(0, 19) === value.slice(0, 19);
}
function orderKey(value: string): string {
  const fraction = value.length > 20 ? value.slice(20, -1).padEnd(6, "0") : "000000";
  return value.slice(0, 19) + fraction;
}
export function outputRequestFollows(previous: OutputRequestSummary,
                                     next: OutputRequestSummary): boolean {
  const before = orderKey(previous.requested_at);
  const after = orderKey(next.requested_at);
  return before > after || before === after
    && previous.output_request_id > next.output_request_id;
}
function fail(): never { throw new OutputRequestListError("OUTPUT_UNAVAILABLE"); }

function parseItem(value: unknown, projectId: string): OutputRequestSummary {
  if (!record(value) || !exact(value, fields)
    || !id(value.output_request_id) || value.project_id !== projectId
    || !["DOCX", "PPTX", "PNG", "JPEG"].includes(value.output_type as string)
    || !id(value.template_version_ref) || !Array.isArray(value.source_version_refs)
    || value.source_version_refs.length < 1 || value.source_version_refs.length > 100
    || !value.source_version_refs.every(id)
    || new Set(value.source_version_refs).size !== value.source_version_refs.length
    || typeof value.output_policy_ref !== "string" || !value.output_policy_ref
    || typeof value.plugin_operation !== "string" || !value.plugin_operation
    || !id(value.context_snapshot_ref)
    || typeof value.context_fingerprint !== "string" || !fingerprint.test(value.context_fingerprint)
    || !["REQUESTED", "QUEUED", "GENERATING", "VALIDATING", "SUCCEEDED", "FAILED",
      "CANCEL_REQUESTED", "CANCELLED"].includes(value.state as string)
    || value.job_ref !== null && !id(value.job_ref)
    || value.execution_ref !== null && !id(value.execution_ref)
    || !Number.isSafeInteger(value.generation_no) || (value.generation_no as number) < 1
    || !instant(value.requested_at)
    || value.completed_at !== null && !instant(value.completed_at)
    || typeof value.etag !== "string" || !etag.test(value.etag)) fail();
  return Object.freeze({
    output_request_id: value.output_request_id,
    project_id: projectId,
    output_type: value.output_type as OutputType,
    state: value.state as OutputRequestState,
    requested_at: value.requested_at,
    completed_at: value.completed_at as string | null,
  });
}

export function parseOutputRequestPage(value: unknown, projectId: string, pageSize: number,
                                       previousCursor: string | null = null): OutputRequestPage {
  if (!record(value) || !exact(value, ["items", "next_cursor", "has_more"])
    || !Array.isArray(value.items) || value.items.length > pageSize
    || typeof value.has_more !== "boolean"
    || value.has_more && (value.items.length === 0
      || typeof value.next_cursor !== "string" || !cursor.test(value.next_cursor)
      || value.next_cursor === previousCursor)
    || !value.has_more && value.next_cursor !== null) fail();
  const items = value.items.map(item => parseItem(item, projectId));
  if (items.some((item, index) => index > 0
    && !outputRequestFollows(items[index - 1]!, item))) fail();
  return Object.freeze({
    items: Object.freeze(items),
    next_cursor: value.next_cursor as string | null,
    has_more: value.has_more,
  });
}

export class OutputRequestListClient {
  constructor(private readonly fetcher: typeof fetch = fetch,
              private readonly timeoutMs = 10_000) {
    if (!Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 30_000) {
      throw new OutputRequestListError("OUTPUT_UNAVAILABLE");
    }
  }

  async list(projectId: string, pageSize = 50, next: string | null = null): Promise<OutputRequestPage> {
    if (!id(projectId) || !Number.isSafeInteger(pageSize) || pageSize < 1 || pageSize > 200
      || next !== null && !cursor.test(next)) {
      throw new OutputRequestListError("OUTPUT_INVALID_INPUT");
    }
    const params = new URLSearchParams({ page_size: String(pageSize) });
    if (next !== null) params.set("cursor", next);
    return parseOutputRequestPage(
      await this.get("/api/v1/projects/" + projectId + "/output-requests?" + params.toString()),
      projectId, pageSize, next,
    );
  }

  private async get(path: string): Promise<unknown> {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const fetcher = this.fetcher;
      const response = await fetcher(path, {
        method: "GET", credentials: "same-origin", cache: "no-store", redirect: "error",
        headers: { Accept: "application/json" }, signal: controller.signal,
      });
      if (controller.signal.aborted
        || response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") fail();
      const payload: unknown = await response.json();
      if (controller.signal.aborted || !record(payload) || typeof payload.trace_id !== "string"
        || !uuid.test(payload.trace_id)) fail();
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const expected: Readonly<Record<string, number>> = {
          AUTH_SESSION_EXPIRED: 401, LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404,
        };
        if (typeof code === "string" && expected[code] === response.status) {
          throw new OutputRequestListError(code as OutputRequestListErrorCode);
        }
        fail();
      }
      if (!exact(payload, ["data", "trace_id"])) fail();
      return payload.data;
    } catch (error) {
      if (error instanceof OutputRequestListError) throw error;
      return fail();
    } finally {
      window.clearTimeout(timer);
    }
  }
}
