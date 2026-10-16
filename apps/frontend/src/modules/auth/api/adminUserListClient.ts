/** Safe Admin User metadata for picking a proposed first Project Manager. */
export interface UserCandidate {
  readonly user_id: string;
  readonly username_display: string;
  readonly account_state: "ENABLED" | "DISABLED";
}

export interface UserCandidatePage {
  readonly items: readonly UserCandidate[];
  readonly next_cursor: string | null;
  readonly has_more: boolean;
}

const messages = {
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许读取用户列表。",
  RESOURCE_NOT_FOUND: "当前账户无权读取用户列表。",
  USER_LIST_CURSOR_INVALID: "用户列表位置已失效，请从第一页重新读取。",
  USER_LIST_UNAVAILABLE: "暂时无法读取用户列表，请稍后重试。",
} as const;
export type UserCandidateErrorCode = keyof typeof messages;

export class UserCandidateError extends Error {
  constructor(readonly code: UserCandidateErrorCode) {
    super(messages[code]);
    this.name = "UserCandidateError";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const cursorPattern = /^u1\.[A-Za-z0-9_-]{1,1536}$/;
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function identifier(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value) && value !== "00000000-0000-0000-0000-000000000000";
}

export class AdminUserListClient {
  constructor(private readonly fetcher: typeof fetch = fetch, private readonly timeoutMs = 10_000) {
    if (!Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 30_000) {
      throw new UserCandidateError("USER_LIST_UNAVAILABLE");
    }
  }

  async page(cursor: string | null = null): Promise<UserCandidatePage> {
    if (cursor !== null && (typeof cursor !== "string" || !cursorPattern.test(cursor))) {
      throw new UserCandidateError("USER_LIST_CURSOR_INVALID");
    }
    const path = `/api/v1/admin/users?page_size=50${cursor === null ? "" : `&cursor=${encodeURIComponent(cursor)}`}`;
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const fetcher = this.fetcher;
      const response = await fetcher(path, { method: "GET", credentials: "same-origin", cache: "no-store",
        redirect: "error", headers: { Accept: "application/json" }, signal: controller.signal });
      if (controller.signal.aborted || response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
        throw new UserCandidateError("USER_LIST_UNAVAILABLE");
      }
      const payload: unknown = await response.json();
      if (controller.signal.aborted || !record(payload) || !identifier(payload.trace_id)) {
        throw new UserCandidateError("USER_LIST_UNAVAILABLE");
      }
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const expected: Record<string, number> = { AUTH_SESSION_EXPIRED: 401,
          LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404, REQUEST_MALFORMED: 400 };
        if (typeof code === "string" && Object.hasOwn(expected, code) && response.status === expected[code]) {
          throw new UserCandidateError(code === "REQUEST_MALFORMED" ? "USER_LIST_CURSOR_INVALID" : code as UserCandidateErrorCode);
        }
        throw new UserCandidateError("USER_LIST_UNAVAILABLE");
      }
      const data = payload.data;
      if (!record(data) || !Array.isArray(data.items) || data.items.length > 50
        || typeof data.has_more !== "boolean"
        || (data.next_cursor !== null && (typeof data.next_cursor !== "string" || !cursorPattern.test(data.next_cursor)))
        || data.has_more !== (data.next_cursor !== null)
        || (data.has_more && data.items.length !== 50)) {
        throw new UserCandidateError("USER_LIST_UNAVAILABLE");
      }
      const items: UserCandidate[] = data.items.map((value: unknown) => {
        if (!record(value) || !identifier(value.user_id)
          || typeof value.username_display !== "string" || !value.username_display.trim()
          || (value.account_state !== "ENABLED" && value.account_state !== "DISABLED")
          || (value.deployment_role !== "NONE" && value.deployment_role !== "DEPLOYMENT_ADMIN")) {
          throw new UserCandidateError("USER_LIST_UNAVAILABLE");
        }
        return Object.freeze({ user_id: value.user_id, username_display: value.username_display,
          account_state: value.account_state });
      });
      if (new Set(items.map((item) => item.user_id)).size !== items.length) {
        throw new UserCandidateError("USER_LIST_UNAVAILABLE");
      }
      return Object.freeze({ items: Object.freeze(items), next_cursor: data.next_cursor as string | null,
        has_more: data.has_more });
    } catch (failure) {
      if (failure instanceof UserCandidateError) throw failure;
      throw new UserCandidateError("USER_LIST_UNAVAILABLE");
    } finally { window.clearTimeout(timer); }
  }
}
