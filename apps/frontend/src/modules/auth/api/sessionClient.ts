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
const uploadToken = /^[A-Za-z0-9_-]{43}$/;
const sha256 = /^[0-9a-f]{64}$/;
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
  async #postCommand(path: "/api/v1/projects" | "/api/v1/admin/users"
    | `/api/v1/projects/${string}/members` | `/api/v1/projects/${string}/departments`
    | `/api/v1/projects/${string}/document-uploads`
    | `/api/v1/projects/${string}/egress-previews`
    | `/api/v1/projects/${string}/ai-tasks`
    | `/api/v1/projects/${string}/retrieval-runs`, body: string,
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

  /** Project UploadIntent only; content and finalize require separate guarded transports. */
  postProjectDocumentUploadCreate(projectId: string, body: string, idempotencyKey: string): Promise<Response> {
    if (!identifier(projectId)) return Promise.reject(new SessionClientError("AUTH_CLIENT_UNAVAILABLE"));
    return this.#postCommand(`/api/v1/projects/${projectId}/document-uploads`, body, idempotencyKey, 8192);
  }

  postProjectAIEgressPreview(projectId: string, body: string, idempotencyKey: string): Promise<Response> {
    if (!identifier(projectId)) return Promise.reject(new SessionClientError("AUTH_CLIENT_UNAVAILABLE"));
    return this.#postCommand(`/api/v1/projects/${projectId}/egress-previews`, body, idempotencyKey, 262_144);
  }

  postProjectAITaskCreate(projectId: string, body: string, idempotencyKey: string): Promise<Response> {
    if (!identifier(projectId)) return Promise.reject(new SessionClientError("AUTH_CLIENT_UNAVAILABLE"));
    return this.#postCommand(`/api/v1/projects/${projectId}/ai-tasks`, body, idempotencyKey, 262_144);
  }

  /** Retrieval query is carried only in this one bounded POST body. */
  postProjectRAGRetrievalCreate(projectId: string, body: string, idempotencyKey: string): Promise<Response> {
    if (!identifier(projectId)) return Promise.reject(new SessionClientError("AUTH_CLIENT_UNAVAILABLE"));
    return this.#postCommand(`/api/v1/projects/${projectId}/retrieval-runs`, body, idempotencyKey, 32_768);
  }

  async postProjectAIEgressDecision(projectId: string, resourceId: string,
    action: "authorize" | "revoke", body: string, etag: string,
    idempotencyKey: string): Promise<Response> {
    if (this.#busy) throw new SessionClientError("AUTH_CLIENT_BUSY");
    if (this.#csrf === null || this.#view === null) throw new SessionClientError("AUTH_RELOGIN_REQUIRED");
    if (!identifier(projectId) || !identifier(resourceId)
      || typeof body !== "string" || body.length === 0
      || new TextEncoder().encode(body).length > 262_144
      || !/^"v(?:0|[1-9]\d*)"$/.test(etag)
      || !Number.isSafeInteger(Number(etag.slice(2, -1)))
      || typeof idempotencyKey !== "string" || !/^[\x20-\x7e]{16,128}$/.test(idempotencyKey)) {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    }
    this.#busy = true;
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const noun = action === "authorize" ? "egress-previews" : "egress-authorizations";
      const fetcher = this.fetcher;
      const response = await fetcher(`/api/v1/projects/${projectId}/${noun}/${resourceId}:${action}`, {
        method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error",
        headers: { Accept: "application/json", "Content-Type": "application/json",
          "X-CSRF-Token": this.#csrf, "Idempotency-Key": idempotencyKey,
          "If-Match": etag }, body, signal: controller.signal,
      });
      if (controller.signal.aborted) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
      if (response.status === 401) { this.#csrf = null; this.#view = null; }
      return response;
    } catch {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    } finally {
      window.clearTimeout(timer);
      this.#busy = false;
    }
  }

  /** Bounded single Content PUT. Blob gives Fetch a known length; scripts cannot set Content-Length. */
  async putProjectDocumentUploadContent(projectId: string, uploadId: string, proof: string,
    contentSha256: string, content: Blob): Promise<Response> {
    if (this.#busy) throw new SessionClientError("AUTH_CLIENT_BUSY");
    if (this.#csrf === null || this.#view === null) throw new SessionClientError("AUTH_RELOGIN_REQUIRED");
    if (!identifier(projectId) || !identifier(uploadId) || typeof proof !== "string"
      || !uploadToken.test(proof) || typeof contentSha256 !== "string" || !sha256.test(contentSha256)
      || !(content instanceof Blob) || !Number.isSafeInteger(content.size)
      || content.size < 1 || content.size > 100_000_000) {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    }
    this.#busy = true;
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 300_000);
    try {
      const fetcher = this.fetcher;
      const response = await fetcher(`/api/v1/projects/${projectId}/document-uploads/${uploadId}/content`, {
        method: "PUT", credentials: "same-origin", cache: "no-store", redirect: "error",
        headers: { Accept: "application/json", "Content-Type": "application/octet-stream",
          "X-CSRF-Token": this.#csrf, "X-Upload-Token": proof, "X-Content-SHA256": contentSha256 },
        body: content, signal: controller.signal,
      });
      if (controller.signal.aborted) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
      if (response.status === 401) { this.#csrf = null; this.#view = null; }
      return response;
    } catch {
      // Content can already have been received when the connection fails; never replay implicitly.
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    } finally {
      window.clearTimeout(timer);
      this.#busy = false;
    }
  }

  async #postProjectUploadFinalize(projectId: string, uploadId: string, action: "commit" | "abort",
    idempotencyKey: string, etag: string | null): Promise<Response> {
    if (this.#busy) throw new SessionClientError("AUTH_CLIENT_BUSY");
    if (this.#csrf === null || this.#view === null) throw new SessionClientError("AUTH_RELOGIN_REQUIRED");
    if (!identifier(projectId) || !identifier(uploadId)
      || typeof idempotencyKey !== "string" || !/^[\x20-\x7e]{16,128}$/.test(idempotencyKey)
      || (etag !== null && (action !== "commit" || !/^"v(?:0|[1-9]\d*)"$/.test(etag)
        || !Number.isSafeInteger(Number(etag.slice(2, -1)))
        || Number(etag.slice(2, -1)) >= Number.MAX_SAFE_INTEGER))) {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    }
    this.#busy = true;
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 60_000);
    try {
      const headers: Record<string, string> = { Accept: "application/json", "X-CSRF-Token": this.#csrf,
        "Idempotency-Key": idempotencyKey };
      if (etag !== null) headers["If-Match"] = etag;
      const fetcher = this.fetcher;
      const response = await fetcher(`/api/v1/projects/${projectId}/document-uploads/${uploadId}:${action}`, {
        method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error",
        headers, signal: controller.signal,
      });
      if (controller.signal.aborted) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
      if (response.status === 401) { this.#csrf = null; this.#view = null; }
      return response;
    } catch {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    } finally {
      window.clearTimeout(timer);
      this.#busy = false;
    }
  }

  postProjectDocumentUploadCommit(projectId: string, uploadId: string,
    idempotencyKey: string, parentEtag: string | null = null): Promise<Response> {
    return this.#postProjectUploadFinalize(projectId, uploadId, "commit", idempotencyKey, parentEtag);
  }

  postProjectDocumentUploadAbort(projectId: string, uploadId: string,
    idempotencyKey: string): Promise<Response> {
    return this.#postProjectUploadFinalize(projectId, uploadId, "abort", idempotencyKey, null);
  }

  /** Project PATCH has no idempotency key; an unknown outcome requires a fresh GET. */
  async patchProject(projectId: string, etag: string, body: string): Promise<Response> {
    if (this.#busy) throw new SessionClientError("AUTH_CLIENT_BUSY");
    if (this.#csrf === null || this.#view === null) throw new SessionClientError("AUTH_RELOGIN_REQUIRED");
    if (!identifier(projectId) || typeof etag !== "string" || !/^"v(?:0|[1-9]\d*)"$/.test(etag)
      || !Number.isSafeInteger(Number(etag.slice(2, -1)))
      || Number(etag.slice(2, -1)) >= Number.MAX_SAFE_INTEGER
      || typeof body !== "string" || body.length === 0
      || new TextEncoder().encode(body).length > 8192) {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    }
    this.#busy = true;
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const fetcher = this.fetcher;
      const response = await fetcher(`/api/v1/projects/${projectId}`, {
        method: "PATCH", credentials: "same-origin", cache: "no-store", redirect: "error",
        headers: { Accept: "application/json", "Content-Type": "application/json",
          "X-CSRF-Token": this.#csrf, "If-Match": etag }, body, signal: controller.signal,
      });
      if (controller.signal.aborted) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
      if (response.status === 401) { this.#csrf = null; this.#view = null; }
      return response;
    } catch {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    } finally {
      window.clearTimeout(timer);
      this.#busy = false;
    }
  }

  /** Empty-body one-way archive; an uncertain result retains the original Key/If-Match. */
  async postProjectArchive(projectId: string, etag: string, idempotencyKey: string): Promise<Response> {
    if (this.#busy) throw new SessionClientError("AUTH_CLIENT_BUSY");
    if (this.#csrf === null || this.#view === null) throw new SessionClientError("AUTH_RELOGIN_REQUIRED");
    if (!identifier(projectId) || typeof etag !== "string" || !/^"v(?:0|[1-9]\d*)"$/.test(etag)
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
      const response = await fetcher(`/api/v1/projects/${projectId}:archive`, {
        method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error",
        headers: { Accept: "application/json", "X-CSRF-Token": this.#csrf,
          "Idempotency-Key": idempotencyKey, "If-Match": etag }, signal: controller.signal,
      });
      if (controller.signal.aborted) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
      if (response.status === 401) { this.#csrf = null; this.#view = null; }
      return response;
    } catch {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    } finally {
      window.clearTimeout(timer);
      this.#busy = false;
    }
  }

  /** Workflow START only accepts the original v0 read and Key; never retries an uncertain result. */
  async postProjectWorkflowStart(projectId: string, etag: string,
    idempotencyKey: string): Promise<Response> {
    if (this.#busy) throw new SessionClientError("AUTH_CLIENT_BUSY");
    if (this.#csrf === null || this.#view === null) throw new SessionClientError("AUTH_RELOGIN_REQUIRED");
    if (!identifier(projectId) || etag !== '"v0"'
      || typeof idempotencyKey !== "string" || !/^[\x20-\x7e]{16,128}$/.test(idempotencyKey)) {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    }
    this.#busy = true;
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const fetcher = this.fetcher;
      const response = await fetcher(`/api/v1/projects/${projectId}/workflow:start`, {
        method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error",
        headers: { Accept: "application/json", "X-CSRF-Token": this.#csrf,
          "Idempotency-Key": idempotencyKey, "If-Match": etag }, signal: controller.signal,
      });
      if (controller.signal.aborted) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
      if (response.status === 401) { this.#csrf = null; this.#view = null; }
      return response;
    } catch {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    } finally {
      window.clearTimeout(timer);
      this.#busy = false;
    }
  }

  /** Project Job cancellation: one request only; the receipt is not current Job state proof. */
  async postProjectJobCancel(projectId: string, jobId: string, etag: string,
    idempotencyKey: string, reason: string): Promise<Response> {
    if (this.#busy) throw new SessionClientError("AUTH_CLIENT_BUSY");
    if (this.#csrf === null || this.#view === null) throw new SessionClientError("AUTH_RELOGIN_REQUIRED");
    const normalizedReason = typeof reason === "string" ? reason.trim() : "";
    if (!identifier(projectId) || !identifier(jobId)
      || typeof etag !== "string" || !/^"v(?:0|[1-9]\d*)"$/.test(etag)
      || !Number.isSafeInteger(Number(etag.slice(2, -1)))
      || Number(etag.slice(2, -1)) >= Number.MAX_SAFE_INTEGER
      || typeof idempotencyKey !== "string" || !/^[\x20-\x7e]{16,128}$/.test(idempotencyKey)
      || normalizedReason.length < 1 || normalizedReason.length > 1024
      || /\p{C}/u.test(normalizedReason)) {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    }
    const body = JSON.stringify({ reason: normalizedReason });
    if (new TextEncoder().encode(body).length > 8192) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    this.#busy = true;
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const fetcher = this.fetcher;
      const response = await fetcher(`/api/v1/projects/${projectId}/jobs/${jobId}:cancel`, {
        method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error",
        headers: { Accept: "application/json", "Content-Type": "application/json",
          "X-CSRF-Token": this.#csrf, "Idempotency-Key": idempotencyKey, "If-Match": etag },
        body, signal: controller.signal,
      });
      if (controller.signal.aborted) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
      if (response.status === 401) { this.#csrf = null; this.#view = null; }
      return response;
    } catch {
      // An uncertain cancellation may already be committed; retain original Key/ETag with the caller.
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    } finally {
      window.clearTimeout(timer);
      this.#busy = false;
    }
  }

  /** Retrieval alias cancellation uses its Run version and never retries implicitly. */
  async postProjectRAGRetrievalCancel(projectId: string, runId: string, etag: string,
    idempotencyKey: string, reason: string): Promise<Response> {
    if (this.#busy) throw new SessionClientError("AUTH_CLIENT_BUSY");
    if (this.#csrf === null || this.#view === null) throw new SessionClientError("AUTH_RELOGIN_REQUIRED");
    const normalizedReason = typeof reason === "string" ? reason.trim() : "";
    if (!identifier(projectId) || !identifier(runId)
      || typeof etag !== "string" || !/^"v(?:0|[1-9]\d*)"$/.test(etag)
      || !Number.isSafeInteger(Number(etag.slice(2, -1)))
      || Number(etag.slice(2, -1)) >= Number.MAX_SAFE_INTEGER
      || typeof idempotencyKey !== "string" || !/^[\x20-\x7e]{16,128}$/.test(idempotencyKey)
      || normalizedReason.length < 1 || normalizedReason.length > 1024
      || /\p{C}/u.test(normalizedReason)) {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    }
    const body = JSON.stringify({ reason: normalizedReason });
    this.#busy = true;
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const fetcher = this.fetcher;
      const response = await fetcher(`/api/v1/projects/${projectId}/retrieval-runs/${runId}:cancel`, {
        method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error",
        headers: { Accept: "application/json", "Content-Type": "application/json",
          "X-CSRF-Token": this.#csrf, "Idempotency-Key": idempotencyKey, "If-Match": etag },
        body, signal: controller.signal,
      });
      if (controller.signal.aborted) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
      if (response.status === 401) { this.#csrf = null; this.#view = null; }
      return response;
    } catch {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    } finally {
      window.clearTimeout(timer);
      this.#busy = false;
    }
  }

  async postProjectMemberCreate(projectId: string, body: string, idempotencyKey: string): Promise<Response> {
    if (!identifier(projectId)) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    return this.#postCommand(`/api/v1/projects/${projectId}/members`, body, idempotencyKey, 8192);
  }

  async postProjectDepartmentCreate(projectId: string, body: string, idempotencyKey: string): Promise<Response> {
    if (!identifier(projectId)) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    return this.#postCommand(`/api/v1/projects/${projectId}/departments`, body, idempotencyKey, 8192);
  }

  /** Exact candidate lookup consumes a durable rate bucket; never retry automatically. */
  async resolveProjectMemberCandidate(projectId: string, body: string): Promise<Response> {
    if (this.#busy) throw new SessionClientError("AUTH_CLIENT_BUSY");
    if (this.#csrf === null || this.#view === null) throw new SessionClientError("AUTH_RELOGIN_REQUIRED");
    if (!identifier(projectId) || typeof body !== "string" || body.length === 0
      || new TextEncoder().encode(body).length > 1024) {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    }
    this.#busy = true;
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const fetcher = this.fetcher;
      const response = await fetcher(`/api/v1/projects/${projectId}/member-candidates:resolve`, {
        method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error",
        headers: { Accept: "application/json", "Content-Type": "application/json",
          "X-CSRF-Token": this.#csrf }, body, signal: controller.signal,
      });
      if (controller.signal.aborted) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
      if (response.status === 401) { this.#csrf = null; this.#view = null; }
      return response;
    } catch {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    } finally {
      window.clearTimeout(timer);
      this.#busy = false;
    }
  }

  /** A member PATCH has no idempotency key; unknown outcomes require a fresh server read. */
  async patchProjectMember(projectId: string, memberId: string, etag: string,
    body: string): Promise<Response> {
    if (this.#busy) throw new SessionClientError("AUTH_CLIENT_BUSY");
    if (this.#csrf === null || this.#view === null) throw new SessionClientError("AUTH_RELOGIN_REQUIRED");
    if (!identifier(projectId) || !identifier(memberId)
      || typeof etag !== "string" || !/^"v(0|[1-9]\d*)"$/.test(etag)
      || !Number.isSafeInteger(Number(etag.slice(2, -1)))
      || Number(etag.slice(2, -1)) >= Number.MAX_SAFE_INTEGER
      || typeof body !== "string" || body.length === 0
      || new TextEncoder().encode(body).length > 8192) {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    }
    this.#busy = true;
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const fetcher = this.fetcher;
      const response = await fetcher(`/api/v1/projects/${projectId}/members/${memberId}`, {
        method: "PATCH", credentials: "same-origin", cache: "no-store", redirect: "error",
        headers: { Accept: "application/json", "Content-Type": "application/json",
          "X-CSRF-Token": this.#csrf, "If-Match": etag }, body, signal: controller.signal,
      });
      if (controller.signal.aborted) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
      if (response.status === 401) { this.#csrf = null; this.#view = null; }
      return response;
    } catch {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    } finally {
      window.clearTimeout(timer);
      this.#busy = false;
    }
  }

  /** Department PATCH has no idempotency key; an unknown result requires a fresh GET. */
  async patchProjectDepartment(projectId: string, departmentId: string, etag: string,
    body: string): Promise<Response> {
    if (this.#busy) throw new SessionClientError("AUTH_CLIENT_BUSY");
    if (this.#csrf === null || this.#view === null) throw new SessionClientError("AUTH_RELOGIN_REQUIRED");
    if (!identifier(projectId) || !identifier(departmentId)
      || typeof etag !== "string" || !/^"v(?:0|[1-9]\d*)"$/.test(etag)
      || !Number.isSafeInteger(Number(etag.slice(2, -1)))
      || Number(etag.slice(2, -1)) >= Number.MAX_SAFE_INTEGER
      || typeof body !== "string" || body.length === 0
      || new TextEncoder().encode(body).length > 8192) {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    }
    this.#busy = true;
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const fetcher = this.fetcher;
      const response = await fetcher(`/api/v1/projects/${projectId}/departments/${departmentId}`, {
        method: "PATCH", credentials: "same-origin", cache: "no-store", redirect: "error",
        headers: { Accept: "application/json", "Content-Type": "application/json",
          "X-CSRF-Token": this.#csrf, "If-Match": etag }, body, signal: controller.signal,
      });
      if (controller.signal.aborted) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
      if (response.status === 401) { this.#csrf = null; this.#view = null; }
      return response;
    } catch {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    } finally {
      window.clearTimeout(timer);
      this.#busy = false;
    }
  }

  /** Empty-body department deactivation; an uncertain result retains the original Key/If-Match. */
  async postProjectDepartmentDeactivate(projectId: string, departmentId: string,
    etag: string, idempotencyKey: string): Promise<Response> {
    if (this.#busy) throw new SessionClientError("AUTH_CLIENT_BUSY");
    if (this.#csrf === null || this.#view === null) throw new SessionClientError("AUTH_RELOGIN_REQUIRED");
    if (!identifier(projectId) || !identifier(departmentId)
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
      const response = await fetcher(`/api/v1/projects/${projectId}/departments/${departmentId}:deactivate`, {
        method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error",
        headers: { Accept: "application/json", "X-CSRF-Token": this.#csrf,
          "Idempotency-Key": idempotencyKey, "If-Match": etag }, signal: controller.signal,
      });
      if (controller.signal.aborted) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
      if (response.status === 401) { this.#csrf = null; this.#view = null; }
      return response;
    } catch {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    } finally {
      window.clearTimeout(timer);
      this.#busy = false;
    }
  }

  /** Empty-body member state command; caller retains the original Key/If-Match on uncertain outcome. */
  async postProjectMemberState(projectId: string, memberId: string,
    action: "suspend" | "resume" | "remove", etag: string, idempotencyKey: string): Promise<Response> {
    if (this.#busy) throw new SessionClientError("AUTH_CLIENT_BUSY");
    if (this.#csrf === null || this.#view === null) throw new SessionClientError("AUTH_RELOGIN_REQUIRED");
    if (!identifier(projectId) || !identifier(memberId)
      || (action !== "suspend" && action !== "resume" && action !== "remove")
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
      const response = await fetcher(`/api/v1/projects/${projectId}/members/${memberId}:${action}`, {
        method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error",
        headers: { Accept: "application/json", "X-CSRF-Token": this.#csrf,
          "Idempotency-Key": idempotencyKey, "If-Match": etag }, signal: controller.signal,
      });
      if (controller.signal.aborted) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
      if (response.status === 401) { this.#csrf = null; this.#view = null; }
      return response;
    } catch {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    } finally {
      window.clearTimeout(timer);
      this.#busy = false;
    }
  }

  /** Human Evidence first decision; caller retains Key and ETag if the result is uncertain. */
  async postEvidenceEligibility(projectId: string, evidenceId: string, etag: string,
    idempotencyKey: string, body: string): Promise<Response> {
    if (this.#busy) throw new SessionClientError("AUTH_CLIENT_BUSY");
    if (this.#csrf === null || this.#view === null) throw new SessionClientError("AUTH_RELOGIN_REQUIRED");
    if (!identifier(projectId) || !identifier(evidenceId)
      || typeof etag !== "string" || !/^"v(?:0|[1-9]\d*)"$/.test(etag)
      || !Number.isSafeInteger(Number(etag.slice(2, -1)))
      || Number(etag.slice(2, -1)) >= Number.MAX_SAFE_INTEGER
      || typeof idempotencyKey !== "string" || !/^[\x20-\x7e]{16,128}$/.test(idempotencyKey)
      || typeof body !== "string" || body.length === 0
      || new TextEncoder().encode(body).length > 8192) {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    }
    this.#busy = true;
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const response = await this.fetcher(
        `/api/v1/projects/${projectId}/evidence/${evidenceId}:set-eligibility`, {
          method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error",
          headers: { Accept: "application/json", "Content-Type": "application/json",
            "X-CSRF-Token": this.#csrf, "Idempotency-Key": idempotencyKey,
            "If-Match": etag }, body, signal: controller.signal,
        });
      if (controller.signal.aborted) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
      if (response.status === 401) { this.#csrf = null; this.#view = null; }
      return response;
    } catch {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    } finally {
      window.clearTimeout(timer);
      this.#busy = false;
    }
  }

  /** Global-admin human Evidence decision; caller retains the original Key on uncertainty. */
  async postGlobalEvidenceEligibility(evidenceId: string, etag: string,
    idempotencyKey: string, body: string): Promise<Response> {
    if (this.#busy) throw new SessionClientError("AUTH_CLIENT_BUSY");
    if (this.#csrf === null || this.#view === null) throw new SessionClientError("AUTH_RELOGIN_REQUIRED");
    if (!identifier(evidenceId) || typeof etag !== "string"
      || !/^"v(?:0|[1-9]\d*)"$/.test(etag)
      || !Number.isSafeInteger(Number(etag.slice(2, -1)))
      || Number(etag.slice(2, -1)) >= Number.MAX_SAFE_INTEGER
      || typeof idempotencyKey !== "string" || !/^[\x20-\x7e]{16,128}$/.test(idempotencyKey)
      || typeof body !== "string" || body.length === 0
      || new TextEncoder().encode(body).length > 8192) {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    }
    this.#busy = true;
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const response = await this.fetcher(`/api/v1/global/evidence/${evidenceId}:set-eligibility`, {
        method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error",
        headers: { Accept: "application/json", "Content-Type": "application/json",
          "X-CSRF-Token": this.#csrf, "Idempotency-Key": idempotencyKey,
          "If-Match": etag }, body, signal: controller.signal,
      });
      if (controller.signal.aborted) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
      if (response.status === 401) { this.#csrf = null; this.#view = null; }
      return response;
    } catch {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    } finally { window.clearTimeout(timer); this.#busy = false; }
  }

  /** Read-only receipt lookup; the original operation key is confined to the JSON body. */
  async postEvidenceEligibilityOperationLookup(projectId: string, evidenceId: string,
    operationKey: string): Promise<Response> {
    if (this.#busy) throw new SessionClientError("AUTH_CLIENT_BUSY");
    if (this.#csrf === null || this.#view === null) throw new SessionClientError("AUTH_RELOGIN_REQUIRED");
    if (!identifier(projectId) || !identifier(evidenceId)
      || typeof operationKey !== "string" || !/^[\x20-\x7e]{16,128}$/.test(operationKey)) {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    }
    this.#busy = true;
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const response = await this.fetcher(
        `/api/v1/projects/${projectId}/evidence/${evidenceId}:lookup-eligibility-operation`, {
          method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error",
          headers: { Accept: "application/json", "Content-Type": "application/json",
            "X-CSRF-Token": this.#csrf },
          body: JSON.stringify({ operation_key: operationKey }), signal: controller.signal,
        });
      if (controller.signal.aborted) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
      if (response.status === 401) { this.#csrf = null; this.#view = null; }
      return response;
    } catch {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    } finally {
      window.clearTimeout(timer);
      this.#busy = false;
    }
  }

  /** Global-admin variant of the read-only receipt lookup. */
  async postGlobalEvidenceEligibilityOperationLookup(evidenceId: string,
    operationKey: string): Promise<Response> {
    if (this.#busy) throw new SessionClientError("AUTH_CLIENT_BUSY");
    if (this.#csrf === null || this.#view === null) throw new SessionClientError("AUTH_RELOGIN_REQUIRED");
    if (!identifier(evidenceId) || typeof operationKey !== "string"
      || !/^[\x20-\x7e]{16,128}$/.test(operationKey)) {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    }
    this.#busy = true;
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const response = await this.fetcher(
        `/api/v1/global/evidence/${evidenceId}:lookup-eligibility-operation`, {
          method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error",
          headers: { Accept: "application/json", "Content-Type": "application/json",
            "X-CSRF-Token": this.#csrf },
          body: JSON.stringify({ operation_key: operationKey }), signal: controller.signal,
        });
      if (controller.signal.aborted) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
      if (response.status === 401) { this.#csrf = null; this.#view = null; }
      return response;
    } catch {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    } finally {
      window.clearTimeout(timer);
      this.#busy = false;
    }
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
