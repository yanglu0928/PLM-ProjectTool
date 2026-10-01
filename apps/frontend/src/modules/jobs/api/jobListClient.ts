/** Read-only Job list transport. Authorization and cursor integrity remain server-owned. */
export interface JobListItem {
  readonly job_id: string;
  readonly job_type: string;
  readonly owner_module: string;
  readonly scope: "PROJECT" | "GLOBAL" | "DEPLOYMENT";
  readonly project_id: string | null;
  readonly state: "PENDING" | "RUNNING" | "RETRY_WAIT" | "SUCCEEDED" | "FAILED" | "CANCEL_REQUESTED" | "CANCELLED";
  readonly attempt_count: number;
  readonly retryable: boolean;
  readonly result_ref: Readonly<{ type: "AUDIT_EXPORT" | "DOCUMENT_PARSE"; id: string }> | null;
  readonly created_at: string;
  readonly completed_at: string | null;
  readonly etag: string;
}

export interface JobListPage {
  readonly items: readonly JobListItem[];
  readonly next_cursor: string | null;
  readonly has_more: boolean;
}

const messages = {
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许查看任务。",
  RESOURCE_NOT_FOUND: "项目不存在或无权查看。",
  JOB_LIST_INVALID_INPUT: "任务列表参数无效。",
  JOB_LIST_UNAVAILABLE: "暂时无法读取任务列表，请稍后重试。",
} as const;
export type JobListErrorCode = keyof typeof messages;
export class JobListError extends Error {
  constructor(readonly code: JobListErrorCode) { super(messages[code]); this.name = "JobListError"; }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const cursorPattern = /^j1\.[A-Za-z0-9_-]{1,1536}$/;
const namePattern = /^[A-Za-z0-9_]{1,64}$/;
const versionPattern = /^"v(0|[1-9][0-9]*)"$/;
const states = new Set(["PENDING", "RUNNING", "RETRY_WAIT", "SUCCEEDED", "FAILED", "CANCEL_REQUESTED", "CANCELLED"]);
const scopes = new Set(["PROJECT", "GLOBAL", "DEPLOYMENT"]);
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function identifier(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value) && value !== "00000000-0000-0000-0000-000000000000";
}
function instant(value: unknown): value is string {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/.test(value)) return false;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) && new Date(parsed).toISOString().slice(0, 19) === value.slice(0, 19);
}
function parseItem(value: unknown, projectId: string | null, scope: string | null): JobListItem {
  if (!record(value) || !identifier(value.job_id) || typeof value.job_type !== "string" || !namePattern.test(value.job_type)
    || typeof value.owner_module !== "string" || !namePattern.test(value.owner_module)
    || typeof value.scope !== "string" || !scopes.has(value.scope)
    || (value.scope === "PROJECT") !== identifier(value.project_id)
    || (value.scope !== "PROJECT" && value.project_id !== null)
    || (projectId !== null && (value.scope !== "PROJECT" || value.project_id !== projectId))
    || (projectId === null && value.scope === "PROJECT") || (scope !== null && value.scope !== scope)
    || typeof value.state !== "string" || !states.has(value.state)
    || !Number.isInteger(value.attempt_count) || (value.attempt_count as number) < 0 || (value.attempt_count as number) > 2147483647
    || typeof value.retryable !== "boolean" || !instant(value.created_at)
    || (value.completed_at !== null && !instant(value.completed_at))
    || (["SUCCEEDED", "FAILED", "CANCELLED"].includes(value.state) !== (value.completed_at !== null))
    || (typeof value.completed_at === "string" && value.completed_at < (value.created_at as string))
    || typeof value.etag !== "string" || !versionPattern.test(value.etag)
    || value.progress !== null || value.checkpoint !== null || value.error_code !== null) {
    throw new JobListError("JOB_LIST_UNAVAILABLE");
  }
  let result: JobListItem["result_ref"] = null;
  if (value.result_ref !== null) {
    if (!record(value.result_ref) || !["AUDIT_EXPORT", "DOCUMENT_PARSE"].includes(String(value.result_ref.type))
      || !identifier(value.result_ref.id) || value.state !== "SUCCEEDED") throw new JobListError("JOB_LIST_UNAVAILABLE");
    result = Object.freeze({ type: value.result_ref.type as "AUDIT_EXPORT" | "DOCUMENT_PARSE", id: value.result_ref.id });
  }
  return Object.freeze({ job_id: value.job_id, job_type: value.job_type, owner_module: value.owner_module,
    scope: value.scope as JobListItem["scope"], project_id: value.project_id as string | null,
    state: value.state as JobListItem["state"], attempt_count: value.attempt_count as number,
    retryable: value.retryable, result_ref: result, created_at: value.created_at,
    completed_at: value.completed_at as string | null, etag: value.etag });
}

