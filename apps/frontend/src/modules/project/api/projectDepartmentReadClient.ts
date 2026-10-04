/** Read-only Department history, including inactive entries. Server authorization is authoritative. */
export interface ProjectDepartmentView {
  readonly department_id: string;
  readonly code: string;
  readonly name: string;
  readonly state: "ACTIVE" | "INACTIVE";
  readonly created_at: string;
  readonly etag: string;
}

export interface ProjectDepartmentPage {
  readonly items: readonly ProjectDepartmentView[];
  readonly next_cursor: string | null;
  readonly has_more: boolean;
}

const messages = {
  PROJECT_DEPARTMENT_INVALID_PROJECT: "项目标识无效。",
  PROJECT_DEPARTMENT_INVALID_CURSOR: "部门列表翻页位置已失效，请从第一页重新读取。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许查看项目部门。",
  RESOURCE_NOT_FOUND: "项目不存在或无权查看部门。",
  PROJECT_DEPARTMENT_CLIENT_UNAVAILABLE: "暂时无法读取项目部门，请稍后重试。",
} as const;
export type ProjectDepartmentReadErrorCode = keyof typeof messages;
export class ProjectDepartmentReadError extends Error {
  constructor(readonly code: ProjectDepartmentReadErrorCode) {
    super(messages[code]); this.name = "ProjectDepartmentReadError";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const cursorToken = /^[A-Za-z0-9_-]{1,512}\.[A-Za-z0-9_-]{43}$/;
const strongEtag = /^"v(0|[1-9][0-9]*)"$/;
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function identifier(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value)
    && value !== "00000000-0000-0000-0000-000000000000";
}
function label(value: unknown, max: number): value is string {
  return typeof value === "string" && value.length > 0 && value.length <= max
    && value.trim().length > 0 && !/\p{C}/u.test(value);
}
function instant(value: unknown): value is string {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/.test(value)) return false;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) && new Date(parsed).toISOString().slice(0, 19) === value.slice(0, 19);
}
export function parseProjectDepartment(value: unknown): ProjectDepartmentView {
  if (!record(value) || !identifier(value.department_id) || !label(value.code, 64)
    || !label(value.name, 255) || (value.state !== "ACTIVE" && value.state !== "INACTIVE")
    || !instant(value.created_at) || typeof value.etag !== "string"
    || !strongEtag.test(value.etag) || !Number.isSafeInteger(Number(value.etag.slice(2, -1)))) {
    throw new ProjectDepartmentReadError("PROJECT_DEPARTMENT_CLIENT_UNAVAILABLE");
  }
  return Object.freeze({ department_id: value.department_id, code: value.code,
    name: value.name, state: value.state, created_at: value.created_at, etag: value.etag });
}

export class ProjectDepartmentReadClient {
  constructor(private readonly fetcher: typeof fetch = fetch, private readonly timeoutMs = 10_000) {
    if (!Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 30_000) {
      throw new ProjectDepartmentReadError("PROJECT_DEPARTMENT_CLIENT_UNAVAILABLE");
    }
  }

  async list(projectId: string, cursor: string | null = null): Promise<ProjectDepartmentPage> {
    if (!identifier(projectId)) throw new ProjectDepartmentReadError("PROJECT_DEPARTMENT_INVALID_PROJECT");
    if (cursor !== null && (typeof cursor !== "string" || !cursorToken.test(cursor))) {
      throw new ProjectDepartmentReadError("PROJECT_DEPARTMENT_INVALID_CURSOR");
    }
    const query = new URLSearchParams({ page_size: "50" });
    if (cursor !== null) query.set("cursor", cursor);
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const fetcher = this.fetcher;
      const response = await fetcher(`/api/v1/projects/${projectId}/departments?${query}`, {
        method: "GET", credentials: "same-origin", cache: "no-store", redirect: "error",
        headers: { Accept: "application/json" }, signal: controller.signal,
      });
      if (controller.signal.aborted || response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
        throw new ProjectDepartmentReadError("PROJECT_DEPARTMENT_CLIENT_UNAVAILABLE");
      }
      const payload: unknown = await response.json();
      if (controller.signal.aborted || !record(payload) || !identifier(payload.trace_id)) {
        throw new ProjectDepartmentReadError("PROJECT_DEPARTMENT_CLIENT_UNAVAILABLE");
      }
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const expected: Record<string, number> = { AUTH_SESSION_EXPIRED: 401,
          LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404 };
        if (typeof code === "string" && Object.hasOwn(expected, code) && response.status === expected[code]) {
          throw new ProjectDepartmentReadError(code as ProjectDepartmentReadErrorCode);
        }
        throw new ProjectDepartmentReadError("PROJECT_DEPARTMENT_CLIENT_UNAVAILABLE");
      }
      const data = payload.data;
      if (!record(data) || !Array.isArray(data.items) || data.items.length > 50
        || typeof data.has_more !== "boolean"
        || (data.has_more && (data.items.length === 0 || typeof data.next_cursor !== "string"
          || !cursorToken.test(data.next_cursor) || data.next_cursor === cursor))
        || (!data.has_more && data.next_cursor !== null)) {
        throw new ProjectDepartmentReadError("PROJECT_DEPARTMENT_CLIENT_UNAVAILABLE");
      }
      const items = data.items.map(parseProjectDepartment);
      if (new Set(items.map((item) => item.department_id)).size !== items.length) {
        throw new ProjectDepartmentReadError("PROJECT_DEPARTMENT_CLIENT_UNAVAILABLE");
      }
      return Object.freeze({ items: Object.freeze(items),
        next_cursor: data.has_more ? data.next_cursor as string : null, has_more: data.has_more });
    } catch (failure) {
      if (failure instanceof ProjectDepartmentReadError) throw failure;
      throw new ProjectDepartmentReadError("PROJECT_DEPARTMENT_CLIENT_UNAVAILABLE");
    } finally { window.clearTimeout(timer); }
  }
}
