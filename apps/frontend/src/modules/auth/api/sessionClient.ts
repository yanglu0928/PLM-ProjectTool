/** Same-origin Auth transport. Views are hints, never authorization capabilities. */
export interface SessionView {
  readonly user: Readonly<{ user_id: string; username_display: string }>;
  readonly deployment_role: "NONE" | "DEPLOYMENT_ADMIN";
  readonly password_change_required: boolean;
  readonly authorized_projects: readonly Readonly<{ project_id: string; name: string; role: string }>[];
  readonly absolute_expires_at: string;
  readonly idle_expires_at: string;
}

const messages = {
  AUTH_INVALID_CREDENTIALS: "用户名或密码不正确。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  AUTH_CSRF_INVALID: "登录状态已变化，请重新登录。",
  AUTH_RATE_LIMITED: "尝试过于频繁，请稍后再试。",
  AUTH_RELOGIN_REQUIRED: "请重新登录以继续此操作。",
  VALIDATION_FAILED: "密码格式不符合要求。",
  CONFLICT_IDEMPOTENCY: "此操作记录与本次输入不一致，请勿重复提交。",
  AUTH_CLIENT_BUSY: "正在处理登录操作，请稍候。",
  AUTH_CLIENT_UNAVAILABLE: "暂时无法确认登录状态，请重新登录。",
} as const;
export type SessionClientErrorCode = keyof typeof messages;

export class SessionClientError extends Error {
  constructor(readonly code: SessionClientErrorCode) {
    super(messages[code]);
    this.name = "SessionClientError";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const csrf = /^[0-9a-f]{64}$/;
const projectRoles = new Set(["PROJECT_MANAGER", "IMPLEMENTATION_MEMBER", "CUSTOMER_MANAGER", "CUSTOMER_MEMBER"]);
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function identifier(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value) && value !== "00000000-0000-0000-0000-000000000000";
}
function text(value: unknown): value is string {
  return typeof value === "string" && value.length > 0;
}
function instant(value: unknown): value is string {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$/.test(value)) return false;
  const parsed = Date.parse(value);
  const calendar = Date.parse(value.slice(0, 19) + "Z");
  return Number.isFinite(parsed) && Number.isFinite(calendar)
    && new Date(calendar).toISOString().slice(0, 19) === value.slice(0, 19);
}
function parseView(data: unknown): SessionView {
  if (!record(data) || !record(data.user) || !identifier(data.user.user_id)
    || !text(data.user.username_display) || typeof data.deployment_role !== "string"
    || !["NONE", "DEPLOYMENT_ADMIN"].includes(data.deployment_role)
    || typeof data.password_change_required !== "boolean" || !Array.isArray(data.authorized_projects)
    || !instant(data.absolute_expires_at) || !instant(data.idle_expires_at)
    || Date.parse(data.idle_expires_at) > Date.parse(data.absolute_expires_at)) {
    throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
  }
  const projects = data.authorized_projects.map((item: unknown) => {
    if (!record(item) || !identifier(item.project_id) || !text(item.name)
      || typeof item.role !== "string" || !projectRoles.has(item.role)) {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    }
    return Object.freeze({ project_id: item.project_id, name: item.name, role: item.role });
  });
  if (new Set(projects.map((item) => item.project_id)).size !== projects.length
    || (data.password_change_required && (data.deployment_role !== "NONE" || projects.length !== 0))) {
    throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
  }
  return Object.freeze({
    user: Object.freeze({ user_id: data.user.user_id, username_display: data.user.username_display }),
    deployment_role: data.deployment_role as SessionView["deployment_role"],
    password_change_required: data.password_change_required,
    authorized_projects: Object.freeze(projects),
    absolute_expires_at: new Date(data.absolute_expires_at).toISOString(),
    idle_expires_at: new Date(data.idle_expires_at).toISOString(),
  });
}

