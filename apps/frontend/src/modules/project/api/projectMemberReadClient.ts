/** Read-only ProjectMember history; server-side authorization remains authoritative. */
export interface ProjectMemberView {
  readonly member_id: string;
  readonly user: Readonly<{ user_id: string; display_name: string }>;
  readonly role: "PROJECT_MANAGER" | "IMPLEMENTATION_MEMBER" | "CUSTOMER_MANAGER" | "CUSTOMER_MEMBER";
  readonly department: Readonly<{ department_id: string; name: string }>;
  readonly state: "ACTIVE" | "SUSPENDED" | "REMOVED";
  readonly effective_at: string;
  readonly ended_at: string | null;
  readonly etag: string;
}

export interface ProjectMemberPage {
  readonly items: readonly ProjectMemberView[];
  readonly next_cursor: string | null;
  readonly has_more: boolean;
}

const messages = {
  PROJECT_MEMBER_INVALID_PROJECT: "项目标识无效。",
  PROJECT_MEMBER_INVALID_CURSOR: "成员列表翻页位置已失效，请从第一页重新读取。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许查看项目成员。",
  RESOURCE_NOT_FOUND: "项目不存在或无权查看成员。",
  PROJECT_MEMBER_CLIENT_UNAVAILABLE: "暂时无法读取项目成员，请稍后重试。",
} as const;
export type ProjectMemberReadErrorCode = keyof typeof messages;

export class ProjectMemberReadError extends Error {
  constructor(readonly code: ProjectMemberReadErrorCode) {
    super(messages[code]);
    this.name = "ProjectMemberReadError";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const cursorToken = /^[A-Za-z0-9_-]{1,512}\.[A-Za-z0-9_-]{43}$/;
const strongEtag = /^"v(0|[1-9][0-9]*)"$/;
const roles = new Set(["PROJECT_MANAGER", "IMPLEMENTATION_MEMBER", "CUSTOMER_MANAGER", "CUSTOMER_MEMBER"]);
const states = new Set(["ACTIVE", "SUSPENDED", "REMOVED"]);
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
export function parseProjectMember(value: unknown): ProjectMemberView {
  if (!record(value) || !identifier(value.member_id) || !record(value.user)
    || !identifier(value.user.user_id) || typeof value.user.display_name !== "string"
    || !value.user.display_name.trim() || !roles.has(value.role as string)
    || !record(value.department) || !identifier(value.department.department_id)
    || typeof value.department.name !== "string" || !value.department.name.trim()
    || !states.has(value.state as string) || !instant(value.effective_at)
    || (value.ended_at !== null && !instant(value.ended_at))
    || (value.state === "REMOVED") !== (value.ended_at !== null)
    || typeof value.etag !== "string" || !strongEtag.test(value.etag)) {
    throw new ProjectMemberReadError("PROJECT_MEMBER_CLIENT_UNAVAILABLE");
  }
  return Object.freeze({ member_id: value.member_id,
    user: Object.freeze({ user_id: value.user.user_id, display_name: value.user.display_name }),
    role: value.role as ProjectMemberView["role"],
    department: Object.freeze({ department_id: value.department.department_id, name: value.department.name }),
    state: value.state as ProjectMemberView["state"], effective_at: value.effective_at,
    ended_at: value.ended_at, etag: value.etag });
}

export class ProjectMemberReadClient {
  constructor(private readonly fetcher: typeof fetch = fetch, private readonly timeoutMs = 10_000) {
    if (!Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 30_000) {
      throw new ProjectMemberReadError("PROJECT_MEMBER_CLIENT_UNAVAILABLE");
    }
  }

  async list(projectId: string, cursor: string | null = null): Promise<ProjectMemberPage> {
    if (!identifier(projectId)) throw new ProjectMemberReadError("PROJECT_MEMBER_INVALID_PROJECT");
    if (cursor !== null && (typeof cursor !== "string" || !cursorToken.test(cursor))) {
      throw new ProjectMemberReadError("PROJECT_MEMBER_INVALID_CURSOR");
    }
    const query = new URLSearchParams({ page_size: "50" });
    if (cursor !== null) query.set("cursor", cursor);
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const fetcher = this.fetcher;
      const response = await fetcher(`/api/v1/projects/${projectId}/members?${query}`, {
        method: "GET", credentials: "same-origin", cache: "no-store", redirect: "error",
        headers: { Accept: "application/json" }, signal: controller.signal,
      });
      if (controller.signal.aborted || response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
        throw new ProjectMemberReadError("PROJECT_MEMBER_CLIENT_UNAVAILABLE");
      }
      const payload: unknown = await response.json();
      if (controller.signal.aborted || !record(payload) || !identifier(payload.trace_id)) {
        throw new ProjectMemberReadError("PROJECT_MEMBER_CLIENT_UNAVAILABLE");
      }
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const expected: Record<string, number> = { AUTH_SESSION_EXPIRED: 401,
          LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404 };
        if (typeof code === "string" && Object.hasOwn(expected, code) && response.status === expected[code]) {
          throw new ProjectMemberReadError(code as ProjectMemberReadErrorCode);
        }
        throw new ProjectMemberReadError("PROJECT_MEMBER_CLIENT_UNAVAILABLE");
      }
      const data = payload.data;
      if (!record(data) || !Array.isArray(data.items) || data.items.length > 50
        || typeof data.has_more !== "boolean"
        || (data.has_more && (data.items.length === 0 || typeof data.next_cursor !== "string"
          || !cursorToken.test(data.next_cursor) || data.next_cursor === cursor))
        || (!data.has_more && data.next_cursor !== null)) {
        throw new ProjectMemberReadError("PROJECT_MEMBER_CLIENT_UNAVAILABLE");
      }
      const items = data.items.map(parseProjectMember);
      if (new Set(items.map((item) => item.member_id)).size !== items.length) {
        throw new ProjectMemberReadError("PROJECT_MEMBER_CLIENT_UNAVAILABLE");
      }
      return Object.freeze({ items: Object.freeze(items),
        next_cursor: data.has_more ? data.next_cursor as string : null, has_more: data.has_more });
    } catch (error) {
      if (error instanceof ProjectMemberReadError) throw error;
      throw new ProjectMemberReadError("PROJECT_MEMBER_CLIENT_UNAVAILABLE");
    } finally { window.clearTimeout(timer); }
  }
}
