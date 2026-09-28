import { SessionClient, SessionClientError } from "./sessionClient";

export interface AdminUserCreateInput {
  readonly username: string;
  readonly password: string;
}

export interface CreatedUserView {
  readonly user_id: string;
  readonly username_display: string;
  readonly account_state: "ENABLED";
  readonly deployment_role: "NONE";
  readonly credential_version: 1;
  readonly created_at: string;
  readonly updated_at: string;
  readonly etag: '"v1"';
}

const messages = {
  USER_CREATE_INVALID_INPUT: "请检查用户名和初始密码。",
  AUTH_RELOGIN_REQUIRED: "创建账户前请重新登录。",
  AUTH_CLIENT_BUSY: "正在处理会话操作，请稍候。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许创建账户。",
  RESOURCE_NOT_FOUND: "当前账户无权创建账户。",
  CONFLICT_DUPLICATE: "该用户名已存在。",
  CONFLICT_IDEMPOTENCY: "原操作记录与输入不一致，已停止重试。",
  USER_CREATE_UNCERTAIN: "账户创建结果无法确认。请勿使用新操作标识重复创建。",
} as const;
export type AdminUserCreateErrorCode = keyof typeof messages;

export class AdminUserCreateError extends Error {
  readonly uncertain: boolean;
  constructor(readonly code: AdminUserCreateErrorCode) {
    super(messages[code]);
    this.name = "AdminUserCreateError";
    this.uncertain = code === "USER_CREATE_UNCERTAIN";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
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

function prepare(input: AdminUserCreateInput, key: string): { body: string; username: string } {
  if (!record(input) || typeof input.username !== "string" || typeof input.password !== "string"
    || typeof key !== "string" || !/^[\x20-\x7e]{16,128}$/.test(key)) {
    throw new AdminUserCreateError("USER_CREATE_INVALID_INPUT");
  }
  const username = input.username.trim().normalize("NFC");
  const bytes = new TextEncoder().encode(input.password);
  if (!username || Array.from(username).length > 255 || /\p{C}/u.test(username)
    || bytes.length < 1 || bytes.length > 1024 || input.password.includes("\0")) {
    throw new AdminUserCreateError("USER_CREATE_INVALID_INPUT");
  }
  return { body: JSON.stringify({ username, password: input.password }), username };
}

export class AdminUserCreateClient {
  constructor(private readonly session: SessionClient) {
    if (!(session instanceof SessionClient)) throw new AdminUserCreateError("USER_CREATE_INVALID_INPUT");
  }

  async create(input: AdminUserCreateInput, idempotencyKey: string): Promise<CreatedUserView> {
    const prepared = prepare(input, idempotencyKey);
    let response: Response;
    try {
      response = await this.session.postAdminUserCreate(prepared.body, idempotencyKey);
    } catch (failure) {
      if (failure instanceof SessionClientError && failure.code === "AUTH_RELOGIN_REQUIRED") {
        throw new AdminUserCreateError("AUTH_RELOGIN_REQUIRED");
      }
      if (failure instanceof SessionClientError && failure.code === "AUTH_CLIENT_BUSY") {
        throw new AdminUserCreateError("AUTH_CLIENT_BUSY");
      }
      throw new AdminUserCreateError("USER_CREATE_UNCERTAIN");
    }
    try {
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
        throw new AdminUserCreateError("USER_CREATE_UNCERTAIN");
      }
      const payload: unknown = await response.json();
      if (!record(payload) || !identifier(payload.trace_id)) {
        throw new AdminUserCreateError("USER_CREATE_UNCERTAIN");
      }
      if (response.status !== 201) {
        const code = record(payload.error) ? payload.error.code : null;
        const expected: Record<string, number> = { AUTH_SESSION_EXPIRED: 401,
          AUTH_CSRF_INVALID: 403, LICENSE_OPERATION_DENIED: 403, RESOURCE_NOT_FOUND: 404,
          CONFLICT_DUPLICATE: 409, CONFLICT_IDEMPOTENCY: 409,
          REQUEST_MALFORMED: 400, VALIDATION_FAILED: 422 };
        if (typeof code === "string" && Object.hasOwn(expected, code) && response.status === expected[code]) {
          throw new AdminUserCreateError(code === "REQUEST_MALFORMED" || code === "VALIDATION_FAILED"
            ? "USER_CREATE_INVALID_INPUT" : code as AdminUserCreateErrorCode);
        }
        throw new AdminUserCreateError("USER_CREATE_UNCERTAIN");
      }
      const data = payload.data;
      if (!record(data) || !identifier(data.user_id)
        || data.username_display !== prepared.username || data.account_state !== "ENABLED"
        || data.deployment_role !== "NONE" || data.credential_version !== 1
        || !utcInstant(data.created_at) || !utcInstant(data.updated_at)
        || Date.parse(data.updated_at) < Date.parse(data.created_at)
        || data.etag !== '"v1"' || response.headers.get("etag") !== data.etag
        || response.headers.get("location") !== `/api/v1/admin/users/${data.user_id}`) {
        throw new AdminUserCreateError("USER_CREATE_UNCERTAIN");
      }
      return Object.freeze({ user_id: data.user_id, username_display: data.username_display,
        account_state: "ENABLED", deployment_role: "NONE", credential_version: 1,
        created_at: data.created_at, updated_at: data.updated_at, etag: '"v1"' });
    } catch (failure) {
      if (failure instanceof AdminUserCreateError) throw failure;
      throw new AdminUserCreateError("USER_CREATE_UNCERTAIN");
    }
  }
}
