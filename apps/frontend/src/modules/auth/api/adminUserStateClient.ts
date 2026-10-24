import { SessionClient, SessionClientError } from "./sessionClient";

export type UserStateAction = "enable" | "disable";
export interface UserStateView {
  readonly user_id: string;
  readonly username_display: string;
  readonly account_state: "ENABLED" | "DISABLED";
  readonly deployment_role: "NONE" | "DEPLOYMENT_ADMIN";
  readonly credential_version: number;
  readonly created_at: string;
  readonly updated_at: string;
  readonly etag: string;
}

const messages = {
  USER_STATE_INVALID_INPUT: "请刷新用户信息后再操作。",
  AUTH_RELOGIN_REQUIRED: "更改账户状态前请重新登录。",
  AUTH_CLIENT_BUSY: "正在处理会话操作，请稍候。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许更改账户状态。",
  RESOURCE_NOT_FOUND: "当前账户无权更改该用户状态，或目标不存在。",
  AUTH_USER_DISABLED: "目标状态冲突；可能涉及最后一名启用的管理员，请刷新后核对。",
  CONFLICT_VERSION: "账户已更新，请刷新后重新决定。",
  CONFLICT_IDEMPOTENCY: "原操作标识与请求不一致，已停止重试。",
  USER_STATE_UNCERTAIN: "状态修改结果无法确认；请保留原操作标识和原版本，不要以新操作标识重试。",
} as const;
export type AdminUserStateErrorCode = keyof typeof messages;

export class AdminUserStateError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: AdminUserStateErrorCode) {
    super(messages[code]);
    this.name = "AdminUserStateError";
    this.uncertain = code === "USER_STATE_UNCERTAIN";
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
  const date = Date.parse(value);
  const calendar = Date.parse(value.slice(0, 19) + "Z");
  return Number.isFinite(date) && Number.isFinite(calendar)
    && new Date(calendar).toISOString().slice(0, 19) === value.slice(0, 19);
}

export class AdminUserStateClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) throw new AdminUserStateError("USER_STATE_INVALID_INPUT");
  }

  async change(userId: string, action: UserStateAction, etag: string, idempotencyKey: string): Promise<UserStateView> {
    const match = typeof etag === "string" ? version.exec(etag) : null;
    const prior = match ? Number(match[1]) : NaN;
    if (!identifier(userId) || (action !== "enable" && action !== "disable")
      || !Number.isSafeInteger(prior) || prior < 0 || prior >= Number.MAX_SAFE_INTEGER
      || typeof idempotencyKey !== "string" || !/^[\x20-\x7e]{16,128}$/.test(idempotencyKey)) {
      throw new AdminUserStateError("USER_STATE_INVALID_INPUT");
    }
    let response: Response;
    try {
      response = await this.session.postAdminUserState(userId, action, etag, idempotencyKey);
    } catch (failure) {
      if (failure instanceof SessionClientError && failure.code === "AUTH_RELOGIN_REQUIRED") {
        throw new AdminUserStateError("AUTH_RELOGIN_REQUIRED");
      }
      if (failure instanceof SessionClientError && failure.code === "AUTH_CLIENT_BUSY") {
        throw new AdminUserStateError("AUTH_CLIENT_BUSY");
      }
      throw new AdminUserStateError("USER_STATE_UNCERTAIN");
    }
    try {
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
        throw new AdminUserStateError("USER_STATE_UNCERTAIN");
      }
      const payload: unknown = await response.json();
      if (!record(payload) || !identifier(payload.trace_id)) {
        throw new AdminUserStateError("USER_STATE_UNCERTAIN");
      }
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const known: Record<string, number> = { AUTH_SESSION_EXPIRED: 401, AUTH_CSRF_INVALID: 403,
          LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404, AUTH_USER_DISABLED: 409,
          CONFLICT_VERSION: 409, CONFLICT_IDEMPOTENCY: 409,
          REQUEST_MALFORMED: 400, VALIDATION_FAILED: 422, CONFLICT_VERSION_REQUIRED: 428 };
        if (typeof code === "string" && Object.hasOwn(known, code) && response.status === known[code]) {
          throw new AdminUserStateError(["REQUEST_MALFORMED", "VALIDATION_FAILED", "CONFLICT_VERSION_REQUIRED"].includes(code)
            ? "USER_STATE_INVALID_INPUT" : code as AdminUserStateErrorCode);
        }
        throw new AdminUserStateError("USER_STATE_UNCERTAIN");
      }
      const data = payload.data;
      const expectedEtag = `"v${prior + 1}"`;
      if (!record(data) || data.user_id !== userId
        || typeof data.username_display !== "string" || !data.username_display.trim()
        || Array.from(data.username_display).length > 255
        || data.account_state !== (action === "enable" ? "ENABLED" : "DISABLED")
        || (data.deployment_role !== "NONE" && data.deployment_role !== "DEPLOYMENT_ADMIN")
        || !Number.isSafeInteger(data.credential_version) || (data.credential_version as number) < 1
        || !utcInstant(data.created_at) || !utcInstant(data.updated_at)
        || Date.parse(data.updated_at) < Date.parse(data.created_at)
        || data.etag !== expectedEtag || response.headers.get("etag") !== expectedEtag) {
        throw new AdminUserStateError("USER_STATE_UNCERTAIN");
      }
      return Object.freeze({ user_id: userId, username_display: data.username_display,
        account_state: action === "enable" ? "ENABLED" : "DISABLED",
        deployment_role: data.deployment_role as UserStateView["deployment_role"],
        credential_version: data.credential_version as number, created_at: data.created_at,
        updated_at: data.updated_at, etag: expectedEtag });
    } catch (failure) {
      if (failure instanceof AdminUserStateError) throw failure;
      throw new AdminUserStateError("USER_STATE_UNCERTAIN");
    }
  }
}
