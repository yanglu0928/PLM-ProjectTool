import { SessionClient, SessionClientError } from "./sessionClient";
import type { UserStateView } from "./adminUserStateClient";

const messages = {
  USER_NAME_INVALID_INPUT: "请核对用户名并重新读取账户详情。",
  AUTH_RELOGIN_REQUIRED: "修改用户名之前请重新登录。",
  AUTH_CLIENT_BUSY: "正在处理会话操作，请稍候。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许修改用户名。",
  RESOURCE_NOT_FOUND: "当前账户无权修改该用户，或用户不存在。",
  CONFLICT_VERSION: "账户已更新，请重新读取后决定。",
  CONFLICT_DUPLICATE: "用户名已存在，请使用其他名称。",
  USER_NAME_UNCERTAIN: "改名结果无法确认；请重新读取账户详情，不要直接重试。",
} as const;
export type AdminUserNameErrorCode = keyof typeof messages;

export class AdminUserNameError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: AdminUserNameErrorCode) {
    super(messages[code]);
    this.name = "AdminUserNameError";
    this.uncertain = code === "USER_NAME_UNCERTAIN";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const version = /^"v(0|[1-9]\d*)"$/;
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function identifier(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value)
    && value !== "00000000-0000-0000-0000-000000000000";
}
function utcInstant(value: unknown): value is string {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/.test(value)) return false;
  const calendar = Date.parse(value.slice(0, 19) + "Z");
  return Number.isFinite(Date.parse(value)) && Number.isFinite(calendar)
    && new Date(calendar).toISOString().slice(0, 19) === value.slice(0, 19);
}

export class AdminUserNameClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) throw new AdminUserNameError("USER_NAME_INVALID_INPUT");
  }

  async change(before: UserStateView, proposed: string): Promise<UserStateView> {
    const match = typeof before?.etag === "string" ? version.exec(before.etag) : null;
    const prior = match ? Number(match[1]) : NaN;
    const name = typeof proposed === "string" ? proposed.normalize("NFC").trim() : "";
    if (!record(before) || !identifier(before.user_id)
      || !Number.isSafeInteger(prior) || prior < 0 || prior >= Number.MAX_SAFE_INTEGER
      || typeof before.username_display !== "string" || !before.username_display
      || (before.account_state !== "ENABLED" && before.account_state !== "DISABLED")
      || (before.deployment_role !== "NONE" && before.deployment_role !== "DEPLOYMENT_ADMIN")
      || !Number.isSafeInteger(before.credential_version) || before.credential_version < 0
      || !utcInstant(before.created_at) || !utcInstant(before.updated_at)
      || Date.parse(before.updated_at) < Date.parse(before.created_at)
      || !name || Array.from(name).length > 255 || /\p{C}/u.test(name)) {
      throw new AdminUserNameError("USER_NAME_INVALID_INPUT");
    }
    let response: Response;
    try {
      response = await this.session.patchAdminUserName(before.user_id, before.etag, name);
    } catch (failure) {
      if (failure instanceof SessionClientError && failure.code === "AUTH_RELOGIN_REQUIRED") {
        throw new AdminUserNameError("AUTH_RELOGIN_REQUIRED");
      }
      if (failure instanceof SessionClientError && failure.code === "AUTH_CLIENT_BUSY") {
        throw new AdminUserNameError("AUTH_CLIENT_BUSY");
      }
      throw new AdminUserNameError("USER_NAME_UNCERTAIN");
    }
    try {
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
        throw new AdminUserNameError("USER_NAME_UNCERTAIN");
      }
      const payload: unknown = await response.json();
      if (!record(payload) || !identifier(payload.trace_id)) {
        throw new AdminUserNameError("USER_NAME_UNCERTAIN");
      }
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const known: Record<string, number> = { AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403,
          LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404, CONFLICT_VERSION: 409,
          CONFLICT_DUPLICATE: 409, REQUEST_MALFORMED: 400, VALIDATION_FAILED: 422,
          CONFLICT_VERSION_REQUIRED: 428 };
        if (typeof code === "string" && Object.hasOwn(known, code) && response.status === known[code]) {
          throw new AdminUserNameError(["REQUEST_MALFORMED", "VALIDATION_FAILED", "CONFLICT_VERSION_REQUIRED"].includes(code)
            ? "USER_NAME_INVALID_INPUT" : code as AdminUserNameErrorCode);
        }
        throw new AdminUserNameError("USER_NAME_UNCERTAIN");
      }
      const data = payload.data;
      const unchanged = record(data) && data.etag === before.etag;
      const expectedEtag = unchanged ? before.etag : `"v${prior + 1}"`;
      if (!record(data) || data.user_id !== before.user_id || data.username_display !== name
        || (unchanged && name !== before.username_display)
        || (!unchanged && name === before.username_display)
        || data.account_state !== before.account_state || data.deployment_role !== before.deployment_role
        || data.credential_version !== before.credential_version || data.created_at !== before.created_at
        || !utcInstant(data.updated_at) || Date.parse(data.updated_at) < Date.parse(before.updated_at)
        || (unchanged && data.updated_at !== before.updated_at)
        || data.etag !== expectedEtag || response.headers.get("etag") !== expectedEtag) {
        throw new AdminUserNameError("USER_NAME_UNCERTAIN");
      }
      return Object.freeze({ user_id: before.user_id, username_display: name,
        account_state: before.account_state, deployment_role: before.deployment_role,
        credential_version: before.credential_version, created_at: before.created_at,
        updated_at: data.updated_at as string, etag: expectedEtag });
    } catch (failure) {
      if (failure instanceof AdminUserNameError) throw failure;
      throw new AdminUserNameError("USER_NAME_UNCERTAIN");
    }
  }
}