export class JobListClient {
  constructor(private readonly fetcher: typeof fetch = fetch, private readonly timeoutMs = 10_000) {
    if (!Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 30_000) throw new JobListError("JOB_LIST_INVALID_INPUT");
  }

  async listProject(projectId: string, pageSize = 50, cursor: string | null = null): Promise<JobListPage> {
    if (!identifier(projectId)) throw new JobListError("JOB_LIST_INVALID_INPUT");
    return this.#list(`/api/v1/projects/${projectId}/jobs`, projectId, null, pageSize, cursor);
  }

  async listAdmin(scope: "GLOBAL" | "DEPLOYMENT" | null = null, pageSize = 50, cursor: string | null = null): Promise<JobListPage> {
    if (scope !== null && scope !== "GLOBAL" && scope !== "DEPLOYMENT") throw new JobListError("JOB_LIST_INVALID_INPUT");
    return this.#list("/api/v1/admin/jobs", null, scope, pageSize, cursor);
  }

  async #list(path: string, projectId: string | null, scope: string | null, pageSize: number, cursor: string | null): Promise<JobListPage> {
    if (!Number.isInteger(pageSize) || pageSize < 1 || pageSize > 200 || (cursor !== null && !cursorPattern.test(cursor))) {
      throw new JobListError("JOB_LIST_INVALID_INPUT");
    }
    const params = new URLSearchParams({ page_size: String(pageSize) });
    if (scope !== null) params.set("scope", scope);
    if (cursor !== null) params.set("cursor", cursor);
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const fetcher = this.fetcher;
      const response = await fetcher(`${path}?${params}`, { method: "GET", credentials: "same-origin", cache: "no-store",
        redirect: "error", headers: { Accept: "application/json" }, signal: controller.signal });
      if (controller.signal.aborted || response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
        throw new JobListError("JOB_LIST_UNAVAILABLE");
      }
      const payload: unknown = await response.json();
      if (controller.signal.aborted || !record(payload) || !identifier(payload.trace_id)) throw new JobListError("JOB_LIST_UNAVAILABLE");
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const expected: Record<string, number> = { AUTH_SESSION_EXPIRED: 401, LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404 };
        if (typeof code === "string" && Object.hasOwn(expected, code) && response.status === expected[code]) {
          throw new JobListError(code as JobListErrorCode);
        }
        throw new JobListError("JOB_LIST_UNAVAILABLE");
      }
      const data = payload.data;
      if (!record(data) || !Array.isArray(data.items) || data.items.length > pageSize || typeof data.has_more !== "boolean"
        || (data.has_more && (typeof data.next_cursor !== "string" || !cursorPattern.test(data.next_cursor) || data.items.length === 0))
        || (!data.has_more && data.next_cursor !== null)) throw new JobListError("JOB_LIST_UNAVAILABLE");
      const items = Object.freeze(data.items.map((item: unknown) => parseItem(item, projectId, scope)));
      if (new Set(items.map(item => item.job_id)).size !== items.length) throw new JobListError("JOB_LIST_UNAVAILABLE");
      return Object.freeze({ items, next_cursor: data.next_cursor as string | null, has_more: data.has_more });
    } catch (error) {
      if (error instanceof JobListError) throw error;
      throw new JobListError("JOB_LIST_UNAVAILABLE");
    } finally { window.clearTimeout(timer); }
  }
}