export class SessionClient {
  #csrf: string | null = null;
  #view: SessionView | null = null;
  #busy = false;
  constructor(private readonly fetcher: typeof fetch = fetch, private readonly timeoutMs = 10_000) {
    if (!Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 30_000) {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    }
  }
  get view(): SessionView | null { return this.#view; }
  get canSubmit(): boolean { return this.#csrf !== null && !this.#busy; }

  async #exclusive<T>(action: (token: string | null) => Promise<T>): Promise<T> {
    if (this.#busy) throw new SessionClientError("AUTH_CLIENT_BUSY");
    this.#busy = true;
    const token = this.#csrf;
    this.#csrf = null;
    this.#view = null;
    try { return await action(token); }
    catch (error) {
      this.#csrf = null;
      this.#view = null;
      if (error instanceof SessionClientError) throw error;
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    } finally { this.#busy = false; }
  }

  async #request(path: string, method: "GET" | "POST", headers: Record<string, string> = {}, body?: string): Promise<unknown> {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      // Do not invoke native Window.fetch with the SessionClient as its receiver.
      const fetcher = this.fetcher;
      const response = await fetcher(path, { method, credentials: "same-origin", cache: "no-store",
        redirect: "error", headers: { Accept: "application/json", ...headers }, body, signal: controller.signal });
      if (controller.signal.aborted) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
      if (response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
        throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
      }
      const payload: unknown = await response.json();
      if (controller.signal.aborted || !record(payload) || !identifier(payload.trace_id)) {
        throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
      }
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const expected: Record<string, number> = { AUTH_INVALID_CREDENTIALS: 401, AUTH_SESSION_EXPIRED: 401,
          AUTH_CSRF_INVALID: 403, AUTH_RATE_LIMITED: 429, VALIDATION_FAILED: 422,
          CONFLICT_IDEMPOTENCY: 409 };
        if (typeof code === "string" && Object.hasOwn(expected, code) && response.status === expected[code]) {
          throw new SessionClientError(code as SessionClientErrorCode);
        }
        throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
      }
      return payload.data;
    } finally { window.clearTimeout(timer); }
  }

