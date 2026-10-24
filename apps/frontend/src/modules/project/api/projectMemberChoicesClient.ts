import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";

export interface MemberCandidate { readonly user_id: string; readonly display_name: string }
export interface ActiveDepartment { readonly department_id: string; readonly code: string; readonly name: string }

const messages = {
  INVALID_INPUT: "请填写准确的用户名，并选择当前项目。",
  AUTH_RELOGIN_REQUIRED: "请重新登录后再选择成员。",
  AUTH_CLIENT_BUSY: "正在处理会话操作，请稍候。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许选择项目成员。",
  RESOURCE_NOT_FOUND: "项目不存在或当前账户无权选择成员。",
  PROJECT_ARCHIVED: "项目已归档，无法添加成员。",
  AUTH_RATE_LIMITED: "查询过于频繁，请稍后再试。",
  UNAVAILABLE: "暂时无法确认成员或部门，请稍后重试。",
} as const;
export type MemberChoicesErrorCode = keyof typeof messages;
export class MemberChoicesError extends Error {
  constructor(readonly code: MemberChoicesErrorCode) {
    super(messages[code]); this.name = "MemberChoicesError";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const cursor = /^[A-Za-z0-9_-]{1,512}\.[A-Za-z0-9_-]{43}$/;
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function identifier(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value) && value !== "00000000-0000-0000-0000-000000000000";
}
function label(value: unknown, max: number): value is string {
  return typeof value === "string" && value.length > 0 && value.length <= max
    && value.trim().length > 0 && !/\p{C}/u.test(value);
}
function failResponse(status: number, payload: Record<string, unknown>): never {
  const code = record(payload.error) ? payload.error.code : null;
  const expected: Record<string, number> = { AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403,
    LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404, PROJECT_ARCHIVED: 409,
    AUTH_RATE_LIMITED: 429 };
  if (typeof code === "string" && Object.hasOwn(expected, code) && expected[code] === status) {
    throw new MemberChoicesError(code as MemberChoicesErrorCode);
  }
  throw new MemberChoicesError("UNAVAILABLE");
}
async function envelope(response: Response): Promise<Record<string, unknown>> {
  if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
    throw new MemberChoicesError("UNAVAILABLE");
  }
  const data: unknown = await response.json();
  if (!record(data) || !identifier(data.trace_id)) throw new MemberChoicesError("UNAVAILABLE");
  if (response.status !== 200) failResponse(response.status, data);
  return data;
}

export class ProjectMemberChoicesClient {
  constructor(private readonly session: SessionClient,
    private readonly fetcher: typeof fetch = fetch, private readonly timeoutMs = 10_000) {
    if (!(session instanceof SessionClient) || !Number.isInteger(timeoutMs)
      || timeoutMs < 1 || timeoutMs > 30_000) throw new MemberChoicesError("INVALID_INPUT");
  }

  async candidate(projectId: string, username: string): Promise<MemberCandidate | null> {
    if (!identifier(projectId) || typeof username !== "string" || username.length > 255
      || !label(username, 255)) throw new MemberChoicesError("INVALID_INPUT");
    let response: Response;
    try {
      response = await this.session.resolveProjectMemberCandidate(projectId, JSON.stringify({ username }));
    } catch (failure) {
      if (failure instanceof SessionClientError) {
        if (failure.code === "AUTH_RELOGIN_REQUIRED" || failure.code === "AUTH_CLIENT_BUSY") {
          throw new MemberChoicesError(failure.code);
        }
      }
      throw new MemberChoicesError("UNAVAILABLE");
    }
    try {
      const payload = await envelope(response);
      if (!record(payload.data) || !("candidate" in payload.data)) throw new MemberChoicesError("UNAVAILABLE");
      const candidate = payload.data.candidate;
      if (candidate === null) return null;
      if (!record(candidate) || !identifier(candidate.user_id) || !label(candidate.display_name, 255)) {
        throw new MemberChoicesError("UNAVAILABLE");
      }
      return Object.freeze({ user_id: candidate.user_id, display_name: candidate.display_name });
    } catch (failure) {
      if (failure instanceof MemberChoicesError) throw failure;
      throw new MemberChoicesError("UNAVAILABLE");
    }
  }

  async activeDepartments(projectId: string): Promise<readonly ActiveDepartment[]> {
    if (!identifier(projectId)) throw new MemberChoicesError("INVALID_INPUT");
    const selected: ActiveDepartment[] = [];
    const seenIds = new Set<string>();
    const seenCursors = new Set<string>();
    let after: string | null = null;
    for (let page = 0; page < 20; page += 1) {
      const controller = new AbortController();
      const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
      try {
        const query = new URLSearchParams({ page_size: "50" });
        if (after !== null) query.set("cursor", after);
        const fetcher = this.fetcher;
        const response = await fetcher(`/api/v1/projects/${projectId}/departments?${query}`, {
          method: "GET", credentials: "same-origin", cache: "no-store", redirect: "error",
          headers: { Accept: "application/json" }, signal: controller.signal,
        });
        if (controller.signal.aborted) throw new MemberChoicesError("UNAVAILABLE");
        const payload = await envelope(response);
        if (!record(payload.data) || !Array.isArray(payload.data.items)
          || payload.data.items.length > 50 || typeof payload.data.has_more !== "boolean"
          || (payload.data.has_more && (payload.data.items.length === 0
            || typeof payload.data.next_cursor !== "string" || !cursor.test(payload.data.next_cursor)
            || seenCursors.has(payload.data.next_cursor)))
          || (!payload.data.has_more && payload.data.next_cursor !== null)) {
          throw new MemberChoicesError("UNAVAILABLE");
        }
        for (const item of payload.data.items) {
          if (!record(item) || !identifier(item.department_id) || seenIds.has(item.department_id)
            || !label(item.code, 64) || !label(item.name, 255)
            || (item.state !== "ACTIVE" && item.state !== "INACTIVE")) {
            throw new MemberChoicesError("UNAVAILABLE");
          }
          seenIds.add(item.department_id);
          if (item.state === "ACTIVE") selected.push(Object.freeze({
            department_id: item.department_id, code: item.code, name: item.name,
          }));
        }
        if (!payload.data.has_more) return Object.freeze(selected);
        after = payload.data.next_cursor as string;
        seenCursors.add(after);
      } catch (failure) {
        if (failure instanceof MemberChoicesError) throw failure;
        throw new MemberChoicesError("UNAVAILABLE");
      } finally { window.clearTimeout(timer); }
    }
    throw new MemberChoicesError("UNAVAILABLE");
  }
}
