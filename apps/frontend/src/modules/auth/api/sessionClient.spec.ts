import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionClient, SessionClientError } from "./sessionClient";

const id = "01234567-89ab-4cde-8123-456789abcdef";
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
});
