import type { UserStateView } from "./adminUserStateClient";

const messages = {
  USER_DETAIL_INVALID_ID: "用户标识无效，请重新选择。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许读取用户详情。",
  RESOURCE_NOT_FOUND: "当前账户无权读取该用户，或用户不存在。",
  USER_DETAIL_UNAVAILABLE: "暂时无法读取用户详情，请稍后重试。",
} as const;
export type AdminUserDetailErrorCode = keyof typeof messages;

export class AdminUserDetailError extends Error {
  constructor(readonly code: AdminUserDetailErrorCode) {
    super(messages[code]);
    this.name = "AdminUserDetailError";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const etagPattern = /^"v(0|[1-9]\d*)"$/;
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function identifier(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value)
    && value !== "00000000-0000-0000-0000-000000000000";
}
function utcInstant(value: unknown): value is string {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/.test(value)) return false;
  const date = Date.parse(value);
  const calendar = Date.parse(value.slice(0, 19) + "Z");
  return Number.isFinite(date) && Number.isFinite(calendar)
    && new Date(calendar).toISOString().slice(0, 19) === value.slice(0, 19);
}

export class AdminUserDetailClient {
  constructor(private readonly fetcher: typeof fetch = fetch, private readonly timeoutMs = 10_000) {
    if (!Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 30_000) {
      throw new AdminUserDetailError("USER_DETAIL_UNAVAILABLE");
    }
  }

  async get(userId: string): Promise<UserStateView> {
    if (!identifier(userId)) throw new AdminUserDetailError("USER_DETAIL_INVALID_ID");
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const fetcher = this.fetcher;
      const response = await fetcher(`/api/v1/admin/users/${userId}`, {
        method: "GET", credentials: "same-origin", cache: "no-store", redirect: "error",
        headers: { Accept: "application/json" }, signal: controller.signal,
      });
      if (controller.signal.aborted || response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
        throw new AdminUserDetailError("USER_DETAIL_UNAVAILABLE");
      }
      const payload: unknown = await response.json();
      if (controller.signal.aborted || !record(payload) || !identifier(payload.trace_id)) {
        throw new AdminUserDetailError("USER_DETAIL_UNAVAILABLE");
      }
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const known: Record<string, number> = { AUTH_SESSION_EXPIRED: 401,
          LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404 };
        if (typeof code === "string" && Object.hasOwn(known, code) && response.status === known[code]) {
          throw new AdminUserDetailError(code as AdminUserDetailErrorCode);
        }
        throw new AdminUserDetailError("USER_DETAIL_UNAVAILABLE");
      }
      const data = payload.data;
      const etag = record(data) ? data.etag : null;
      const match = typeof etag === "string" ? etagPattern.exec(etag) : null;
      if (!record(data) || data.user_id !== userId
        || typeof data.username_display !== "string" || !data.username_display.trim()
        || Array.from(data.username_display).length > 255
        || (data.account_state !== "ENABLED" && data.account_state !== "DISABLED")
        || (data.deployment_role !== "NONE" && data.deployment_role !== "DEPLOYMENT_ADMIN")
        || !Number.isSafeInteger(data.credential_version) || (data.credential_version as number) < 0
        || (data.account_state === "ENABLED" && data.credential_version === 0)
        || !utcInstant(data.created_at) || !utcInstant(data.updated_at)
        || Date.parse(data.updated_at) < Date.parse(data.created_at)
        || !match || !Number.isSafeInteger(Number(match[1]))
        || Number(match[1]) >= Number.MAX_SAFE_INTEGER
        || response.headers.get("etag") !== etag) {
        throw new AdminUserDetailError("USER_DETAIL_UNAVAILABLE");
      }
      return Object.freeze({ user_id: userId, username_display: data.username_display,
        account_state: data.account_state as UserStateView["account_state"],
        deployment_role: data.deployment_role as UserStateView["deployment_role"],
        credential_version: data.credential_version as number, created_at: data.created_at,
        updated_at: data.updated_at, etag: etag as string });
    } catch (failure) {
      if (failure instanceof AdminUserDetailError) throw failure;
      throw new AdminUserDetailError("USER_DETAIL_UNAVAILABLE");
    } finally { window.clearTimeout(timer); }
  }
}