  #accept(data: unknown, requireCsrf: boolean): SessionView {
    const view = parseView(data);
    if (requireCsrf) {
      if (!record(data) || typeof data.csrf_token !== "string" || !csrf.test(data.csrf_token)) {
        throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
      }
      this.#csrf = data.csrf_token;
    }
    this.#view = view;
    return view;
  }

  login(username: string, password: string): Promise<SessionView> {
    return this.#exclusive(async () => {
      if (typeof username !== "string" || typeof password !== "string") throw new SessionClientError("AUTH_INVALID_CREDENTIALS");
      return this.#accept(await this.#request("/api/v1/auth/login", "POST", { "Content-Type": "application/json" },
        JSON.stringify({ username, password })), true);
    });
  }
  current(): Promise<SessionView> {
    // GET cannot recover CSRF after reload or establish write authority.
    return this.#exclusive(async () => this.#accept(await this.#request("/api/v1/auth/session", "GET"), false));
  }
  renew(): Promise<SessionView> {
    const userId = this.#view?.user.user_id;
    return this.#exclusive(async (token) => {
      if (token === null) throw new SessionClientError("AUTH_RELOGIN_REQUIRED");
      const view = this.#accept(await this.#request("/api/v1/auth/session:renew", "POST", { "X-CSRF-Token": token }), true);
      if (view.user.user_id !== userId) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
      return view;
    });
  }
  logout(idempotencyKey: string): Promise<void> {
    return this.#exclusive(async (token) => {
      if (token === null) throw new SessionClientError("AUTH_RELOGIN_REQUIRED");
      if (typeof idempotencyKey !== "string" || !/^[\x20-\x7e]{16,128}$/.test(idempotencyKey)) {
        throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
      }
      const data = await this.#request("/api/v1/auth/logout", "POST", {
        "X-CSRF-Token": token, "Idempotency-Key": idempotencyKey,
      });
      if (!record(data) || data.revoked !== true) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    });
  }

  /** Frozen create command paths; the CSRF token never leaves this client. */
  async #postCommand(path: "/api/v1/projects" | "/api/v1/admin/users" | `/api/v1/projects/${string}/members`, body: string,
    idempotencyKey: string, maxBodyBytes: number): Promise<Response> {
    if (this.#busy) throw new SessionClientError("AUTH_CLIENT_BUSY");
    if (this.#csrf === null || this.#view === null) throw new SessionClientError("AUTH_RELOGIN_REQUIRED");
    if (typeof body !== "string" || new TextEncoder().encode(body).length > maxBodyBytes || body.length === 0
      || typeof idempotencyKey !== "string" || !/^[\x20-\x7e]{16,128}$/.test(idempotencyKey)) {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    }
    this.#busy = true;
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const fetcher = this.fetcher;
      const response = await fetcher(path, { method: "POST", credentials: "same-origin",
        cache: "no-store", redirect: "error", headers: { Accept: "application/json",
          "Content-Type": "application/json", "X-CSRF-Token": this.#csrf,
          "Idempotency-Key": idempotencyKey }, body, signal: controller.signal });
      if (controller.signal.aborted) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
      if (response.status === 401) { this.#csrf = null; this.#view = null; }
      return response;
    } catch {
      // A timed-out idempotent command may have committed; do not retry or rotate its key here.
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    } finally {
      window.clearTimeout(timer);
      this.#busy = false;
    }
  }

  postProjectCreate(body: string, idempotencyKey: string): Promise<Response> {
    return this.#postCommand("/api/v1/projects", body, idempotencyKey, 8192);
  }

  async postProjectMemberCreate(projectId: string, body: string, idempotencyKey: string): Promise<Response> {
    if (!identifier(projectId)) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    return this.#postCommand(`/api/v1/projects/${projectId}/members`, body, idempotencyKey, 8192);
  }

  postAdminUserCreate(body: string, idempotencyKey: string): Promise<Response> {
    return this.#postCommand("/api/v1/admin/users", body, idempotencyKey, 16384);
  }

  /** Frozen empty-body state commands. A 200 replay cannot prove the current session was revoked. */
  async postAdminUserState(userId: string, action: "enable" | "disable",
    etag: string, idempotencyKey: string): Promise<Response> {
    if (this.#busy) throw new SessionClientError("AUTH_CLIENT_BUSY");
    if (this.#csrf === null || this.#view === null) throw new SessionClientError("AUTH_RELOGIN_REQUIRED");
    if (!identifier(userId) || (action !== "enable" && action !== "disable")
      || typeof etag !== "string" || !/^"v(?:0|[1-9]\d*)"$/.test(etag)
      || !Number.isSafeInteger(Number(etag.slice(2, -1)))
      || Number(etag.slice(2, -1)) >= Number.MAX_SAFE_INTEGER
      || typeof idempotencyKey !== "string" || !/^[\x20-\x7e]{16,128}$/.test(idempotencyKey)) {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    }
    this.#busy = true;
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const fetcher = this.fetcher;
      const response = await fetcher(`/api/v1/admin/users/${userId}:${action}`, {
        method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error",
        headers: { Accept: "application/json", "X-CSRF-Token": this.#csrf,
          "Idempotency-Key": idempotencyKey, "If-Match": etag }, signal: controller.signal,
      });
      if (controller.signal.aborted) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
      if (response.status === 401) { this.#csrf = null; this.#view = null; }
      return response;
    } catch {
      // Commit may have succeeded before the connection failed; caller must retain Key/If-Match.
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    } finally {
      window.clearTimeout(timer);
      this.#busy = false;
    }
  }

  /** Name PATCH has no idempotency key; an uncertain response must be reconciled by GET. */
  async patchAdminUserName(userId: string, etag: string, username: string): Promise<Response> {
    if (this.#busy) throw new SessionClientError("AUTH_CLIENT_BUSY");
    if (this.#csrf === null || this.#view === null) throw new SessionClientError("AUTH_RELOGIN_REQUIRED");
    if (!identifier(userId) || typeof etag !== "string" || !/^"v(?:0|[1-9]\d*)"$/.test(etag)
      || !Number.isSafeInteger(Number(etag.slice(2, -1)))
      || Number(etag.slice(2, -1)) >= Number.MAX_SAFE_INTEGER
      || typeof username !== "string" || !username.trim()
      || Array.from(username.normalize("NFC").trim()).length > 255) {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    }
    const body = JSON.stringify({ username });
    if (new TextEncoder().encode(body).length > 16_384) {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    }
    this.#busy = true;
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const fetcher = this.fetcher;
      const response = await fetcher(`/api/v1/admin/users/${userId}`, {
        method: "PATCH", credentials: "same-origin", cache: "no-store", redirect: "error",
        headers: { Accept: "application/json", "Content-Type": "application/json",
          "X-CSRF-Token": this.#csrf, "If-Match": etag }, body, signal: controller.signal,
      });
      if (controller.signal.aborted) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
      if (response.status === 401) { this.#csrf = null; this.#view = null; }
      return response;
    } catch {
      // The write may have committed before the connection failed; caller must GET before deciding.
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    } finally {
      window.clearTimeout(timer);
      this.#busy = false;
    }
  }

  async changePassword(currentPassword: string, newPassword: string, idempotencyKey: string): Promise<number> {
    const validPassword = (value: unknown): value is string => {
      if (typeof value !== "string" || value.includes("\0")) return false;
      const size = new TextEncoder().encode(value).length;
      return size >= 1 && size <= 1024;
    };
    if (!validPassword(currentPassword) || !validPassword(newPassword)) {
      throw new SessionClientError("VALIDATION_FAILED");
    }
    if (typeof idempotencyKey !== "string" || !/^[\x20-\x7e]{16,128}$/.test(idempotencyKey)) {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    }
    return this.#exclusive(async (token) => {
      if (token === null) throw new SessionClientError("AUTH_RELOGIN_REQUIRED");
      const data = await this.#request("/api/v1/auth/password:change", "POST", {
        "Content-Type": "application/json", "X-CSRF-Token": token,
        "Idempotency-Key": idempotencyKey,
      }, JSON.stringify({ current_password: currentPassword, new_password: newPassword }));
      if (!record(data) || !Number.isSafeInteger(data.credential_version)
        || (data.credential_version as number) < 2) {
        throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
      }
      return data.credential_version as number;
    });
  }
}
