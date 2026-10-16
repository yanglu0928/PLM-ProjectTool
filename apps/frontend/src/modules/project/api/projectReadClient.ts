/** Read-only Project transport; the server remains the sole authorization source. */
export interface ProjectView {
  readonly project_id: string;
  readonly code: string;
  readonly name: string;
  readonly state: "ACTIVE" | "ARCHIVED";
  readonly created_at: string;
  readonly etag: string;
}

export interface ProjectPage {
  readonly items: readonly ProjectView[];
  readonly next_cursor: null;
  readonly has_more: false;
}

const messages = {
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许查看项目。",
  RESOURCE_NOT_FOUND: "项目不存在或无权查看。",
  PROJECT_INVALID_ID: "项目标识无效。",
  PROJECT_CLIENT_UNAVAILABLE: "暂时无法读取项目，请稍后重试。",
} as const;
export type ProjectReadErrorCode = keyof typeof messages;

export class ProjectReadError extends Error {
  constructor(readonly code: ProjectReadErrorCode) {
    super(messages[code]);
    this.name = "ProjectReadError";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const etag = /^"v(0|[1-9][0-9]*)"$/;
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
export function parseProject(value: unknown): ProjectView {
  if (!record(value) || !identifier(value.project_id) || typeof value.code !== "string" || !value.code.trim()
    || typeof value.name !== "string" || !value.name.trim()
    || (value.state !== "ACTIVE" && value.state !== "ARCHIVED")
    || !instant(value.created_at) || typeof value.etag !== "string" || !etag.test(value.etag)) {
    throw new ProjectReadError("PROJECT_CLIENT_UNAVAILABLE");
  }
  return Object.freeze({ project_id: value.project_id, code: value.code, name: value.name,
    state: value.state, created_at: value.created_at, etag: value.etag });
}

export class ProjectReadClient {
  constructor(private readonly fetcher: typeof fetch = fetch, private readonly timeoutMs = 10_000) {
    if (!Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 30_000) {
      throw new ProjectReadError("PROJECT_CLIENT_UNAVAILABLE");
    }
  }

  async #get(path: string): Promise<{ data: unknown; etag: string | null }> {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      // Invoke native fetch without binding its receiver to this client.
      const fetcher = this.fetcher;
      const response = await fetcher(path, { method: "GET", credentials: "same-origin", cache: "no-store",
        redirect: "error", headers: { Accept: "application/json" }, signal: controller.signal });
      if (controller.signal.aborted || response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
        throw new ProjectReadError("PROJECT_CLIENT_UNAVAILABLE");
      }
      const payload: unknown = await response.json();
      if (controller.signal.aborted || !record(payload) || !identifier(payload.trace_id)) {
        throw new ProjectReadError("PROJECT_CLIENT_UNAVAILABLE");
      }
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const expected: Record<string, number> = { AUTH_SESSION_EXPIRED: 401,
          LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404 };
        if (typeof code === "string" && Object.hasOwn(expected, code) && response.status === expected[code]) {
          throw new ProjectReadError(code as ProjectReadErrorCode);
        }
        throw new ProjectReadError("PROJECT_CLIENT_UNAVAILABLE");
      }
      return { data: payload.data, etag: response.headers.get("etag") };
    } catch (error) {
      if (error instanceof ProjectReadError) throw error;
      throw new ProjectReadError("PROJECT_CLIENT_UNAVAILABLE");
    } finally { window.clearTimeout(timer); }
  }

  async list(): Promise<ProjectPage> {
    const { data } = await this.#get("/api/v1/projects");
    if (!record(data) || !Array.isArray(data.items) || data.items.length > 1
      || data.next_cursor !== null || data.has_more !== false) {
      throw new ProjectReadError("PROJECT_CLIENT_UNAVAILABLE");
    }
    return Object.freeze({ items: Object.freeze(data.items.map(parseProject)), next_cursor: null, has_more: false });
  }

  async get(projectId: string): Promise<ProjectView> {
    if (!identifier(projectId)) throw new ProjectReadError("PROJECT_INVALID_ID");
    const { data, etag: header } = await this.#get(`/api/v1/projects/${projectId}`);
    const project = parseProject(data);
    if (project.project_id !== projectId || header !== project.etag) {
      throw new ProjectReadError("PROJECT_CLIENT_UNAVAILABLE");
    }
    return project;
  }
}
