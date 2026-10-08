/** Same-origin Auth transport. Views are hints, never authorization capabilities. */
export interface SessionView {
  readonly user: Readonly<{ user_id: string; username_display: string }>;
  readonly deployment_role: "NONE" | "DEPLOYMENT_ADMIN";
  readonly password_change_required: boolean;
  readonly authorized_projects: readonly Readonly<{ project_id: string; name: string; role: string }>[];
  readonly absolute_expires_at: string;
  readonly idle_expires_at: string;
}

export type PrototypeWriteRoute =
  | { readonly operation: "package-create"; readonly projectId: string }
  | { readonly operation: "package-patch" | "package-set-members"; readonly projectId: string; readonly packageId: string }
  | { readonly operation: "prototype-create"; readonly projectId: string }
  | { readonly operation: "prototype-patch" | "prototype-mark-not-required" | "prototype-archive";
      readonly projectId: string; readonly prototypeId: string }
  | { readonly operation: "version-create"; readonly projectId: string; readonly prototypeId: string }
  | { readonly operation: "version-validate" | "version-submit-review"; readonly projectId: string;
      readonly prototypeId: string; readonly versionId: string }
  | { readonly operation: "template-project-create"; readonly projectId: string }
  | { readonly operation: "template-project-revise"; readonly projectId: string; readonly templateId: string }
  | { readonly operation: "template-global-create" }
  | { readonly operation: "template-global-revise"; readonly templateId: string }
  | { readonly operation: "link-create"; readonly projectId: string }
  | { readonly operation: "link-revoke" | "link-supersede"; readonly projectId: string; readonly linkId: string };

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
  #revision = 0;
  readonly #listeners = new Set<() => void>();
  constructor(private readonly fetcher: typeof fetch = fetch, private readonly timeoutMs = 10_000) {
    if (!Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 30_000) {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    }
  }
  get view(): SessionView | null { return this.#view; }
  get canSubmit(): boolean { return this.#csrf !== null && !this.#busy; }
  get revision(): number { return this.#revision; }
  subscribe(listener: () => void): () => void {
    if (typeof listener !== "function") throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    this.#listeners.add(listener); return () => { this.#listeners.delete(listener); };
  }
  #changed() {
    this.#revision += 1;
    for (const listener of [...this.#listeners]) { try { listener(); } catch { /* UI observers cannot alter auth state. */ } }
  }

  async #exclusive<T>(action: (token: string | null) => Promise<T>): Promise<T> {
    if (this.#busy) throw new SessionClientError("AUTH_CLIENT_BUSY");
    this.#busy = true;
    const token = this.#csrf;
    this.#csrf = null;
    this.#view = null;
    this.#changed();
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
    this.#changed();
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

  /** Checklist writes are single attempts; callers retain the original body, Key and ETag after uncertainty. */
  async postProjectWorkflowChecklistRecord(projectId: string,
    itemKey: "HANDOVER_BASELINE" | "HANDOVER_ISSUES"
      | "SURVEY_ACTUAL_SOURCES" | "SURVEY_CONCLUSION"
      | "REQUIREMENT_FORMAL_VERSIONS" | "REQUIREMENT_ACCEPTANCE"
      | "PROTOTYPE_SCOPE_DECISIONS" | "PROTOTYPE_COVERAGE", body: string,
    etag: string, idempotencyKey: string): Promise<Response> {
    if (this.#busy) throw new SessionClientError("AUTH_CLIENT_BUSY");
    if (this.#csrf === null || this.#view === null) throw new SessionClientError("AUTH_RELOGIN_REQUIRED");
    const version = typeof etag === "string" && /^"v[1-9]\d*"$/.test(etag)
      ? Number(etag.slice(2, -1)) : null;
    if (!identifier(projectId)
      || !["HANDOVER_BASELINE", "HANDOVER_ISSUES",
        "SURVEY_ACTUAL_SOURCES", "SURVEY_CONCLUSION",
        "REQUIREMENT_FORMAL_VERSIONS", "REQUIREMENT_ACCEPTANCE",
        "PROTOTYPE_SCOPE_DECISIONS", "PROTOTYPE_COVERAGE"].includes(itemKey)
      || typeof body !== "string" || body.length === 0
      || new TextEncoder().encode(body).length > 2 * 1024 * 1024
      || !Number.isSafeInteger(version) || version === null || version >= Number.MAX_SAFE_INTEGER
      || typeof idempotencyKey !== "string" || !/^[\x20-\x7e]{16,128}$/.test(idempotencyKey)) {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    }
    this.#busy = true;
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const fetcher = this.fetcher;
      const response = await fetcher(
        `/api/v1/projects/${projectId}/workflow/checklist-items/${itemKey}:record`, {
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

  /** Stage Transition is a single attempt; callers retain the original body, Key and ETag after uncertainty. */
  async postProjectWorkflowTransition(projectId: string, body: string,
    etag: string, idempotencyKey: string): Promise<Response> {
    if (this.#busy) throw new SessionClientError("AUTH_CLIENT_BUSY");
    if (this.#csrf === null || this.#view === null) throw new SessionClientError("AUTH_RELOGIN_REQUIRED");
    const version = typeof etag === "string" && /^"v[1-9]\d*"$/.test(etag)
      ? Number(etag.slice(2, -1)) : null;
    if (!identifier(projectId) || typeof body !== "string" || body.length === 0
      || new TextEncoder().encode(body).length > 8192
      || !Number.isSafeInteger(version) || version === null || version >= Number.MAX_SAFE_INTEGER
      || typeof idempotencyKey !== "string" || !/^[\x20-\x7e]{16,128}$/.test(idempotencyKey)) {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    }
    this.#busy = true;
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const fetcher = this.fetcher;
      const response = await fetcher(`/api/v1/projects/${projectId}/workflow:transition`, {
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

  /** Handover Action writes: the caller retains the original body, Key and ETag after uncertainty. */
  async #writeProjectHandoverAction(projectId: string, actionId: string | null,
    method: "POST" | "PATCH", operation: "create" | "patch" | "start" | "submit" | "verify" | "close" | "cancel",
    body: string, etag: string | null, idempotencyKey: string | null): Promise<Response> {
    if (this.#busy) throw new SessionClientError("AUTH_CLIENT_BUSY");
    if (this.#csrf === null || this.#view === null) throw new SessionClientError("AUTH_RELOGIN_REQUIRED");
    const version = etag === null ? null : /^"v(?:0|[1-9]\d*)"$/.test(etag) ? Number(etag.slice(2, -1)) : null;
    if (!identifier(projectId) || (operation === "create") !== (actionId === null)
      || actionId !== null && !identifier(actionId)
      || typeof body !== "string" || body.length === 0 || new TextEncoder().encode(body).length > 2 * 1024 * 1024
      || (operation === "create") !== (etag === null)
      || etag !== null && (!Number.isSafeInteger(version) || version === null || version >= Number.MAX_SAFE_INTEGER)
      || (operation === "patch") !== (idempotencyKey === null)
      || idempotencyKey !== null && !/^[\x20-\x7e]{16,128}$/.test(idempotencyKey)
      || operation === "patch" && method !== "PATCH" || operation !== "patch" && method !== "POST") {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    }
    const base = `/api/v1/projects/${projectId}/handover-action-items`;
    const path = operation === "create" ? base
      : operation === "patch" ? `${base}/${actionId}` : `${base}/${actionId}:${operation}`;
    const headers: Record<string, string> = { Accept: "application/json", "Content-Type": "application/json",
      "X-CSRF-Token": this.#csrf };
    if (etag !== null) headers["If-Match"] = etag;
    if (idempotencyKey !== null) headers["Idempotency-Key"] = idempotencyKey;
    this.#busy = true;
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const fetcher = this.fetcher;
      const response = await fetcher(path, { method, credentials: "same-origin", cache: "no-store",
        redirect: "error", headers, body, signal: controller.signal });
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

  postProjectHandoverActionCreate(projectId: string, body: string, idempotencyKey: string): Promise<Response> {
    return this.#writeProjectHandoverAction(projectId, null, "POST", "create", body, null, idempotencyKey);
  }

  patchProjectHandoverAction(projectId: string, actionId: string, etag: string, body: string): Promise<Response> {
    return this.#writeProjectHandoverAction(projectId, actionId, "PATCH", "patch", body, etag, null);
  }

  postProjectHandoverActionTransition(projectId: string, actionId: string,
    operation: "start" | "submit" | "verify" | "close" | "cancel", etag: string,
    idempotencyKey: string, body: string): Promise<Response> {
    return this.#writeProjectHandoverAction(projectId, actionId, "POST", operation, body, etag, idempotencyKey);
  }

  /** Survey Round writes retain the caller's original body, Key and ETag after uncertainty. */
  async writeProjectSurveyRound(projectId: string, roundId: string | null,
    method: "POST" | "PATCH", operation: "create" | "patch" | "open" | "close" | "cancel",
    body: string | null, etag: string | null, idempotencyKey: string | null): Promise<Response> {
    if (this.#busy) throw new SessionClientError("AUTH_CLIENT_BUSY");
    if (this.#csrf === null || this.#view === null) throw new SessionClientError("AUTH_RELOGIN_REQUIRED");
    const version = etag === null ? null : /^"v(?:0|[1-9]\d*)"$/.test(etag) ? Number(etag.slice(2, -1)) : null;
    const hasBody = operation === "create" || operation === "patch" || operation === "cancel";
    const needsKey = operation !== "patch";
    if (!identifier(projectId) || (operation === "create") !== (roundId === null)
      || roundId !== null && !identifier(roundId)
      || hasBody !== (body !== null) || body !== null && (body.length === 0 || new TextEncoder().encode(body).length > 8192)
      || (operation === "create") !== (etag === null)
      || etag !== null && (!Number.isSafeInteger(version) || version === null || version >= Number.MAX_SAFE_INTEGER)
      || needsKey !== (idempotencyKey !== null)
      || idempotencyKey !== null && !/^[\x20-\x7e]{16,128}$/.test(idempotencyKey)
      || operation === "patch" && method !== "PATCH" || operation !== "patch" && method !== "POST") {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    }
    const base = `/api/v1/projects/${projectId}/survey-rounds`;
    const path = operation === "create" ? base : operation === "patch" ? `${base}/${roundId}` : `${base}/${roundId}:${operation}`;
    const headers: Record<string, string> = { Accept: "application/json", "X-CSRF-Token": this.#csrf };
    if (body !== null) headers["Content-Type"] = "application/json";
    if (etag !== null) headers["If-Match"] = etag;
    if (idempotencyKey !== null) headers["Idempotency-Key"] = idempotencyKey;
    this.#busy = true;
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      // Native Window.fetch rejects a SessionClient receiver; detach it before invocation.
      const fetcher = this.fetcher;
      const response = await fetcher(path, { method, credentials: "same-origin", cache: "no-store",
        redirect: "error", headers, ...(body === null ? {} : { body }), signal: controller.signal });
      if (controller.signal.aborted) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
      if (response.status === 401) { this.#csrf = null; this.#view = null; }
      return response;
    } catch {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    } finally {
      window.clearTimeout(timer); this.#busy = false;
    }
  }

  /** Assignment writes are single attempts; callers retain body, Key and ETag after uncertainty. */
  async writeProjectSurveyAssignment(projectId: string, roundId: string,
    assignmentId: string | null,
    operation: "create" | "response" | "submit" | "validate" | "return",
    body: string | null, etag: string | null, idempotencyKey: string): Promise<Response> {
    if (this.#busy) throw new SessionClientError("AUTH_CLIENT_BUSY");
    if (this.#csrf === null || this.#view === null) throw new SessionClientError("AUTH_RELOGIN_REQUIRED");
    const version = etag === null ? null : /^"v(?:0|[1-9]\d*)"$/.test(etag)
      ? Number(etag.slice(2, -1)) : null;
    const hasBody = operation === "create" || operation === "response" || operation === "return";
    if (!identifier(projectId) || !identifier(roundId)
      || (operation === "create") !== (assignmentId === null)
      || assignmentId !== null && !identifier(assignmentId)
      || hasBody !== (body !== null)
      || body !== null && (body.length === 0 || new TextEncoder().encode(body).length > 2 * 1024 * 1024)
      || (operation === "create") !== (etag === null)
      || etag !== null && (!Number.isSafeInteger(version) || version === null || version >= Number.MAX_SAFE_INTEGER)
      || typeof idempotencyKey !== "string" || !/^[\x20-\x7e]{16,128}$/.test(idempotencyKey)) {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    }
    const root = `/api/v1/projects/${projectId}/survey-rounds/${roundId}/assignments`;
    const path = operation === "create" ? root : operation === "response"
      ? `${root}/${assignmentId}/responses` : `${root}/${assignmentId}:${operation}`;
    const headers: Record<string, string> = { Accept: "application/json",
      "X-CSRF-Token": this.#csrf, "Idempotency-Key": idempotencyKey };
    if (body !== null) headers["Content-Type"] = "application/json";
    if (etag !== null) headers["If-Match"] = etag;
    this.#busy = true;
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const fetcher = this.fetcher;
      const response = await fetcher(path, { method: "POST", credentials: "same-origin",
        cache: "no-store", redirect: "error", headers,
        ...(body === null ? {} : { body }), signal: controller.signal });
      if (controller.signal.aborted) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
      if (response.status === 401) { this.#csrf = null; this.#view = null; }
      return response;
    } catch {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    } finally { window.clearTimeout(timer); this.#busy = false; }
  }

  /** Conclusion writes are single attempts; callers retain the exact body and Key after uncertainty. */
  async writeProjectSurveyConclusion(projectId: string, conclusionId: string | null,
    operation: "create" | "validate" | "submit-review", body: string | null,
    idempotencyKey: string): Promise<Response> {
    if (this.#busy) throw new SessionClientError("AUTH_CLIENT_BUSY");
    if (this.#csrf === null || this.#view === null) throw new SessionClientError("AUTH_RELOGIN_REQUIRED");
    const hasBody = operation === "create" || operation === "submit-review";
    if (!(["create", "validate", "submit-review"] as const).includes(operation)
      || !identifier(projectId) || (operation === "create") !== (conclusionId === null)
      || conclusionId !== null && !identifier(conclusionId)
      || hasBody !== (body !== null)
      || body !== null && (body.length === 0 || new TextEncoder().encode(body).length > 2 * 1024 * 1024)
      || typeof idempotencyKey !== "string" || !/^[\x20-\x7e]{16,128}$/.test(idempotencyKey)) {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    }
    const root = `/api/v1/projects/${projectId}/survey-conclusions`;
    const path = operation === "create" ? root : `${root}/${conclusionId}:${operation}`;
    const headers: Record<string, string> = { Accept: "application/json",
      "X-CSRF-Token": this.#csrf, "Idempotency-Key": idempotencyKey };
    if (body !== null) headers["Content-Type"] = "application/json";
    this.#busy = true;
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const fetcher = this.fetcher;
      const response = await fetcher(path, { method: "POST", credentials: "same-origin",
        cache: "no-store", redirect: "error", headers,
        ...(body === null ? {} : { body }), signal: controller.signal });
      if (controller.signal.aborted) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
      if (response.status === 401) { this.#csrf = null; this.#view = null; }
      return response;
    } catch {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    } finally { window.clearTimeout(timer); this.#busy = false; }
  }

  /** Requirement Version writes retain the exact body, Key and root ETag after uncertainty. */
  async writeProjectRequirementVersion(projectId: string, requirementId: string,
    versionId: string | null, operation: "create" | "validate" | "submit-review",
    body: string | null, etag: string | null, idempotencyKey: string): Promise<Response> {
    if (this.#busy) throw new SessionClientError("AUTH_CLIENT_BUSY");
    if (this.#csrf === null || this.#view === null) throw new SessionClientError("AUTH_RELOGIN_REQUIRED");
    const hasBody = operation === "create" || operation === "submit-review";
    const version = etag === null ? null : /^"v(?:0|[1-9]\d*)"$/.test(etag) ? Number(etag.slice(2, -1)) : null;
    if (!identifier(projectId) || !identifier(requirementId)
      || (operation === "create") !== (versionId === null) || versionId !== null && !identifier(versionId)
      || hasBody !== (body !== null) || body !== null && (body.length === 0 || new TextEncoder().encode(body).length > 2 * 1024 * 1024)
      || (operation === "create") !== (etag !== null)
      || etag !== null && (!Number.isSafeInteger(version) || version === null || version >= Number.MAX_SAFE_INTEGER)
      || typeof idempotencyKey !== "string" || !/^[\x20-\x7e]{16,128}$/.test(idempotencyKey)) {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    }
    const root = `/api/v1/projects/${projectId}/requirements/${requirementId}/versions`;
    const path = operation === "create" ? root : `${root}/${versionId}:${operation}`;
    const headers: Record<string, string> = { Accept: "application/json", "X-CSRF-Token": this.#csrf,
      "Idempotency-Key": idempotencyKey };
    if (body !== null) headers["Content-Type"] = "application/json";
    if (etag !== null) headers["If-Match"] = etag;
    this.#busy = true; const controller = new AbortController(); const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const fetcher = this.fetcher; const response = await fetcher(path, { method: "POST", credentials: "same-origin",
        cache: "no-store", redirect: "error", headers, ...(body === null ? {} : { body }), signal: controller.signal });
      if (controller.signal.aborted) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
      if (response.status === 401) { this.#csrf = null; this.#view = null; }
      return response;
    } catch { throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE"); }
    finally { window.clearTimeout(timer); this.#busy = false; }
  }

  /** Frozen Prototype writes never retry implicitly; callers retain the exact body, Key and ETag after uncertainty. */
  async writePrototype(route: PrototypeWriteRoute, body: string | null,
    etag: string | null, idempotencyKey: string | null): Promise<Response> {
    if (this.#busy) throw new SessionClientError("AUTH_CLIENT_BUSY");
    if (this.#csrf === null || this.#view === null) throw new SessionClientError("AUTH_RELOGIN_REQUIRED");
    let path = "", method: "POST" | "PATCH" = "POST";
    let needsBody = true, needsEtag = false, needsKey = true;
    const project = "projectId" in route ? route.projectId : null;
    if (project !== null && !identifier(project)) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    switch (route.operation) {
      case "package-create": path = `/api/v1/projects/${route.projectId}/prototype-packages`; break;
      case "package-patch":
        if (!identifier(route.packageId)) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
        path = `/api/v1/projects/${route.projectId}/prototype-packages/${route.packageId}`;
        method = "PATCH"; needsEtag = true; needsKey = false; break;
      case "package-set-members":
        if (!identifier(route.packageId)) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
        path = `/api/v1/projects/${route.projectId}/prototype-packages/${route.packageId}:set-members`;
        needsEtag = true; break;
      case "prototype-create": path = `/api/v1/projects/${route.projectId}/prototypes`; break;
      case "prototype-patch":
        if (!identifier(route.prototypeId)) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
        path = `/api/v1/projects/${route.projectId}/prototypes/${route.prototypeId}`;
        method = "PATCH"; needsEtag = true; needsKey = false; break;
      case "prototype-mark-not-required":
        if (!identifier(route.prototypeId)) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
        path = `/api/v1/projects/${route.projectId}/prototypes/${route.prototypeId}:mark-not-required`;
        needsEtag = true; break;
      case "prototype-archive":
        if (!identifier(route.prototypeId)) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
        path = `/api/v1/projects/${route.projectId}/prototypes/${route.prototypeId}:archive`;
        needsBody = false; needsEtag = true; break;
      case "version-create":
        if (!identifier(route.prototypeId)) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
        path = `/api/v1/projects/${route.projectId}/prototypes/${route.prototypeId}/versions`;
        needsEtag = true; break;
      case "version-validate":
      case "version-submit-review":
        if (!identifier(route.prototypeId) || !identifier(route.versionId)) {
          throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
        }
        path = `/api/v1/projects/${route.projectId}/prototypes/${route.prototypeId}/versions/${route.versionId}`
          + (route.operation === "version-validate" ? ":validate" : ":submit-review");
        needsBody = route.operation === "version-submit-review"; break;
      case "template-project-create":
        path = `/api/v1/projects/${route.projectId}/prototype-templates`; break;
      case "template-project-revise":
        if (!identifier(route.templateId)) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
        path = `/api/v1/projects/${route.projectId}/prototype-templates/${route.templateId}:revise`;
        needsEtag = true; break;
      case "template-global-create": path = "/api/v1/global/prototype-templates"; break;
      case "template-global-revise":
        if (!identifier(route.templateId)) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
        path = `/api/v1/global/prototype-templates/${route.templateId}:revise`; needsEtag = true; break;
      case "link-create": path = `/api/v1/projects/${route.projectId}/prototype-requirement-links`; break;
      case "link-revoke":
      case "link-supersede":
        if (!identifier(route.linkId)) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
        path = `/api/v1/projects/${route.projectId}/prototype-requirement-links/${route.linkId}`
          + (route.operation === "link-revoke" ? ":revoke" : ":supersede");
        needsBody = route.operation === "link-supersede"; break;
    }
    const parsedVersion = etag === null ? null : /^"v(?:0|[1-9]\d*)"$/.test(etag) ? Number(etag.slice(2, -1)) : null;
    if ((body !== null) !== needsBody || body !== null && (body.length === 0
        || new TextEncoder().encode(body).length > 2 * 1024 * 1024)
      || (etag !== null) !== needsEtag || etag !== null && (parsedVersion === null
        || !Number.isSafeInteger(parsedVersion) || parsedVersion >= Number.MAX_SAFE_INTEGER)
      || (idempotencyKey !== null) !== needsKey || idempotencyKey !== null
        && !/^[\x20-\x7e]{16,128}$/.test(idempotencyKey)) {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    }
    const headers: Record<string, string> = { Accept: "application/json", "X-CSRF-Token": this.#csrf };
    if (body !== null) headers["Content-Type"] = "application/json";
    if (etag !== null) headers["If-Match"] = etag;
    if (idempotencyKey !== null) headers["Idempotency-Key"] = idempotencyKey;
    this.#busy = true; const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const fetcher = this.fetcher;
      const response = await fetcher(path, { method, credentials: "same-origin", cache: "no-store", redirect: "error",
        headers, ...(body === null ? {} : { body }), signal: controller.signal });
      if (controller.signal.aborted) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
      if (response.status === 401) { this.#csrf = null; this.#view = null; this.#changed(); }
      return response;
    } catch {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    } finally { window.clearTimeout(timer); this.#busy = false; }
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

  /** GLOBAL human deidentification workflow; CSRF remains private to this client. */
  async postGlobalReferenceDeidentificationPreview(body: string): Promise<Response> {
    return this.#postGlobalReferenceDeidentification("preview", body);
  }

  async postGlobalReferenceDeidentificationConfirm(body: string, idempotencyKey: string): Promise<Response> {
    return this.#postGlobalReferenceDeidentification("confirm", body, idempotencyKey);
  }

  async postGlobalReferenceDeidentificationRevoke(confirmationId: string, body: string,
    idempotencyKey: string): Promise<Response> {
    if (!identifier(confirmationId)) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    return this.#postGlobalReferenceDeidentification("revoke", body, idempotencyKey, confirmationId);
  }

  async postGlobalReferenceDeidentificationOperationLookup(body: string): Promise<Response> {
    return this.#postGlobalReferenceDeidentification("lookup", body);
  }

  /** GLOBAL Reference Create keeps the CSRF token private and never retries a write. */
  async postGlobalReferenceCreate(body: string, idempotencyKey: string): Promise<Response> {
    if (this.#busy) throw new SessionClientError("AUTH_CLIENT_BUSY");
    if (this.#csrf === null || this.#view === null) throw new SessionClientError("AUTH_RELOGIN_REQUIRED");
    if (typeof body !== "string" || !body || new TextEncoder().encode(body).length > 128 * 1024
      || typeof idempotencyKey !== "string" || !/^[\x20-\x7e]{16,128}$/.test(idempotencyKey)) {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    }
    this.#busy = true;
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const fetcher = this.fetcher;
      const response = await fetcher("/api/v1/global/reference-solutions", {
        method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error",
        headers: { Accept: "application/json", "Content-Type": "application/json",
          "X-CSRF-Token": this.#csrf, "Idempotency-Key": idempotencyKey },
        body, signal: controller.signal,
      });
      if (controller.signal.aborted) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
      if (response.status === 401) { this.#csrf = null; this.#view = null; }
      return response;
    } catch { throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE"); }
    finally { window.clearTimeout(timer); this.#busy = false; }
  }

  async #postGlobalReferenceDeidentification(action: "preview" | "confirm" | "revoke" | "lookup",
    body: string, idempotencyKey?: string, confirmationId?: string): Promise<Response> {
    if (this.#busy) throw new SessionClientError("AUTH_CLIENT_BUSY");
    if (this.#csrf === null || this.#view === null) throw new SessionClientError("AUTH_RELOGIN_REQUIRED");
    if (typeof body !== "string" || body.length === 0 || new TextEncoder().encode(body).length > 128 * 1024
      || ((action === "preview" || action === "lookup") && idempotencyKey !== undefined)
      || ((action === "confirm" || action === "revoke") && (typeof idempotencyKey !== "string"
        || !/^[\x20-\x7e]{16,128}$/.test(idempotencyKey)))) {
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    }
    const base = "/api/v1/global/reference-deidentification-confirmations";
    const path = action === "preview" ? `${base}:preview` : action === "lookup"
      ? `${base}:lookup-operation` : action === "confirm" ? base
        : `${base}/${confirmationId}:revoke`;
    this.#busy = true;
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      // Browser-native fetch must not inherit this SessionClient as its receiver.
      const fetcher = this.fetcher;
      const response = await fetcher(path, {
        method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error",
        headers: { Accept: "application/json", "Content-Type": "application/json",
          "X-CSRF-Token": this.#csrf, ...(idempotencyKey ? { "Idempotency-Key": idempotencyKey } : {}) },
        body, signal: controller.signal,
      });
      if (controller.signal.aborted) throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
      if (response.status === 401) { this.#csrf = null; this.#view = null; }
      return response;
    } catch {
      // A timed-out write may have committed; callers must preserve its operation key.
      throw new SessionClientError("AUTH_CLIENT_UNAVAILABLE");
    } finally { window.clearTimeout(timer); this.#busy = false; }
  }
}
