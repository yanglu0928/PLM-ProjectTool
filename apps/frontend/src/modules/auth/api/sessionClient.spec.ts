import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionClient, SessionClientError } from "./sessionClient";

const id = "01234567-89ab-4cde-8123-456789abcdef";
const projectId = "11234567-89ab-4cde-8123-456789abcdef";
const token = "a".repeat(64);
function session(extra: Record<string, unknown> = {}) {
  return { user: { user_id: id, username_display: "测试用户" }, deployment_role: "DEPLOYMENT_ADMIN",
    password_change_required: false, authorized_projects: [], absolute_expires_at: "2030-01-01T12:00:00+00:00",
    idle_expires_at: "2030-01-01T11:00:00.123456+00:00", csrf_token: token, ...extra };
}
function response(data: unknown, status = 200) {
  return new Response(JSON.stringify({ data, trace_id: id }), { status, headers: { "Content-Type": "application/json" } });
}
function client(...responses: Response[]) {
  const fetcher = vi.fn();
  for (const item of responses) fetcher.mockResolvedValueOnce(item);
  return { api: new SessionClient(fetcher as typeof fetch), fetcher };
}

describe("SessionClient", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); });

  it("uses only relative same-origin Cookie requests and returns safe immutable identity", async () => {
    const { api, fetcher } = client(response(session({ secret: "not-public" })));
    const view = await api.login("测试用户", "synthetic-input");
    expect(fetcher).toHaveBeenCalledWith("/api/v1/auth/login", expect.objectContaining({
      credentials: "same-origin", cache: "no-store", redirect: "error", method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify({ username: "测试用户", password: "synthetic-input" }),
    }));
    expect(view).not.toHaveProperty("csrf_token");
    expect(view).not.toHaveProperty("secret");
    expect(Object.isFrozen(view)).toBe(true);
    expect(Object.isFrozen(view.user)).toBe(true);
    expect(Object.isFrozen(view.authorized_projects)).toBe(true);
    expect(api.canSubmit).toBe(true);
    expect(JSON.stringify(api)).not.toContain(token);
  });

  it("notifies session-bound UI when identity is invalidated or replaced and supports unsubscribe", async () => {
    const { api } = client(response(session()), response(session({ csrf_token: "b".repeat(64) })), response({ revoked: true }));
    const observed: Array<string | null> = []; const revisions: number[] = [];
    const unsubscribe = api.subscribe(() => { observed.push(api.view?.user.user_id ?? null); revisions.push(api.revision); });
    await api.login("user", "synthetic-input"); await api.renew();
    expect(observed).toEqual([null, id, null, id]); expect(revisions).toEqual([1, 2, 3, 4]);
    unsubscribe(); await api.logout("synthetic-key-0001"); expect(observed).toHaveLength(4);
  });

  it("notifies the application boundary when a Prototype write receives session expiry", async () => {
    const expired = new Response("", { status: 401 }); const { api } = client(response(session()), expired);
    await api.login("user", "synthetic-input"); const listener = vi.fn(); api.subscribe(listener);
    await expect(api.writePrototype({ operation: "package-create", projectId }, JSON.stringify({ name: "原型包" }),
      null, "prototype-create-0001")).resolves.toBe(expired);
    expect(api.view).toBeNull(); expect(api.canSubmit).toBe(false); expect(listener).toHaveBeenCalledTimes(1);
  });

  it("does not persist inputs or tokens in browser storage", async () => {
    const local = vi.spyOn(Storage.prototype, "setItem");
    const cookies = vi.spyOn(Document.prototype, "cookie", "set");
    const { api } = client(response(session()));
    await api.login("user", "synthetic-input");
    expect(local).not.toHaveBeenCalled();
    expect(cookies).not.toHaveBeenCalled();
    expect(JSON.stringify(api)).not.toContain("synthetic-input");
  });

  it("never binds a transport function to the SessionClient receiver", async () => {
    const fetcher = function (this: unknown): Promise<Response> {
      expect(this).toBeUndefined();
      return Promise.resolve(response(session()));
    } as typeof fetch;
    const api = new SessionClient(fetcher);
    await expect(api.login("user", "synthetic-input")).resolves.toMatchObject({ deployment_role: "DEPLOYMENT_ADMIN" });
  });

  it.each(["+08:00", "-04:00"])("normalizes valid database offset %s to UTC", async (offset) => {
    const { api } = client(response(session({ absolute_expires_at: `2030-01-01T12:00:00${offset}`,
      idle_expires_at: `2030-01-01T11:00:00.123456${offset}` })));
    const view = await api.login("user", "synthetic-input");
    expect(view.absolute_expires_at).toBe(new Date(`2030-01-01T12:00:00${offset}`).toISOString());
    expect(view.idle_expires_at).toBe(new Date(`2030-01-01T11:00:00.123456${offset}`).toISOString());
  });

  it("accepts restricted identity without inventing rights", async () => {
    const { api } = client(response(session({ password_change_required: true, deployment_role: "NONE" })));
    const view = await api.login("user", "synthetic-input");
    expect(view.password_change_required).toBe(true);
    expect(view.deployment_role).toBe("NONE");
    expect(view.authorized_projects).toEqual([]);
  });

  it("accepts current project enum and strips extra project details", async () => {
    const { api } = client(response(session({ authorized_projects: [{ project_id: id, name: "项目",
      role: "PROJECT_MANAGER", internal: "not-public" }] })));
    const view = await api.login("user", "synthetic-input");
    expect(view.authorized_projects[0]).toEqual({ project_id: id, name: "项目", role: "PROJECT_MANAGER" });
    expect(Object.isFrozen(view.authorized_projects[0])).toBe(true);
  });

  it.each([
    { deployment_role: "ROOT" }, { deployment_role: ["NONE"] },
    { password_change_required: "false" }, { password_change_required: true },
    { user: { user_id: "bad", username_display: "user" } },
    { user: { user_id: "00000000-0000-0000-0000-000000000000", username_display: "user" } },
    { authorized_projects: [{ project_id: id, name: "项目", role: "ROOT" }] },
    { password_change_required: true, deployment_role: "NONE", authorized_projects: [{ project_id: id, name: "项目", role: "PROJECT_MANAGER" }] },
    { authorized_projects: [{ project_id: id, name: "项目", role: "PROJECT_MANAGER" }, { project_id: id, name: "项目", role: "PROJECT_MANAGER" }] },
    { absolute_expires_at: "not-a-date" }, { absolute_expires_at: "2030-02-30T12:00:00Z" },
    { idle_expires_at: "2031-01-01T12:00:00Z" }, { csrf_token: "bad" },
  ])("fails closed on malformed or inconsistent session %j", async (extra) => {
    const { api } = client(response(session(extra)));
    await expect(api.login("user", "synthetic-input")).rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    expect(api.view).toBeNull();
    expect(api.canSubmit).toBe(false);
  });

  it("current GET recovers read-only identity, never persists or invents CSRF", async () => {
    const data = session(); delete (data as Partial<typeof data>).csrf_token;
    const { api, fetcher } = client(response(session()), response(data));
    await api.login("user", "synthetic-input");
    await api.current();
    expect(api.view?.user.user_id).toBe(id);
    expect(api.canSubmit).toBe(false);
    await expect(api.renew()).rejects.toMatchObject({ code: "AUTH_RELOGIN_REQUIRED" });
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(fetcher.mock.calls[1]).toEqual(["/api/v1/auth/session", expect.objectContaining({ method: "GET", body: undefined })]);
  });

  it("renew rotates CSRF and logout supplies the exact caller idempotency key without a body", async () => {
    const rotated = "b".repeat(64);
    const { api, fetcher } = client(response(session()), response(session({ csrf_token: rotated })), response({ revoked: true }));
    await api.login("user", "synthetic-input");
    await api.renew();
    await api.logout("synthetic-key-0001");
    expect(fetcher.mock.calls[1][1]).toMatchObject({ method: "POST", body: undefined, headers: { "X-CSRF-Token": token } });
    expect(fetcher.mock.calls[2][1]).toMatchObject({ method: "POST", body: undefined,
      headers: { "X-CSRF-Token": rotated, "Idempotency-Key": "synthetic-key-0001" } });
    expect(api.view).toBeNull();
    expect(api.canSubmit).toBe(false);
  });

  it.each(["short", "x".repeat(129), "synthetic-key-\n0001"])("rejects invalid logout key without sending %j", async (key) => {
    const { api, fetcher } = client(response(session()));
    await api.login("user", "synthetic-input");
    await expect(api.logout(key)).rejects.toBeInstanceOf(SessionClientError);
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(api.canSubmit).toBe(false);
  });

  it("rejects logout without local CSRF, never fakes server revocation", async () => {
    const { api, fetcher } = client();
    await expect(api.logout("synthetic-key-0001")).rejects.toMatchObject({ code: "AUTH_RELOGIN_REQUIRED" });
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("rejects a logout result that does not confirm revocation", async () => {
    const { api } = client(response(session()), response({ revoked: false }));
    await api.login("user", "synthetic-input");
    await expect(api.logout("synthetic-key-0001")).rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
  });

  it.each([false, true])("changes password once with the original CSRF and caller key (restricted=%s)", async (restricted) => {
    const initial = restricted ? session({ password_change_required: true, deployment_role: "NONE" }) : session();
    const { api, fetcher } = client(response(initial), response({ credential_version: 2, internal: "not-public" }));
    await api.login("user", "old-synthetic");
    await expect(api.changePassword("旧密码", "新密码-123", "synthetic-change-0001")).resolves.toBe(2);
    expect(fetcher.mock.calls[1]).toEqual(["/api/v1/auth/password:change", expect.objectContaining({
      method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error",
      headers: { Accept: "application/json", "Content-Type": "application/json",
        "X-CSRF-Token": token, "Idempotency-Key": "synthetic-change-0001" },
      body: JSON.stringify({ current_password: "旧密码", new_password: "新密码-123" }),
    })]);
    expect(api.view).toBeNull();
    expect(api.canSubmit).toBe(false);
    expect(JSON.stringify(api)).not.toContain("新密码-123");
  });

  it.each(["", "\0secret", "x".repeat(1025), "汉".repeat(342)])("rejects invalid password before request without losing active login", async (value) => {
    const { api, fetcher } = client(response(session()));
    await api.login("user", "synthetic-input");
    await expect(api.changePassword(value, "new-secret", "synthetic-change-0001"))
      .rejects.toMatchObject({ code: "VALIDATION_FAILED" });
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(api.canSubmit).toBe(true);
  });

  it("rejects a malformed caller key before request and read-only sessions cannot change password", async () => {
    const readOnly = session(); delete (readOnly as Partial<typeof readOnly>).csrf_token;
    const { api, fetcher } = client(response(session()), response(readOnly));
    await api.login("user", "synthetic-input");
    await expect(api.changePassword("old", "new", "short"))
      .rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    expect(api.canSubmit).toBe(true);
    await api.current();
    await expect(api.changePassword("old", "new", "synthetic-change-0001"))
      .rejects.toMatchObject({ code: "AUTH_RELOGIN_REQUIRED" });
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it.each([[409, "CONFLICT_IDEMPOTENCY"], [422, "VALIDATION_FAILED"],
    [503, "SYSTEM_UNAVAILABLE"]] as const)("does not retry uncertain or rejected change %s %s", async (status, code) => {
    const failed = new Response(JSON.stringify({ error: { code, message: "private" }, trace_id: id }),
      { status, headers: { "Content-Type": "application/json" } });
    const { api, fetcher } = client(response(session()), failed);
    await api.login("user", "synthetic-input");
    const error = await api.changePassword("old", "new", "synthetic-change-0001").catch((value: unknown) => value);
    expect(error).toBeInstanceOf(SessionClientError);
    if (!(error instanceof SessionClientError)) throw new Error("expected safe client error");
    expect(String(error)).not.toContain("private");
    expect(error.code).toBe(code === "SYSTEM_UNAVAILABLE" ? "AUTH_CLIENT_UNAVAILABLE" : code);
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(api.view).toBeNull();
    expect(api.canSubmit).toBe(false);
  });

  it.each([{}, { credential_version: 1 }, { credential_version: 2.5 },
    { credential_version: "2" }])("fails closed on malformed change response %j", async (data) => {
    const { api } = client(response(session()), response(data));
    await api.login("user", "synthetic-input");
    await expect(api.changePassword("old", "new", "synthetic-change-0001"))
      .rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    expect(api.view).toBeNull();
  });

  it("rejects changed identity during renewal and discards the returned CSRF", async () => {
    const { api } = client(response(session()), response(session({
      user: { user_id: "11234567-89ab-4cde-8123-456789abcdef", username_display: "other" },
    })));
    await api.login("user", "synthetic-input");
    await expect(api.renew()).rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    expect(api.view).toBeNull();
    expect(api.canSubmit).toBe(false);
  });

  it("does not trust a recognized error code with the wrong HTTP status", async () => {
    const { api } = client(new Response(JSON.stringify({ error: { code: "AUTH_INVALID_CREDENTIALS" }, trace_id: id }),
      { status: 503, headers: { "Content-Type": "application/json" } }));
    await expect(api.current()).rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
  });

  it.each([[401, "AUTH_INVALID_CREDENTIALS"], [401, "AUTH_SESSION_EXPIRED"], [403, "AUTH_CSRF_INVALID"],
    [429, "AUTH_RATE_LIMITED"], [503, "PRIVATE_CODE"]] as const)("returns fixed safe error for %s %s", async (status, code) => {
    const raw = new Response(JSON.stringify({ error: { code, message: "private host/password" }, trace_id: id }),
      { status, headers: { "Content-Type": "application/json" } });
    const { api, fetcher } = client(raw);
    const error = await api.current().catch((value: unknown) => value);
    expect(error).toBeInstanceOf(SessionClientError);
    expect(String(error)).not.toContain("private");
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(api.view).toBeNull();
  });

  it.each([
    new Response("<html>private</html>", { headers: { "Content-Type": "text/html" } }),
    new Response("bad-json", { headers: { "Content-Type": "application/json" } }),
    new Response(JSON.stringify({ data: session() }), { headers: { "Content-Type": "application/json" } }),
    new Response(JSON.stringify({ data: session(), trace_id: "bad" }), { headers: { "Content-Type": "application/json" } }),
  ])("rejects bad content/envelope without exposing it", async (raw) => {
    const { api } = client(raw);
    await expect(api.current()).rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
  });

  it("clears local state after an uncertain renew transport failure, without retry", async () => {
    const { api, fetcher } = client(response(session()));
    fetcher.mockRejectedValueOnce(new Error("private transport details"));
    await api.login("user", "synthetic-input");
    await expect(api.renew()).rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    expect(api.view).toBeNull();
    expect(api.canSubmit).toBe(false);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("prevents concurrent commands from racing Cookie/CSRF rotation", async () => {
    let resolve!: (value: Response) => void;
    const fetcher = vi.fn().mockReturnValue(new Promise<Response>((done) => { resolve = done; }));
    const api = new SessionClient(fetcher as typeof fetch);
    const pending = api.login("user", "synthetic-input");
    await expect(api.current()).rejects.toMatchObject({ code: "AUTH_CLIENT_BUSY" });
    expect(fetcher).toHaveBeenCalledTimes(1);
    resolve(response(session()));
    await pending;
    expect(api.canSubmit).toBe(true);
  });

  it("aborts a timed-out request and releases its exclusive state", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn().mockImplementation((_path: string, options: RequestInit) => new Promise((_resolve, reject) => {
      options.signal?.addEventListener("abort", () => reject(new Error("private timeout")));
    }));
    const api = new SessionClient(fetcher as typeof fetch, 100);
    const pending = expect(api.current()).rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    await vi.advanceTimersByTimeAsync(101);
    await pending;
    expect(api.view).toBeNull();
    expect(api.canSubmit).toBe(false);
  });

  it.each([0, -1, 30_001, 1.5, NaN])("rejects invalid client timeout %s", (timeout) => {
    expect(() => new SessionClient(fetch, timeout)).toThrow(SessionClientError);
  });

  it("posts one scoped Project bootstrap request with private CSRF and original caller key", async () => {
    const created = response({ project_id: id }, 201);
    const { api, fetcher } = client(response(session()), created);
    await api.login("user", "synthetic-only");
    const body = JSON.stringify({ code: "DEMO", name: "演示", initial_manager_user_id: id });
    await expect(api.postProjectCreate(body, "synthetic-project-0001")).resolves.toBe(created);
    expect(fetcher.mock.calls[1]).toEqual(["/api/v1/projects", expect.objectContaining({
      method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error", body,
      headers: { Accept: "application/json", "Content-Type": "application/json",
        "X-CSRF-Token": token, "Idempotency-Key": "synthetic-project-0001" },
    })]);
    expect(api.view?.user.user_id).toBe(id);
    expect(api.canSubmit).toBe(true);
    expect(JSON.stringify(api)).not.toContain(token);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("posts one fixed Project UploadIntent with private CSRF and the original key", async () => {
    const created = response({ upload_id: id }, 201);
    const { api, fetcher } = client(response(session()), created);
    await api.login("user", "synthetic-only");
    const body = JSON.stringify({ purpose: "SOURCE", category: "SOLUTION", title: "测试", display_name: "test.pdf" });
    await expect(api.postProjectDocumentUploadCreate(projectId, body, "synthetic-upload-0001")).resolves.toBe(created);
    expect(fetcher.mock.calls[1]).toEqual([`/api/v1/projects/${projectId}/document-uploads`,
      expect.objectContaining({ method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error",
        headers: { Accept: "application/json", "Content-Type": "application/json",
          "X-CSRF-Token": token, "Idempotency-Key": "synthetic-upload-0001" }, body,
        signal: expect.any(AbortSignal) })]);
    expect(JSON.stringify(api)).not.toContain(token);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("rejects invalid UploadIntent project, key and oversized body before transport", async () => {
    const { api, fetcher } = client(response(session()));
    await api.login("user", "synthetic-only");
    for (const project of ["../other", "00000000-0000-0000-0000-000000000000", projectId.toUpperCase()]) {
      await expect(api.postProjectDocumentUploadCreate(project, "{}", "synthetic-upload-0001"))
        .rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    }
    await expect(api.postProjectDocumentUploadCreate(projectId, "{}", "short"))
      .rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    await expect(api.postProjectDocumentUploadCreate(projectId, "x".repeat(8193), "synthetic-upload-0001"))
      .rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("requires writable Session and clears proof on UploadIntent 401", async () => {
    const { api, fetcher } = client(response(session()), new Response("{}", { status: 401 }));
    await expect(api.postProjectDocumentUploadCreate(projectId, "{}", "synthetic-upload-0001"))
      .rejects.toMatchObject({ code: "AUTH_RELOGIN_REQUIRED" });
    await api.login("user", "synthetic-only");
    await expect(api.postProjectDocumentUploadCreate(projectId, "{}", "synthetic-upload-0001"))
      .resolves.toMatchObject({ status: 401 });
    expect(api.canSubmit).toBe(false);
    expect(api.view).toBeNull();
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("keeps UploadIntent exclusive and does not replay an uncertain timeout", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn().mockResolvedValueOnce(response(session()))
      .mockImplementationOnce((_path: string, options: RequestInit) => new Promise((_done, reject) => {
        options.signal?.addEventListener("abort", () => reject(new Error("synthetic transport failure")));
      }));
    const api = new SessionClient(fetcher as typeof fetch, 100);
    await api.login("user", "synthetic-only");
    const pending = expect(api.postProjectDocumentUploadCreate(projectId, "{}", "synthetic-upload-0001"))
      .rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    await expect(api.renew()).rejects.toMatchObject({ code: "AUTH_CLIENT_BUSY" });
    await vi.advanceTimersByTimeAsync(101);
    await pending;
    expect(api.canSubmit).toBe(true);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("PUTs one known-length Blob to the fixed project upload path with private proof", async () => {
    const uploadId = "21234567-89ab-4cde-8123-456789abcdef";
    const proof = "u".repeat(43);
    const digest = "b".repeat(64);
    const content = new Blob(["synthetic content"], { type: "text/plain" });
    const received = response({ upload_id: uploadId, size_bytes: content.size });
    const { api, fetcher } = client(response(session()), received);
    await api.login("user", "synthetic-only");
    await expect(api.putProjectDocumentUploadContent(projectId, uploadId, proof, digest, content)).resolves.toBe(received);
    expect(fetcher.mock.calls[1]).toEqual([`/api/v1/projects/${projectId}/document-uploads/${uploadId}/content`,
      expect.objectContaining({ method: "PUT", credentials: "same-origin", cache: "no-store",
        redirect: "error", body: content, signal: expect.any(AbortSignal),
        headers: { Accept: "application/json", "Content-Type": "application/octet-stream",
          "X-CSRF-Token": token, "X-Upload-Token": proof, "X-Content-SHA256": digest } })]);
    expect(fetcher.mock.calls[1][1].headers).not.toHaveProperty("Content-Length");
    expect(JSON.stringify(api)).not.toContain(proof);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("rejects invalid Content PUT claims and Blob size before network", async () => {
    const { api, fetcher } = client(response(session()));
    await api.login("user", "synthetic-only");
    const content = new Blob(["synthetic"]);
    const oversized = new Blob(["synthetic"]);
    Object.defineProperty(oversized, "size", { value: 100_000_001 });
    for (const [project, upload, proof, digest, file] of [
      ["../other", id, "u".repeat(43), "b".repeat(64), content],
      [projectId, "bad", "u".repeat(43), "b".repeat(64), content],
      [projectId, id, "bad", "b".repeat(64), content],
      [projectId, id, "u".repeat(43), "B".repeat(64), content],
      [projectId, id, "u".repeat(43), "b".repeat(64), new Blob([])],
      [projectId, id, "u".repeat(43), "b".repeat(64), oversized],
    ] as const) {
      await expect(api.putProjectDocumentUploadContent(project, upload, proof, digest, file))
        .rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    }
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("requires writable Session and clears local proof on Content PUT 401", async () => {
    const { api, fetcher } = client(response(session()), new Response("{}", { status: 401 }));
    const content = new Blob(["synthetic"]);
    await expect(api.putProjectDocumentUploadContent(projectId, id, "u".repeat(43), "b".repeat(64), content))
      .rejects.toMatchObject({ code: "AUTH_RELOGIN_REQUIRED" });
    await api.login("user", "synthetic-only");
    await expect(api.putProjectDocumentUploadContent(projectId, id, "u".repeat(43), "b".repeat(64), content))
      .resolves.toMatchObject({ status: 401 });
    expect(api.canSubmit).toBe(false);
    expect(api.view).toBeNull();
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("holds Content PUT exclusive and aborts at its upload deadline without replay", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn().mockResolvedValueOnce(response(session()))
      .mockImplementationOnce((_path: string, options: RequestInit) => new Promise((_done, reject) => {
        options.signal?.addEventListener("abort", () => reject(new Error("synthetic network failure")));
      }));
    const api = new SessionClient(fetcher as typeof fetch);
    await api.login("user", "synthetic-only");
    const pending = expect(api.putProjectDocumentUploadContent(projectId, id, "u".repeat(43),
      "b".repeat(64), new Blob(["synthetic"]))).rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    await expect(api.renew()).rejects.toMatchObject({ code: "AUTH_CLIENT_BUSY" });
    await vi.advanceTimersByTimeAsync(300_001);
    await pending;
    expect(api.canSubmit).toBe(true);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it.each(["commit", "abort"] as const)("sends one empty-body Project upload %s with private CSRF and original key", async (action) => {
    const uploadId = "21234567-89ab-4cde-8123-456789abcdef";
    const reply = response({ upload_id: uploadId }, action === "commit" ? 201 : 200);
    const { api, fetcher } = client(response(session()), reply);
    await api.login("user", "synthetic-only");
    const key = `synthetic-${action}-0001`;
    if (action === "commit") {
      await expect(api.postProjectDocumentUploadCommit(projectId, uploadId, key, '"v0"')).resolves.toBe(reply);
    } else {
      await expect(api.postProjectDocumentUploadAbort(projectId, uploadId, key)).resolves.toBe(reply);
    }
    expect(fetcher.mock.calls[1]).toEqual([`/api/v1/projects/${projectId}/document-uploads/${uploadId}:${action}`,
      { method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error",
        headers: { Accept: "application/json", "X-CSRF-Token": token, "Idempotency-Key": key,
          ...(action === "commit" ? { "If-Match": '"v0"' } : {}) }, signal: expect.any(AbortSignal) }]);
    expect(fetcher.mock.calls[1][1]).not.toHaveProperty("body");
    expect(fetcher.mock.calls[1][1].headers).not.toHaveProperty("Content-Type");
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("omits If-Match for a new Document upload Commit", async () => {
    const { api, fetcher } = client(response(session()), response({ upload_id: id }, 201));
    await api.login("user", "synthetic-only");
    await api.postProjectDocumentUploadCommit(projectId, id, "synthetic-commit-0001");
    expect(fetcher.mock.calls[1][1].headers).not.toHaveProperty("If-Match");
  });

  it("rejects malformed upload finalize IDs, key and parent ETag before network", async () => {
    const { api, fetcher } = client(response(session()));
    await api.login("user", "synthetic-only");
    await expect(api.postProjectDocumentUploadCommit("../other", id, "synthetic-commit-0001"))
      .rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    await expect(api.postProjectDocumentUploadAbort(projectId, "bad", "synthetic-abort-0001"))
      .rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    await expect(api.postProjectDocumentUploadAbort(projectId, id, "short"))
      .rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    for (const etag of ["v0", '"v01"', '"v9007199254740991"']) {
      await expect(api.postProjectDocumentUploadCommit(projectId, id, "synthetic-commit-0001", etag))
        .rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    }
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("requires writable Session and clears local proof on finalize 401", async () => {
    const { api, fetcher } = client(response(session()), new Response("{}", { status: 401 }));
    await expect(api.postProjectDocumentUploadAbort(projectId, id, "synthetic-abort-0001"))
      .rejects.toMatchObject({ code: "AUTH_RELOGIN_REQUIRED" });
    await api.login("user", "synthetic-only");
    await expect(api.postProjectDocumentUploadAbort(projectId, id, "synthetic-abort-0001"))
      .resolves.toMatchObject({ status: 401 });
    expect(api.canSubmit).toBe(false);
    expect(api.view).toBeNull();
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("holds upload finalize exclusive and aborts at its deadline without replay", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn().mockResolvedValueOnce(response(session()))
      .mockImplementationOnce((_path: string, options: RequestInit) => new Promise((_done, reject) => {
        options.signal?.addEventListener("abort", () => reject(new Error("synthetic network failure")));
      }));
    const api = new SessionClient(fetcher as typeof fetch);
    await api.login("user", "synthetic-only");
    const pending = expect(api.postProjectDocumentUploadCommit(projectId, id, "synthetic-commit-0001", '"v0"'))
      .rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    await expect(api.renew()).rejects.toMatchObject({ code: "AUTH_CLIENT_BUSY" });
    await vi.advanceTimersByTimeAsync(60_001);
    await pending;
    expect(api.canSubmit).toBe(true);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("does not submit Project create from a missing or read-only local session", async () => {
    const readOnly = session(); delete (readOnly as Partial<typeof readOnly>).csrf_token;
    const { api, fetcher } = client(response(readOnly));
    await expect(api.postProjectCreate("{}", "synthetic-project-0001"))
      .rejects.toMatchObject({ code: "AUTH_RELOGIN_REQUIRED" });
    await api.current();
    await expect(api.postProjectCreate("{}", "synthetic-project-0001"))
      .rejects.toMatchObject({ code: "AUTH_RELOGIN_REQUIRED" });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it.each(["short", "x".repeat(129), "key-with-a-newline\n0001"])(
    "rejects invalid Project create key before sending %j", async (key) => {
      const { api, fetcher } = client(response(session()));
      await api.login("user", "synthetic-only");
      await expect(api.postProjectCreate("{}", key)).rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
      expect(fetcher).toHaveBeenCalledTimes(1);
      expect(api.canSubmit).toBe(true);
    });

  it("clears local write proof on Project create 401 but preserves it for an uncertain 503", async () => {
    const unauthorized = new Response("{}", { status: 401 });
    const unavailable = new Response("{}", { status: 503 });
    const { api, fetcher } = client(response(session()), unavailable, unauthorized);
    await api.login("user", "synthetic-only");
    await api.postProjectCreate("{}", "synthetic-project-0001");
    expect(api.canSubmit).toBe(true);
    await api.postProjectCreate("{}", "synthetic-project-0001");
    expect(api.view).toBeNull();
    expect(api.canSubmit).toBe(false);
    expect(fetcher).toHaveBeenCalledTimes(3);
  });

  it("holds auth mutation exclusivity while Project create is in flight", async () => {
    let resolve!: (response: Response) => void;
    const fetcher = vi.fn().mockResolvedValueOnce(response(session()))
      .mockReturnValueOnce(new Promise<Response>((done) => { resolve = done; }));
    const api = new SessionClient(fetcher as typeof fetch);
    await api.login("user", "synthetic-only");
    const pending = api.postProjectCreate("{}", "synthetic-project-0001");
    expect(api.canSubmit).toBe(false);
    await expect(api.renew()).rejects.toMatchObject({ code: "AUTH_CLIENT_BUSY" });
    expect(fetcher).toHaveBeenCalledTimes(2);
    resolve(response({ project_id: id }, 201));
    await pending;
    expect(api.canSubmit).toBe(true);
  });

  it("aborts an uncertain Project create timeout once without dropping the original session", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn().mockResolvedValueOnce(response(session()))
      .mockImplementationOnce((_path: string, options: RequestInit) => new Promise((_done, reject) => {
        options.signal?.addEventListener("abort", () => reject(new Error("private transport failure")));
      }));
    const api = new SessionClient(fetcher as typeof fetch, 100);
    await api.login("user", "synthetic-only");
    const pending = expect(api.postProjectCreate("{}", "synthetic-project-0001"))
      .rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    await vi.advanceTimersByTimeAsync(101);
    await pending;
    expect(api.view?.user.user_id).toBe(id);
    expect(api.canSubmit).toBe(true);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("sends only the frozen Project PATCH path with v0, private CSRF and no idempotency key", async () => {
    const body = JSON.stringify({ name: "更新项目" });
    const reply = response({ project_id: projectId });
    const { api, fetcher } = client(response(session()), reply);
    await api.login("manager", "synthetic-only");
    await expect(api.patchProject(projectId, '"v0"', body)).resolves.toBe(reply);
    expect(fetcher.mock.calls[1]).toEqual([`/api/v1/projects/${projectId}`, {
      method: "PATCH", credentials: "same-origin", cache: "no-store", redirect: "error",
      headers: { Accept: "application/json", "Content-Type": "application/json",
        "X-CSRF-Token": token, "If-Match": '"v0"' }, body, signal: expect.any(AbortSignal),
    }]);
    expect(JSON.stringify(api)).not.toContain(token);
  });

  it("rejects unsafe Project PATCH path, version or body without network", async () => {
    const { api, fetcher } = client(response(session()));
    await api.login("manager", "synthetic-only");
    for (const [project, version, body] of [
      ["../admin", '"v0"', "{}"], [projectId.toUpperCase(), '"v0"', "{}"],
      [projectId, 'W/"v0"', "{}"], [projectId, '"v00"', "{}"],
      [projectId, '"v9007199254740991"', "{}"], [projectId, '"v0"', ""],
      [projectId, '"v0"', "中".repeat(2731)],
    ]) {
      await expect(api.patchProject(project, version, body))
        .rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    }
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("requires CSRF and clears Project PATCH proof on 401, not 503", async () => {
    const readOnly = session(); delete (readOnly as Partial<typeof readOnly>).csrf_token;
    const { api: viewer, fetcher: viewerFetcher } = client(response(readOnly));
    await viewer.current();
    await expect(viewer.patchProject(projectId, '"v0"', "{}"))
      .rejects.toMatchObject({ code: "AUTH_RELOGIN_REQUIRED" });
    expect(viewerFetcher).toHaveBeenCalledTimes(1);
    const { api, fetcher } = client(response(session()), new Response("{}", { status: 503 }),
      new Response("{}", { status: 401 }));
    await api.login("manager", "synthetic-only");
    await api.patchProject(projectId, '"v0"', "{}");
    expect(api.canSubmit).toBe(true);
    await api.patchProject(projectId, '"v0"', "{}");
    expect(api.canSubmit).toBe(false);
    expect(api.view).toBeNull();
    expect(fetcher).toHaveBeenCalledTimes(3);
  });

  it("does not retry a timed-out Project PATCH or overlap another command", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn().mockResolvedValueOnce(response(session()))
      .mockImplementationOnce((_path: string, options: RequestInit) => new Promise((_done, reject) => {
        options.signal?.addEventListener("abort", () => reject(new Error("synthetic timeout")));
      }));
    const api = new SessionClient(fetcher as typeof fetch, 100);
    await api.login("manager", "synthetic-only");
    const pending = expect(api.patchProject(projectId, '"v0"', "{}"))
      .rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    await expect(api.postProjectCreate("{}", "synthetic-project-0001"))
      .rejects.toMatchObject({ code: "AUTH_CLIENT_BUSY" });
    await vi.advanceTimersByTimeAsync(101);
    await pending;
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(api.canSubmit).toBe(true);
  });

  it("posts only the frozen empty-body Project archive with original version, key and private CSRF", async () => {
    const archived = response({ project_id: projectId, state: "ARCHIVED" });
    const { api, fetcher } = client(response(session()), archived);
    await api.login("manager", "synthetic-only");
    const key = "synthetic-project-archive-0001";
    await expect(api.postProjectArchive(projectId, '"v7"', key)).resolves.toBe(archived);
    expect(fetcher.mock.calls[1]).toEqual([`/api/v1/projects/${projectId}:archive`, {
      method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error",
      headers: { Accept: "application/json", "X-CSRF-Token": token,
        "Idempotency-Key": key, "If-Match": '"v7"' }, signal: expect.any(AbortSignal),
    }]);
    expect(JSON.stringify(api)).not.toContain(token);
    expect(api.canSubmit).toBe(true);
  });

  it("rejects unsafe Project archive path, version and key without network", async () => {
    const { api, fetcher } = client(response(session()));
    await api.login("manager", "synthetic-only");
    for (const [project, etag, key] of [
      ["../other", '"v0"', "synthetic-project-archive-0001"],
      [projectId.toUpperCase(), '"v0"', "synthetic-project-archive-0001"],
      [projectId, 'W/"v0"', "synthetic-project-archive-0001"],
      [projectId, '"v00"', "synthetic-project-archive-0001"],
      [projectId, '"v9007199254740991"', "synthetic-project-archive-0001"],
      [projectId, '"v0"', "short"],
      [projectId, '"v0"', "synthetic-project-archive\n0001"],
    ]) {
      await expect(api.postProjectArchive(project, etag, key))
        .rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    }
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("requires fresh Project archive write proof, retaining it on unknown result and clearing on 401", async () => {
    const readOnly = session(); delete (readOnly as Partial<typeof readOnly>).csrf_token;
    const { api: viewer, fetcher: viewerFetcher } = client(response(readOnly));
    await viewer.current();
    await expect(viewer.postProjectArchive(projectId, '"v0"', "synthetic-project-archive-0001"))
      .rejects.toMatchObject({ code: "AUTH_RELOGIN_REQUIRED" });
    expect(viewerFetcher).toHaveBeenCalledTimes(1);
    const { api, fetcher } = client(response(session()), new Response("{}", { status: 503 }),
      new Response("{}", { status: 401 }));
    await api.login("manager", "synthetic-only");
    await api.postProjectArchive(projectId, '"v0"', "synthetic-project-archive-0001");
    expect(api.canSubmit).toBe(true);
    await api.postProjectArchive(projectId, '"v0"', "synthetic-project-archive-0001");
    expect(api.view).toBeNull();
    expect(api.canSubmit).toBe(false);
    expect(fetcher).toHaveBeenCalledTimes(3);
  });

  it("does not overlap or retry a timed-out Project archive command", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn().mockResolvedValueOnce(response(session()))
      .mockImplementationOnce((_path: string, options: RequestInit) => new Promise((_done, reject) => {
        options.signal?.addEventListener("abort", () => reject(new Error("synthetic timeout")));
      }));
    const api = new SessionClient(fetcher as typeof fetch, 100);
    await api.login("manager", "synthetic-only");
    const pending = expect(api.postProjectArchive(projectId, '"v0"', "synthetic-project-archive-0001"))
      .rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    await expect(api.postProjectCreate("{}", "synthetic-project-create-0001"))
      .rejects.toMatchObject({ code: "AUTH_CLIENT_BUSY" });
    await vi.advanceTimersByTimeAsync(101);
    await pending;
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(api.canSubmit).toBe(true);
  });

  it("posts only an empty Workflow start with private CSRF and original v0/Key", async () => {
    const first = response({ workflow_id: id, state: "ACTIVE", etag: '"v1"' });
    const { api, fetcher } = client(response(session()), first);
    await api.login("manager", "synthetic-only");
    const key = "synthetic-workflow-start-0001";
    await expect(api.postProjectWorkflowStart(projectId, '"v0"', key)).resolves.toBe(first);
    expect(fetcher.mock.calls[1]).toEqual([`/api/v1/projects/${projectId}/workflow:start`, {
      method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error",
      headers: { Accept: "application/json", "X-CSRF-Token": token,
        "Idempotency-Key": key, "If-Match": '"v0"' }, signal: expect.any(AbortSignal),
    }]);
    expect(JSON.stringify(api)).not.toContain(token);
    expect(api.canSubmit).toBe(true);
  });

  it("rejects Workflow start unsafe scope, stale version and bad Key before network", async () => {
    const { api, fetcher } = client(response(session()));
    await api.login("manager", "synthetic-only");
    for (const [project, etag, key] of [
      ["../other", '"v0"', "synthetic-workflow-start-0001"],
      [projectId.toUpperCase(), '"v0"', "synthetic-workflow-start-0001"],
      [projectId, '"v1"', "synthetic-workflow-start-0001"],
      [projectId, 'W/"v0"', "synthetic-workflow-start-0001"],
      [projectId, '"v0"', "short"],
      [projectId, '"v0"', "synthetic-workflow\nstart-0001"],
    ]) {
      await expect(api.postProjectWorkflowStart(project, etag, key))
        .rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    }
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("requires current Workflow start write proof, retains original on unknown and clears on 401", async () => {
    const readOnly = session(); delete (readOnly as Partial<typeof readOnly>).csrf_token;
    const { api: viewer, fetcher: viewerFetcher } = client(response(readOnly));
    await viewer.current();
    await expect(viewer.postProjectWorkflowStart(projectId, '"v0"', "synthetic-workflow-start-0001"))
      .rejects.toMatchObject({ code: "AUTH_RELOGIN_REQUIRED" });
    expect(viewerFetcher).toHaveBeenCalledTimes(1);
    const { api, fetcher } = client(response(session()), new Response("{}", { status: 503 }),
      new Response("{}", { status: 401 }));
    await api.login("manager", "synthetic-only");
    await api.postProjectWorkflowStart(projectId, '"v0"', "synthetic-workflow-start-0001");
    expect(api.canSubmit).toBe(true);
    await api.postProjectWorkflowStart(projectId, '"v0"', "synthetic-workflow-start-0001");
    expect(api.view).toBeNull();
    expect(api.canSubmit).toBe(false);
    expect(fetcher).toHaveBeenCalledTimes(3);
  });

  it("never overlaps or automatically retries a timed-out Workflow start", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn().mockResolvedValueOnce(response(session()))
      .mockImplementationOnce((_path: string, options: RequestInit) => new Promise((_done, reject) => {
        options.signal?.addEventListener("abort", () => reject(new Error("synthetic timeout")));
      }));
    const api = new SessionClient(fetcher as typeof fetch, 100);
    await api.login("manager", "synthetic-only");
    const pending = expect(api.postProjectWorkflowStart(projectId, '"v0"',
      "synthetic-workflow-start-0001"))
      .rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    await expect(api.postProjectWorkflowStart(projectId, '"v0"', "synthetic-workflow-start-0001"))
      .rejects.toMatchObject({ code: "AUTH_CLIENT_BUSY" });
    await vi.advanceTimersByTimeAsync(101);
    await pending;
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(api.canSubmit).toBe(true);
  });

  it("posts a bounded Checklist record with private CSRF and caller-owned replay inputs", async () => {
    const receipt = response({ record_id: id, result: "PASS", etag: '"v5"' });
    const { api, fetcher } = client(response(session()), receipt);
    await api.login("manager", "synthetic-only");
    const body = JSON.stringify({ result: "PASS", reason: null, impact: null,
      evidence_refs: [id], exception_refs: [] });
    const key = "synthetic-checklist-record-0001";
    await expect(api.postProjectWorkflowChecklistRecord(projectId,
      "HANDOVER_BASELINE", body, '"v4"', key)).resolves.toBe(receipt);
    expect(fetcher.mock.calls[1]).toEqual([
      `/api/v1/projects/${projectId}/workflow/checklist-items/HANDOVER_BASELINE:record`, {
        method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error",
        headers: { Accept: "application/json", "Content-Type": "application/json",
          "X-CSRF-Token": token, "Idempotency-Key": key, "If-Match": '"v4"' },
        body, signal: expect.any(AbortSignal),
      },
    ]);
    expect(JSON.stringify(api)).not.toContain(token);
    expect(api.canSubmit).toBe(true);
  });

  it("accepts Survey Checklist items on the same bounded write boundary", async () => {
    const receipt = response({ record_id: id, result: "PASS", etag: '"v7"' });
    const { api, fetcher } = client(response(session()), receipt);
    await api.login("manager", "synthetic-only");
    const body = JSON.stringify({ result: "PASS", reason: null, impact: null,
      evidence_refs: [id], exception_refs: [] });
    await expect(api.postProjectWorkflowChecklistRecord(projectId,
      "SURVEY_CONCLUSION", body, '"v6"', "synthetic-survey-record-0001"))
      .resolves.toBe(receipt);
    expect(fetcher.mock.calls[1]?.[0]).toBe(
      `/api/v1/projects/${projectId}/workflow/checklist-items/SURVEY_CONCLUSION:record`,
    );
  });

  it("accepts Requirement Checklist items on the same bounded write boundary", async () => {
    const receipt = response({ record_id: id, result: "PASS", etag: '"v10"' });
    const { api, fetcher } = client(response(session()), receipt);
    await api.login("manager", "synthetic-only");
    const body = JSON.stringify({ result: "PASS", reason: null, impact: null,
      evidence_refs: [id], exception_refs: [] });
    await expect(api.postProjectWorkflowChecklistRecord(projectId,
      "REQUIREMENT_ACCEPTANCE", body, '"v9"', "synthetic-requirement-record-0001"))
      .resolves.toBe(receipt);
    expect(fetcher.mock.calls[1]?.[0]).toBe(
      `/api/v1/projects/${projectId}/workflow/checklist-items/REQUIREMENT_ACCEPTANCE:record`,
    );
  });

  it("rejects unsafe Checklist path, body, version and Key before network", async () => {
    const { api, fetcher } = client(response(session()));
    await api.login("manager", "synthetic-only");
    const key = "synthetic-checklist-record-0001";
    for (const [project, item, body, etag, operation] of [
      ["../other", "HANDOVER_BASELINE", "{}", '"v4"', key],
      [projectId.toUpperCase(), "HANDOVER_BASELINE", "{}", '"v4"', key],
      [projectId, "PROTOTYPE_COVERAGE", "{}", '"v4"', key],
      [projectId, "HANDOVER_BASELINE", "", '"v4"', key],
      [projectId, "HANDOVER_BASELINE", "x".repeat(2 * 1024 * 1024 + 1), '"v4"', key],
      [projectId, "HANDOVER_BASELINE", "{}", '"v0"', key],
      [projectId, "HANDOVER_BASELINE", "{}", 'W/"v4"', key],
      [projectId, "HANDOVER_BASELINE", "{}", '"v9007199254740991"', key],
      [projectId, "HANDOVER_BASELINE", "{}", '"v4"', "short"],
    ] as const) {
      await expect(api.postProjectWorkflowChecklistRecord(project,
        item as "HANDOVER_BASELINE", body, etag, operation))
        .rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    }
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("requires Checklist write proof, retains it after unknown and clears it on 401", async () => {
    const readOnly = session(); delete (readOnly as Partial<typeof readOnly>).csrf_token;
    const { api: viewer, fetcher: viewerFetcher } = client(response(readOnly));
    await viewer.current();
    await expect(viewer.postProjectWorkflowChecklistRecord(projectId,
      "HANDOVER_ISSUES", "{}", '"v4"', "synthetic-checklist-record-0001"))
      .rejects.toMatchObject({ code: "AUTH_RELOGIN_REQUIRED" });
    expect(viewerFetcher).toHaveBeenCalledTimes(1);
    const { api, fetcher } = client(response(session()), new Response("{}", { status: 503 }),
      new Response("{}", { status: 401 }));
    await api.login("manager", "synthetic-only");
    await api.postProjectWorkflowChecklistRecord(projectId, "HANDOVER_ISSUES", "{}",
      '"v4"', "synthetic-checklist-record-0001");
    expect(api.canSubmit).toBe(true);
    await api.postProjectWorkflowChecklistRecord(projectId, "HANDOVER_ISSUES", "{}",
      '"v4"', "synthetic-checklist-record-0001");
    expect(api.canSubmit).toBe(false);
    expect(api.view).toBeNull();
    expect(fetcher).toHaveBeenCalledTimes(3);
  });

  it("never overlaps or retries a timed-out Checklist record", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn().mockResolvedValueOnce(response(session()))
      .mockImplementationOnce((_path: string, options: RequestInit) => new Promise((_done, reject) => {
        options.signal?.addEventListener("abort", () => reject(new Error("synthetic timeout")));
      }));
    const api = new SessionClient(fetcher as typeof fetch, 100);
    await api.login("manager", "synthetic-only");
    const pending = expect(api.postProjectWorkflowChecklistRecord(projectId,
      "HANDOVER_BASELINE", "{}", '"v4"', "synthetic-checklist-record-0001"))
      .rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    await expect(api.postProjectWorkflowChecklistRecord(projectId,
      "HANDOVER_BASELINE", "{}", '"v4"', "synthetic-checklist-record-0001"))
      .rejects.toMatchObject({ code: "AUTH_CLIENT_BUSY" });
    await vi.advanceTimersByTimeAsync(101);
    await pending;
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(api.canSubmit).toBe(true);
  });

  it("posts Workflow Transition with private CSRF and caller-owned replay inputs", async () => {
    const receipt = response({ stage_transition_id: id, etag: '"v4"' });
    const { api, fetcher } = client(response(session()), receipt);
    await api.login("manager", "synthetic-only");
    const body = JSON.stringify({ target_stage_key: "SURVEY", reason: "approved",
      gate_snapshot_refs: [] });
    const key = "synthetic-transition-key-0001";
    await expect(api.postProjectWorkflowTransition(projectId, body, '"v3"', key))
      .resolves.toBe(receipt);
    expect(fetcher.mock.calls[1]).toEqual([
      `/api/v1/projects/${projectId}/workflow:transition`, {
        method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error",
        headers: { Accept: "application/json", "Content-Type": "application/json",
          "X-CSRF-Token": token, "Idempotency-Key": key, "If-Match": '"v3"' },
        body, signal: expect.any(AbortSignal),
      },
    ]);
    expect(JSON.stringify(api)).not.toContain(token);
  });

  it("rejects unsafe Workflow Transition inputs and never overlaps a request", async () => {
    const { api, fetcher } = client(response(session()));
    await api.login("manager", "synthetic-only");
    const key = "synthetic-transition-key-0001";
    for (const [project, body, etag, operation] of [
      ["../other", "{}", '"v3"', key],
      [projectId.toUpperCase(), "{}", '"v3"', key],
      [projectId, "", '"v3"', key],
      [projectId, "x".repeat(8193), '"v3"', key],
      [projectId, "{}", '"v0"', key],
      [projectId, "{}", 'W/"v3"', key],
      [projectId, "{}", '"v9007199254740991"', key],
      [projectId, "{}", '"v3"', "short"],
    ] as const) {
      await expect(api.postProjectWorkflowTransition(project, body, etag, operation))
        .rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    }
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("keeps Workflow Transition submit capability after unknown and clears it on 401", async () => {
    const readOnly = session(); delete (readOnly as Partial<typeof readOnly>).csrf_token;
    const { api: viewer, fetcher: viewerFetcher } = client(response(readOnly));
    await viewer.current();
    await expect(viewer.postProjectWorkflowTransition(projectId, "{}", '"v3"',
      "synthetic-transition-key-0001"))
      .rejects.toMatchObject({ code: "AUTH_RELOGIN_REQUIRED" });
    expect(viewerFetcher).toHaveBeenCalledTimes(1);
    const { api, fetcher } = client(response(session()), new Response("{}", { status: 503 }),
      new Response("{}", { status: 401 }));
    await api.login("manager", "synthetic-only");
    await api.postProjectWorkflowTransition(projectId, "{}", '"v3"',
      "synthetic-transition-key-0001");
    expect(api.canSubmit).toBe(true);
    await api.postProjectWorkflowTransition(projectId, "{}", '"v3"',
      "synthetic-transition-key-0001");
    expect(api.canSubmit).toBe(false);
    expect(api.view).toBeNull();
    expect(fetcher).toHaveBeenCalledTimes(3);
  });

  it("posts Project Job cancel with private CSRF, original version, key and bounded reason", async () => {
    const receipt = response({ job_id: id, state: "CANCEL_REQUESTED", etag: '"v2"' });
    const { api, fetcher } = client(response(session()), receipt);
    await api.login("manager", "synthetic-only");
    const key = "synthetic-job-cancel-0001";
    await expect(api.postProjectJobCancel(projectId, id, '"v1"', key, "  用户请求取消  ")).resolves.toBe(receipt);
    expect(fetcher.mock.calls[1]).toEqual([`/api/v1/projects/${projectId}/jobs/${id}:cancel`, {
      method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error",
      headers: { Accept: "application/json", "Content-Type": "application/json", "X-CSRF-Token": token,
        "Idempotency-Key": key, "If-Match": '"v1"' },
      body: JSON.stringify({ reason: "用户请求取消" }), signal: expect.any(AbortSignal),
    }]);
    expect(JSON.stringify(api)).not.toContain(token);
  });

  it("rejects invalid Project Job cancellation inputs without network", async () => {
    const { api, fetcher } = client(response(session()));
    await api.login("manager", "synthetic-only");
    const key = "synthetic-job-cancel-0001";
    for (const [project, job, etag, operation, reason] of [
      ["../other", id, '"v1"', key, "reason"],
      [projectId, id.toUpperCase(), '"v1"', key, "reason"],
      [projectId, id, 'W/"v1"', key, "reason"],
      [projectId, id, '"v9007199254740991"', key, "reason"],
      [projectId, id, '"v1"', "short", "reason"],
      [projectId, id, '"v1"', key, "  "],
      [projectId, id, '"v1"', key, "reason\ninside"],
      [projectId, id, '"v1"', key, "reason\u200binside"],
      [projectId, id, '"v1"', key, "x".repeat(1025)],
    ]) {
      await expect(api.postProjectJobCancel(project, job, etag, operation, reason))
        .rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    }
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("requires a write session and clears it on 401, but retains it after an unknown result", async () => {
    const readOnly = session(); delete (readOnly as Partial<typeof readOnly>).csrf_token;
    const { api: viewer, fetcher: viewerFetcher } = client(response(readOnly));
    await viewer.current();
    await expect(viewer.postProjectJobCancel(projectId, id, '"v1"', "synthetic-job-cancel-0001", "reason"))
      .rejects.toMatchObject({ code: "AUTH_RELOGIN_REQUIRED" });
    expect(viewerFetcher).toHaveBeenCalledTimes(1);
    const { api, fetcher } = client(response(session()), new Response("{}", { status: 503 }),
      new Response("{}", { status: 401 }));
    await api.login("manager", "synthetic-only");
    await api.postProjectJobCancel(projectId, id, '"v1"', "synthetic-job-cancel-0001", "reason");
    expect(api.canSubmit).toBe(true);
    await api.postProjectJobCancel(projectId, id, '"v1"', "synthetic-job-cancel-0001", "reason");
    expect(api.canSubmit).toBe(false);
    expect(api.view).toBeNull();
    expect(fetcher).toHaveBeenCalledTimes(3);
  });

  it("does not overlap or retry a timed-out Project Job cancellation", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn().mockResolvedValueOnce(response(session()))
      .mockImplementationOnce((_path: string, options: RequestInit) => new Promise((_done, reject) => {
        options.signal?.addEventListener("abort", () => reject(new Error("synthetic timeout")));
      }));
    const api = new SessionClient(fetcher as typeof fetch, 100);
    await api.login("manager", "synthetic-only");
    const pending = expect(api.postProjectJobCancel(projectId, id, '"v1"', "synthetic-job-cancel-0001", "reason"))
      .rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    await expect(api.postProjectJobCancel(projectId, id, '"v1"', "synthetic-job-cancel-0001", "reason"))
      .rejects.toMatchObject({ code: "AUTH_CLIENT_BUSY" });
    await vi.advanceTimersByTimeAsync(101);
    await pending;
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(api.canSubmit).toBe(true);
  });

  it("posts only the target Project Member create endpoint with private CSRF and caller key", async () => {
    const created = response({ member_id: id }, 201);
    const { api, fetcher } = client(response(session()), created);
    await api.login("manager", "synthetic-only");
    const body = JSON.stringify({ user_id: id, role: "CUSTOMER_MEMBER", department_id: id });
    await expect(api.postProjectMemberCreate(projectId, body, "synthetic-member-create-0001"))
      .resolves.toBe(created);
    expect(fetcher.mock.calls[1]).toEqual([`/api/v1/projects/${projectId}/members`, expect.objectContaining({
      method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error", body,
      headers: { Accept: "application/json", "Content-Type": "application/json",
        "X-CSRF-Token": token, "Idempotency-Key": "synthetic-member-create-0001" },
    })]);
    expect(JSON.stringify(api)).not.toContain(token);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it.each(["", "../admin", projectId.toUpperCase(), "00000000-0000-0000-0000-000000000000"])(
    "rejects unsafe Project Member path without network: %s", async (target) => {
      const { api, fetcher } = client(response(session()));
      await api.login("manager", "synthetic-only");
      await expect(api.postProjectMemberCreate(target, "{}", "synthetic-member-create-0001"))
        .rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
      expect(fetcher).toHaveBeenCalledTimes(1);
    });

  it.each([["", "synthetic-member-create-0001"], ["x".repeat(8193), "synthetic-member-create-0001"],
    ["{}", "short"]])("rejects unsupported Project Member body or key before network", async (body, key) => {
    const { api, fetcher } = client(response(session()));
    await api.login("manager", "synthetic-only");
    await expect(api.postProjectMemberCreate(projectId, body, key))
      .rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("does not submit Project Member create without fresh in-memory CSRF", async () => {
    const readOnly = session(); delete (readOnly as Partial<typeof readOnly>).csrf_token;
    const { api, fetcher } = client(response(readOnly));
    await api.current();
    await expect(api.postProjectMemberCreate(projectId, "{}", "synthetic-member-create-0001"))
      .rejects.toMatchObject({ code: "AUTH_RELOGIN_REQUIRED" });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("clears Project Member write proof on 401 but retains it on uncertain 503", async () => {
    const { api, fetcher } = client(response(session()), new Response("{}", { status: 503 }),
      new Response("{}", { status: 401 }));
    await api.login("manager", "synthetic-only");
    await api.postProjectMemberCreate(projectId, "{}", "synthetic-member-create-0001");
    expect(api.canSubmit).toBe(true);
    await api.postProjectMemberCreate(projectId, "{}", "synthetic-member-create-0001");
    expect(api.view).toBeNull();
    expect(api.canSubmit).toBe(false);
    expect(fetcher).toHaveBeenCalledTimes(3);
  });

  it("keeps Auth commands exclusive while Project Member create is in flight", async () => {
    let resolve!: (response: Response) => void;
    const fetcher = vi.fn().mockResolvedValueOnce(response(session()))
      .mockReturnValueOnce(new Promise<Response>((done) => { resolve = done; }));
    const api = new SessionClient(fetcher as typeof fetch);
    await api.login("manager", "synthetic-only");
    const pending = api.postProjectMemberCreate(projectId, "{}", "synthetic-member-create-0001");
    await expect(api.renew()).rejects.toMatchObject({ code: "AUTH_CLIENT_BUSY" });
    expect(fetcher).toHaveBeenCalledTimes(2);
    resolve(response({ member_id: id }, 201));
    await pending;
    expect(api.canSubmit).toBe(true);
  });

  it("aborts an uncertain Project Member create timeout once without dropping identity", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn().mockResolvedValueOnce(response(session()))
      .mockImplementationOnce((_path: string, options: RequestInit) => new Promise((_done, reject) => {
        options.signal?.addEventListener("abort", () => reject(new Error("private timeout")));
      }));
    const api = new SessionClient(fetcher as typeof fetch, 100);
    await api.login("manager", "synthetic-only");
    const pending = expect(api.postProjectMemberCreate(projectId, "{}", "synthetic-member-create-0001"))
      .rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    await vi.advanceTimersByTimeAsync(101);
    await pending;
    expect(api.view?.user.user_id).toBe(id);
    expect(api.canSubmit).toBe(true);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("posts only the fixed Project Department endpoint with private CSRF and original key", async () => {
    const created = response({ department_id: id }, 201);
    const { api, fetcher } = client(response(session()), created);
    await api.login("manager", "synthetic-only");
    const body = JSON.stringify({ code: "RD", name: "研发部" });
    await expect(api.postProjectDepartmentCreate(projectId, body, "synthetic-department-0001"))
      .resolves.toBe(created);
    expect(fetcher.mock.calls[1]).toEqual([`/api/v1/projects/${projectId}/departments`, expect.objectContaining({
      method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error", body,
      headers: { Accept: "application/json", "Content-Type": "application/json",
        "X-CSRF-Token": token, "Idempotency-Key": "synthetic-department-0001" },
    })]);
    expect(JSON.stringify(api)).not.toContain(token);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it.each(["", "../admin", projectId.toUpperCase(), "00000000-0000-0000-0000-000000000000"])(
    "rejects unsafe Project Department path without network: %s", async (target) => {
      const { api, fetcher } = client(response(session()));
      await api.login("manager", "synthetic-only");
      await expect(api.postProjectDepartmentCreate(target, "{}", "synthetic-department-0001"))
        .rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
      expect(fetcher).toHaveBeenCalledTimes(1);
    });

  it.each([["", "synthetic-department-0001"], ["x".repeat(8193), "synthetic-department-0001"],
    ["{}", "short"]])("rejects bad Project Department body or key before network", async (body, key) => {
    const { api, fetcher } = client(response(session()));
    await api.login("manager", "synthetic-only");
    await expect(api.postProjectDepartmentCreate(projectId, body, key))
      .rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("requires an in-memory CSRF proof for Project Department creation", async () => {
    const readOnly = session(); delete (readOnly as Partial<typeof readOnly>).csrf_token;
    const { api, fetcher } = client(response(readOnly));
    await api.current();
    await expect(api.postProjectDepartmentCreate(projectId, "{}", "synthetic-department-0001"))
      .rejects.toMatchObject({ code: "AUTH_RELOGIN_REQUIRED" });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("clears Department write proof on 401 but retains it on uncertain 503", async () => {
    const { api, fetcher } = client(response(session()), new Response("{}", { status: 503 }),
      new Response("{}", { status: 401 }));
    await api.login("manager", "synthetic-only");
    await api.postProjectDepartmentCreate(projectId, "{}", "synthetic-department-0001");
    expect(api.canSubmit).toBe(true);
    await api.postProjectDepartmentCreate(projectId, "{}", "synthetic-department-0001");
    expect(api.view).toBeNull();
    expect(api.canSubmit).toBe(false);
    expect(fetcher).toHaveBeenCalledTimes(3);
  });

  it("keeps Auth operations exclusive while Department create is pending", async () => {
    let resolve!: (response: Response) => void;
    const fetcher = vi.fn().mockResolvedValueOnce(response(session()))
      .mockReturnValueOnce(new Promise<Response>((done) => { resolve = done; }));
    const api = new SessionClient(fetcher as typeof fetch);
    await api.login("manager", "synthetic-only");
    const pending = api.postProjectDepartmentCreate(projectId, "{}", "synthetic-department-0001");
    await expect(api.renew()).rejects.toMatchObject({ code: "AUTH_CLIENT_BUSY" });
    resolve(response({ department_id: id }, 201));
    await pending;
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("aborts an uncertain Department create timeout once without dropping identity", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn().mockResolvedValueOnce(response(session()))
      .mockImplementationOnce((_path: string, options: RequestInit) => new Promise((_done, reject) => {
        options.signal?.addEventListener("abort", () => reject(new Error("private timeout")));
      }));
    const api = new SessionClient(fetcher as typeof fetch, 100);
    await api.login("manager", "synthetic-only");
    const pending = expect(api.postProjectDepartmentCreate(projectId, "{}", "synthetic-department-0001"))
      .rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    await vi.advanceTimersByTimeAsync(101);
    await pending;
    expect(api.view?.user.user_id).toBe(id);
    expect(api.canSubmit).toBe(true);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("posts only the fixed Admin User create endpoint with private CSRF and caller key", async () => {
    const created = response({ user_id: id }, 201);
    const { api, fetcher } = client(response(session()), created);
    await api.login("user", "synthetic-only");
    const body = JSON.stringify({ username: "Synthetic Manager", password: "synthetic-password" });
    await expect(api.postAdminUserCreate(body, "synthetic-user-create-0001")).resolves.toBe(created);
    expect(fetcher.mock.calls[1]).toEqual(["/api/v1/admin/users", expect.objectContaining({
      method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error", body,
      headers: { Accept: "application/json", "Content-Type": "application/json",
        "X-CSRF-Token": token, "Idempotency-Key": "synthetic-user-create-0001" },
    })]);
    expect(JSON.stringify(api)).not.toContain(token);
    expect(JSON.stringify(api)).not.toContain("synthetic-password");
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("does not submit Admin User create without fresh in-memory CSRF", async () => {
    const readOnly = session(); delete (readOnly as Partial<typeof readOnly>).csrf_token;
    const { api, fetcher } = client(response(readOnly));
    await expect(api.postAdminUserCreate("{}", "synthetic-user-create-0001"))
      .rejects.toMatchObject({ code: "AUTH_RELOGIN_REQUIRED" });
    await api.current();
    await expect(api.postAdminUserCreate("{}", "synthetic-user-create-0001"))
      .rejects.toMatchObject({ code: "AUTH_RELOGIN_REQUIRED" });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it.each(["", "x".repeat(16_385)])("rejects unsupported Admin User body size before network", async (body) => {
    const { api, fetcher } = client(response(session()));
    await api.login("user", "synthetic-only");
    await expect(api.postAdminUserCreate(body, "synthetic-user-create-0001"))
      .rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("clears Admin User write proof on 401 but retains it on uncertain 503", async () => {
    const { api, fetcher } = client(response(session()), new Response("{}", { status: 503 }),
      new Response("{}", { status: 401 }));
    await api.login("user", "synthetic-only");
    await api.postAdminUserCreate("{}", "synthetic-user-create-0001");
    expect(api.canSubmit).toBe(true);
    await api.postAdminUserCreate("{}", "synthetic-user-create-0001");
    expect(api.view).toBeNull();
    expect(api.canSubmit).toBe(false);
    expect(fetcher).toHaveBeenCalledTimes(3);
  });

  it("holds Auth exclusivity during Admin User create", async () => {
    let resolve!: (response: Response) => void;
    const fetcher = vi.fn().mockResolvedValueOnce(response(session()))
      .mockReturnValueOnce(new Promise<Response>((done) => { resolve = done; }));
    const api = new SessionClient(fetcher as typeof fetch);
    await api.login("user", "synthetic-only");
    const pending = api.postAdminUserCreate("{}", "synthetic-user-create-0001");
    await expect(api.postProjectCreate("{}", "synthetic-project-0001"))
      .rejects.toMatchObject({ code: "AUTH_CLIENT_BUSY" });
    expect(fetcher).toHaveBeenCalledTimes(2);
    resolve(response({ user_id: id }, 201));
    await pending;
    expect(api.canSubmit).toBe(true);
  });

  it("aborts Admin User create timeout once without rotating identity", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn().mockResolvedValueOnce(response(session()))
      .mockImplementationOnce((_path: string, options: RequestInit) => new Promise((_done, reject) => {
        options.signal?.addEventListener("abort", () => reject(new Error("private transport failure")));
      }));
    const api = new SessionClient(fetcher as typeof fetch, 100);
    await api.login("user", "synthetic-only");
    const pending = expect(api.postAdminUserCreate("{}", "synthetic-user-create-0001"))
      .rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    await vi.advanceTimersByTimeAsync(101);
    await pending;
    expect(api.view?.user.user_id).toBe(id);
    expect(api.canSubmit).toBe(true);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it.each(["enable", "disable"])("posts only the frozen %s User state command with an empty body", async (action) => {
    const result = response({ user_id: id, account_state: action === "enable" ? "ENABLED" : "DISABLED" });
    const { api, fetcher } = client(response(session()), result);
    await api.login("admin", "synthetic-only");
    await expect(api.postAdminUserState(id, action as "enable" | "disable", '"v17"',
      "synthetic-user-state-0001")).resolves.toBe(result);
    expect(fetcher.mock.calls[1]).toEqual([`/api/v1/admin/users/${id}:${action}`, {
      method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error",
      headers: { Accept: "application/json", "X-CSRF-Token": token,
        "Idempotency-Key": "synthetic-user-state-0001", "If-Match": '"v17"' },
      signal: expect.any(AbortSignal),
    }]);
    expect(api.canSubmit).toBe(true);
    expect(JSON.stringify(api)).not.toContain(token);
  });

  it("rejects invalid User state path, version, action and key without network", async () => {
    const { api, fetcher } = client(response(session()));
    await api.login("admin", "synthetic-only");
    const invalid: Array<[string, "enable" | "disable", string, string]> = [
      ["../other", "disable", '"v1"', "synthetic-user-state-0001"],
      [id, "delete" as "disable", '"v1"', "synthetic-user-state-0001"],
      [id, "enable", 'W/"v1"', "synthetic-user-state-0001"],
      [id, "enable", '"v00"', "synthetic-user-state-0001"],
      [id, "enable", '"v9007199254740992"', "synthetic-user-state-0001"],
      [id, "enable", '"v9007199254740991"', "synthetic-user-state-0001"],
      [id, "enable", '"v1"', "short"],
    ];
    for (const args of invalid) {
      await expect(api.postAdminUserState(...args)).rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    }
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("requires a fresh CSRF token for User state commands", async () => {
    const readOnly = session(); delete (readOnly as Partial<typeof readOnly>).csrf_token;
    const { api, fetcher } = client(response(readOnly));
    await api.current();
    await expect(api.postAdminUserState(id, "disable", '"v1"', "synthetic-user-state-0001"))
      .rejects.toMatchObject({ code: "AUTH_RELOGIN_REQUIRED" });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("keeps original write proof on uncertain User state result but clears it on 401", async () => {
    const { api, fetcher } = client(response(session()), new Response("{}", { status: 503 }),
      new Response("{}", { status: 401 }));
    await api.login("admin", "synthetic-only");
    await api.postAdminUserState(id, "disable", '"v1"', "synthetic-user-state-0001");
    expect(api.canSubmit).toBe(true);
    await api.postAdminUserState(id, "disable", '"v1"', "synthetic-user-state-0001");
    expect(api.view).toBeNull();
    expect(api.canSubmit).toBe(false);
    expect(fetcher).toHaveBeenCalledTimes(3);
  });

  it("allows no overlapping Auth command and never retries timed-out User state POST", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn().mockResolvedValueOnce(response(session()))
      .mockImplementationOnce((_path: string, options: RequestInit) => new Promise((_done, reject) => {
        options.signal?.addEventListener("abort", () => reject(new Error("synthetic timeout")));
      }));
    const api = new SessionClient(fetcher as typeof fetch, 100);
    await api.login("admin", "synthetic-only");
    const pending = expect(api.postAdminUserState(id, "disable", '"v1"', "synthetic-user-state-0001"))
      .rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    await expect(api.postProjectCreate("{}", "synthetic-project-0001"))
      .rejects.toMatchObject({ code: "AUTH_CLIENT_BUSY" });
    await vi.advanceTimersByTimeAsync(101);
    await pending;
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(api.canSubmit).toBe(true);
  });

  it("sends only the frozen User name PATCH with initial v0 and private CSRF", async () => {
    const reply = response({ user_id: id, username_display: "新名称" });
    const { api, fetcher } = client(response(session()), reply);
    await api.login("admin", "synthetic-only");
    await expect(api.patchAdminUserName(id, '"v0"', "新名称")).resolves.toBe(reply);
    expect(fetcher.mock.calls[1]).toEqual([`/api/v1/admin/users/${id}`, {
      method: "PATCH", credentials: "same-origin", cache: "no-store", redirect: "error",
      headers: { Accept: "application/json", "Content-Type": "application/json",
        "X-CSRF-Token": token, "If-Match": '"v0"' },
      body: JSON.stringify({ username: "新名称" }), signal: expect.any(AbortSignal),
    }]);
    expect(api.canSubmit).toBe(true);
    expect(JSON.stringify(api)).not.toContain(token);
  });

  it("rejects malformed User name PATCH input without network", async () => {
    const { api, fetcher } = client(response(session()));
    await api.login("admin", "synthetic-only");
    for (const [target, version, name] of [
      ["../other", '"v0"', "新名称"], [id, 'W/"v0"', "新名称"],
      [id, '"v00"', "新名称"], [id, '"v9007199254740991"', "新名称"],
      [id, '"v0"', "  "], [id, '"v0"', "a".repeat(256)],
    ]) {
      await expect(api.patchAdminUserName(target, version, name))
        .rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    }
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("requires a fresh write proof and clears it on User name PATCH 401", async () => {
    const readOnly = session(); delete (readOnly as Partial<typeof readOnly>).csrf_token;
    const { api: viewer, fetcher: viewerFetcher } = client(response(readOnly));
    await viewer.current();
    await expect(viewer.patchAdminUserName(id, '"v0"', "新名称"))
      .rejects.toMatchObject({ code: "AUTH_RELOGIN_REQUIRED" });
    expect(viewerFetcher).toHaveBeenCalledTimes(1);
    const { api, fetcher } = client(response(session()), new Response("{}", { status: 401 }));
    await api.login("admin", "synthetic-only");
    await expect(api.patchAdminUserName(id, '"v0"', "新名称")).resolves.toHaveProperty("status", 401);
    expect(api.view).toBeNull();
    expect(api.canSubmit).toBe(false);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("does not retry an uncertain timed-out name PATCH or start a second command", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn().mockResolvedValueOnce(response(session()))
      .mockImplementationOnce((_path: string, options: RequestInit) => new Promise((_done, reject) => {
        options.signal?.addEventListener("abort", () => reject(new Error("synthetic timeout")));
      }));
    const api = new SessionClient(fetcher as typeof fetch, 100);
    await api.login("admin", "synthetic-only");
    const pending = expect(api.patchAdminUserName(id, '"v0"', "新名称"))
      .rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    await expect(api.postProjectCreate("{}", "synthetic-project-0001"))
      .rejects.toMatchObject({ code: "AUTH_CLIENT_BUSY" });
    await vi.advanceTimersByTimeAsync(101);
    await pending;
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(api.canSubmit).toBe(true);
  });

  it("sends only the frozen member PATCH path with v0, private CSRF and no idempotency key", async () => {
    const body = JSON.stringify({ role: "CUSTOMER_MEMBER", department_id: id });
    const reply = response({ member_id: id });
    const { api, fetcher } = client(response(session()), reply);
    await api.login("manager", "synthetic-only");
    await expect(api.patchProjectMember(projectId, id, '"v0"', body)).resolves.toBe(reply);
    expect(fetcher.mock.calls[1]).toEqual([`/api/v1/projects/${projectId}/members/${id}`, {
      method: "PATCH", credentials: "same-origin", cache: "no-store", redirect: "error",
      headers: { Accept: "application/json", "Content-Type": "application/json",
        "X-CSRF-Token": token, "If-Match": '"v0"' }, body, signal: expect.any(AbortSignal),
    }]);
    expect(JSON.stringify(api)).not.toContain(token);
  });

  it("rejects unsafe member PATCH path, version or body without network", async () => {
    const { api, fetcher } = client(response(session()));
    await api.login("manager", "synthetic-only");
    for (const [project, member, version, body] of [
      ["../admin", id, '"v0"', "{}"], [projectId, "../other", '"v0"', "{}"],
      [projectId, id, 'W/"v0"', "{}"], [projectId, id, '"v00"', "{}"],
      [projectId, id, '"v9007199254740991"', "{}"], [projectId, id, '"v0"', ""],
      [projectId, id, '"v0"', "x".repeat(8193)],
    ]) {
      await expect(api.patchProjectMember(project, member, version, body))
        .rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    }
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("requires fresh CSRF and clears it on member PATCH 401 but not on 503", async () => {
    const readOnly = session(); delete (readOnly as Partial<typeof readOnly>).csrf_token;
    const { api: viewer, fetcher: viewerFetcher } = client(response(readOnly));
    await viewer.current();
    await expect(viewer.patchProjectMember(projectId, id, '"v0"', "{}"))
      .rejects.toMatchObject({ code: "AUTH_RELOGIN_REQUIRED" });
    expect(viewerFetcher).toHaveBeenCalledTimes(1);
    const { api, fetcher } = client(response(session()), new Response("{}", { status: 503 }),
      new Response("{}", { status: 401 }));
    await api.login("manager", "synthetic-only");
    await api.patchProjectMember(projectId, id, '"v0"', "{}");
    expect(api.canSubmit).toBe(true);
    await api.patchProjectMember(projectId, id, '"v0"', "{}");
    expect(api.canSubmit).toBe(false);
    expect(api.view).toBeNull();
    expect(fetcher).toHaveBeenCalledTimes(3);
  });

  it("does not retry a timed-out member PATCH or overlap an Auth command", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn().mockResolvedValueOnce(response(session()))
      .mockImplementationOnce((_path: string, options: RequestInit) => new Promise((_done, reject) => {
        options.signal?.addEventListener("abort", () => reject(new Error("synthetic timeout")));
      }));
    const api = new SessionClient(fetcher as typeof fetch, 100);
    await api.login("manager", "synthetic-only");
    const pending = expect(api.patchProjectMember(projectId, id, '"v0"', "{}"))
      .rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    await expect(api.postProjectCreate("{}", "synthetic-project-0001"))
      .rejects.toMatchObject({ code: "AUTH_CLIENT_BUSY" });
    await vi.advanceTimersByTimeAsync(101);
    await pending;
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(api.canSubmit).toBe(true);
  });

  it("sends only the frozen department PATCH path with v0, private CSRF and no idempotency key", async () => {
    const body = JSON.stringify({ name: "更新部门" });
    const reply = response({ department_id: id });
    const { api, fetcher } = client(response(session()), reply);
    await api.login("manager", "synthetic-only");
    await expect(api.patchProjectDepartment(projectId, id, '"v0"', body)).resolves.toBe(reply);
    expect(fetcher.mock.calls[1]).toEqual([`/api/v1/projects/${projectId}/departments/${id}`, {
      method: "PATCH", credentials: "same-origin", cache: "no-store", redirect: "error",
      headers: { Accept: "application/json", "Content-Type": "application/json",
        "X-CSRF-Token": token, "If-Match": '"v0"' }, body, signal: expect.any(AbortSignal),
    }]);
    expect(JSON.stringify(api)).not.toContain(token);
  });

  it("rejects unsafe department PATCH path, version or body without network", async () => {
    const { api, fetcher } = client(response(session()));
    await api.login("manager", "synthetic-only");
    for (const [project, department, version, body] of [
      ["../admin", id, '"v0"', "{}"], [projectId, "../other", '"v0"', "{}"],
      [projectId, id, 'W/"v0"', "{}"], [projectId, id, '"v00"', "{}"],
      [projectId, id, '"v9007199254740991"', "{}"], [projectId, id, '"v0"', ""],
      [projectId, id, '"v0"', "x".repeat(8193)],
    ]) {
      await expect(api.patchProjectDepartment(project, department, version, body))
        .rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    }
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("requires CSRF and clears department PATCH proof on 401, not 503", async () => {
    const readOnly = session(); delete (readOnly as Partial<typeof readOnly>).csrf_token;
    const { api: viewer, fetcher: viewerFetcher } = client(response(readOnly));
    await viewer.current();
    await expect(viewer.patchProjectDepartment(projectId, id, '"v0"', "{}"))
      .rejects.toMatchObject({ code: "AUTH_RELOGIN_REQUIRED" });
    expect(viewerFetcher).toHaveBeenCalledTimes(1);
    const { api, fetcher } = client(response(session()), new Response("{}", { status: 503 }),
      new Response("{}", { status: 401 }));
    await api.login("manager", "synthetic-only");
    await api.patchProjectDepartment(projectId, id, '"v0"', "{}");
    expect(api.canSubmit).toBe(true);
    await api.patchProjectDepartment(projectId, id, '"v0"', "{}");
    expect(api.canSubmit).toBe(false);
    expect(api.view).toBeNull();
    expect(fetcher).toHaveBeenCalledTimes(3);
  });

  it("does not retry a timed-out department PATCH or overlap another command", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn().mockResolvedValueOnce(response(session()))
      .mockImplementationOnce((_path: string, options: RequestInit) => new Promise((_done, reject) => {
        options.signal?.addEventListener("abort", () => reject(new Error("synthetic timeout")));
      }));
    const api = new SessionClient(fetcher as typeof fetch, 100);
    await api.login("manager", "synthetic-only");
    const pending = expect(api.patchProjectDepartment(projectId, id, '"v0"', "{}"))
      .rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    await expect(api.postProjectCreate("{}", "synthetic-project-0001"))
      .rejects.toMatchObject({ code: "AUTH_CLIENT_BUSY" });
    await vi.advanceTimersByTimeAsync(101);
    await pending;
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(api.canSubmit).toBe(true);
  });

  it("sends exact empty-body department deactivation with original v0 and Key", async () => {
    const key = "synthetic-department-deactivate-0001";
    const reply = response({ department_id: id });
    const { api, fetcher } = client(response(session()), reply);
    await api.login("manager", "synthetic-only");
    await expect(api.postProjectDepartmentDeactivate(projectId, id, '"v0"', key)).resolves.toBe(reply);
    expect(fetcher.mock.calls[1]).toEqual([`/api/v1/projects/${projectId}/departments/${id}:deactivate`, {
      method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error",
      headers: { Accept: "application/json", "X-CSRF-Token": token,
        "Idempotency-Key": key, "If-Match": '"v0"' }, signal: expect.any(AbortSignal),
    }]);
    expect(JSON.stringify(api)).not.toContain(token);
  });

  it("rejects unsafe department deactivation identifiers, version and Key before network", async () => {
    const { api, fetcher } = client(response(session()));
    await api.login("manager", "synthetic-only");
    const key = "synthetic-department-deactivate-0001";
    for (const [project, department, etag, attemptKey] of [
      ["../admin", id, '"v0"', key], [projectId, "../other", '"v0"', key],
      [projectId, id, 'W/"v0"', key], [projectId, id, '"v00"', key],
      [projectId, id, '"v9007199254740991"', key], [projectId, id, '"v0"', "short"],
      [projectId, id, '"v0"', "x".repeat(129)], [projectId, id, '"v0"', "x".repeat(15) + "\n"],
    ]) {
      await expect(api.postProjectDepartmentDeactivate(project, department, etag, attemptKey))
        .rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    }
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("requires write proof and clears it only on deactivation 401", async () => {
    const readOnly = session(); delete (readOnly as Partial<typeof readOnly>).csrf_token;
    const { api: viewer, fetcher: viewerFetcher } = client(response(readOnly));
    await viewer.current();
    await expect(viewer.postProjectDepartmentDeactivate(projectId, id, '"v0"', "synthetic-department-deactivate-0001"))
      .rejects.toMatchObject({ code: "AUTH_RELOGIN_REQUIRED" });
    expect(viewerFetcher).toHaveBeenCalledTimes(1);
    const { api, fetcher } = client(response(session()), new Response("{}", { status: 503 }),
      new Response("{}", { status: 401 }));
    await api.login("manager", "synthetic-only");
    await api.postProjectDepartmentDeactivate(projectId, id, '"v0"', "synthetic-department-deactivate-0001");
    expect(api.canSubmit).toBe(true);
    await api.postProjectDepartmentDeactivate(projectId, id, '"v0"', "synthetic-department-deactivate-0001");
    expect(api.canSubmit).toBe(false);
    expect(api.view).toBeNull();
    expect(fetcher).toHaveBeenCalledTimes(3);
  });

  it("does not retry a timed-out department deactivation or overlap another command", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn().mockResolvedValueOnce(response(session()))
      .mockImplementationOnce((_path: string, options: RequestInit) => new Promise((_done, reject) => {
        options.signal?.addEventListener("abort", () => reject(new Error("synthetic timeout")));
      }));
    const api = new SessionClient(fetcher as typeof fetch, 100);
    await api.login("manager", "synthetic-only");
    const pending = expect(api.postProjectDepartmentDeactivate(projectId, id, '"v0"',
      "synthetic-department-deactivate-0001")).rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    await expect(api.postProjectCreate("{}", "synthetic-project-0001"))
      .rejects.toMatchObject({ code: "AUTH_CLIENT_BUSY" });
    await vi.advanceTimersByTimeAsync(101);
    await pending;
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(api.canSubmit).toBe(true);
  });

  it.each(["suspend", "resume", "remove"] as const)("sends exact empty-body member %s command", async (action) => {
    const key = "synthetic-member-state-0001";
    const reply = response({ member_id: id });
    const { api, fetcher } = client(response(session()), reply);
    await api.login("manager", "synthetic-only");
    await expect(api.postProjectMemberState(projectId, id, action, '"v0"', key)).resolves.toBe(reply);
    expect(fetcher.mock.calls[1]).toEqual([`/api/v1/projects/${projectId}/members/${id}:${action}`, {
      method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error",
      headers: { Accept: "application/json", "X-CSRF-Token": token,
        "Idempotency-Key": key, "If-Match": '"v0"' }, signal: expect.any(AbortSignal),
    }]);
    expect(JSON.stringify(api)).not.toContain(token);
  });

  it("rejects unsafe member state path, action, version and key without network", async () => {
    const { api, fetcher } = client(response(session()));
    await api.login("manager", "synthetic-only");
    const key = "synthetic-member-state-0001";
    for (const [project, member, action, etag, attemptKey] of [
      ["../admin", id, "suspend", '"v0"', key], [projectId, "../other", "resume", '"v0"', key],
      [projectId, id, "delete", '"v0"', key], [projectId, id, "remove", 'W/"v0"', key],
      [projectId, id, "suspend", '"v00"', key],
      [projectId, id, "suspend", '"v9007199254740991"', key],
      [projectId, id, "suspend", '"v0"', "short"],
    ]) {
      await expect(api.postProjectMemberState(project, member,
        action as "suspend", etag, attemptKey)).rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    }
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("requires fresh CSRF and clears member state proof on 401 but not 503", async () => {
    const readOnly = session(); delete (readOnly as Partial<typeof readOnly>).csrf_token;
    const { api: viewer, fetcher: viewerFetcher } = client(response(readOnly));
    await viewer.current();
    await expect(viewer.postProjectMemberState(projectId, id, "suspend", '"v0"', "synthetic-member-state-0001"))
      .rejects.toMatchObject({ code: "AUTH_RELOGIN_REQUIRED" });
    expect(viewerFetcher).toHaveBeenCalledTimes(1);
    const { api, fetcher } = client(response(session()), new Response("{}", { status: 503 }),
      new Response("{}", { status: 401 }));
    await api.login("manager", "synthetic-only");
    await api.postProjectMemberState(projectId, id, "suspend", '"v0"', "synthetic-member-state-0001");
    expect(api.canSubmit).toBe(true);
    await api.postProjectMemberState(projectId, id, "suspend", '"v0"', "synthetic-member-state-0001");
    expect(api.canSubmit).toBe(false);
    expect(api.view).toBeNull();
    expect(fetcher).toHaveBeenCalledTimes(3);
  });

  it("does not retry timed-out member state command or overlap another write", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn().mockResolvedValueOnce(response(session()))
      .mockImplementationOnce((_path: string, options: RequestInit) => new Promise((_done, reject) => {
        options.signal?.addEventListener("abort", () => reject(new Error("synthetic timeout")));
      }));
    const api = new SessionClient(fetcher as typeof fetch, 100);
    await api.login("manager", "synthetic-only");
    const pending = expect(api.postProjectMemberState(projectId, id, "remove", '"v0"',
      "synthetic-member-state-0001")).rejects.toMatchObject({ code: "AUTH_CLIENT_UNAVAILABLE" });
    await expect(api.postProjectCreate("{}", "synthetic-project-0001"))
      .rejects.toMatchObject({ code: "AUTH_CLIENT_BUSY" });
    await vi.advanceTimersByTimeAsync(101);
    await pending;
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(api.canSubmit).toBe(true);
  });
});
