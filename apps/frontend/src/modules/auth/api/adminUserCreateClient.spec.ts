import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionClient } from "./sessionClient";
import { AdminUserCreateClient, AdminUserCreateError, type AdminUserCreateInput } from "./adminUserCreateClient";

const adminId = "01234567-89ab-4cde-8123-456789abcdef";
const userId = "11234567-89ab-4cde-8123-456789abcdef";
const key = "synthetic-user-create-0001";
const input: AdminUserCreateInput = { username: " 测试负责人 ", password: "synthetic-initial-password" };
const created = { user_id: userId, username_display: "测试负责人", account_state: "ENABLED",
  deployment_role: "NONE", credential_version: 1, created_at: "2026-09-28T08:30:00.123456Z",
  updated_at: "2026-09-28T08:30:00.123456Z", etag: '"v1"' };
function response(data: unknown, status = 201, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify({ data, trace_id: adminId }), { status,
    headers: { "Content-Type": "application/json", ETag: '"v1"',
      Location: `/api/v1/admin/users/${userId}`, ...headers } });
}
function failure(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: "private server details" }, trace_id: adminId }),
    { status, headers: { "Content-Type": "application/json" } });
}
function auth(replies: Response[]) {
  const login = response({ user: { user_id: adminId, username_display: "Synthetic Admin" },
    deployment_role: "DEPLOYMENT_ADMIN", password_change_required: false, authorized_projects: [],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64) }, 200);
  const fetcher = vi.fn();
  for (const reply of [login, ...replies]) fetcher.mockResolvedValueOnce(reply);
  const session = new SessionClient(fetcher as typeof fetch);
  return { session, api: new AdminUserCreateClient(session), fetcher };
}

describe("AdminUserCreateClient", () => {
  afterEach(() => vi.restoreAllMocks());

  it("posts one normalized write-only password and exposes only safe immutable metadata", async () => {
    const { session, api, fetcher } = auth([response({ ...created, password: "server-secret",
      password_hash: "private-hash", username_normalized: "private" })]);
    await session.login("Synthetic Admin", "synthetic-only");
    const view = await api.create(input, key);
    expect(fetcher.mock.calls[1]).toEqual(["/api/v1/admin/users", expect.objectContaining({
      method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error",
      body: JSON.stringify({ username: "测试负责人", password: "synthetic-initial-password" }),
      headers: { Accept: "application/json", "Content-Type": "application/json",
        "X-CSRF-Token": "a".repeat(64), "Idempotency-Key": key },
    })]);
    expect(view).toEqual(created);
    expect(Object.isFrozen(view)).toBe(true);
    expect(JSON.stringify(view)).not.toContain("password");
    expect(JSON.stringify(api)).not.toContain(input.password);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("normalizes the display name using NFC without inventing a canonical casefold", async () => {
    const { session, api, fetcher } = auth([response({ ...created, username_display: "Café" })]);
    await session.login("Synthetic Admin", "synthetic-only");
    await api.create({ username: " Cafe\u0301 ", password: "synthetic-only" }, key);
    expect(JSON.parse(fetcher.mock.calls[1][1].body)).toEqual({ username: "Café", password: "synthetic-only" });
  });

  it.each([{ ...input, username: "" }, { ...input, username: "x".repeat(256) },
    { ...input, username: "a\u0000" }, { ...input, password: "" },
    { ...input, password: "a\0b" }, { ...input, password: "界".repeat(342) }])(
    "rejects invalid input before any network call %j", async (bad) => {
      const { api, fetcher } = auth([]);
      await expect(api.create(bad, key)).rejects.toMatchObject({ code: "USER_CREATE_INVALID_INPUT", uncertain: false });
      expect(fetcher).not.toHaveBeenCalled();
    });

  it("rejects invalid key and read-only session without a create request", async () => {
    const readOnly = { user: { user_id: adminId, username_display: "Synthetic Admin" },
      deployment_role: "DEPLOYMENT_ADMIN", password_change_required: false, authorized_projects: [],
      absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z" };
    const { session, api, fetcher } = auth([response(readOnly, 200)]);
    await session.login("Synthetic Admin", "synthetic-only");
    await expect(api.create(input, "short")).rejects.toMatchObject({ code: "USER_CREATE_INVALID_INPUT" });
    await session.current();
    await expect(api.create(input, key)).rejects.toMatchObject({ code: "AUTH_RELOGIN_REQUIRED", uncertain: false });
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it.each([[401, "AUTH_SESSION_EXPIRED"], [403, "AUTH_CSRF_INVALID"],
    [403, "LICENSE_OPERATION_DENIED"], [404, "RESOURCE_NOT_FOUND"],
    [409, "CONFLICT_DUPLICATE"], [409, "CONFLICT_IDEMPOTENCY"]] as const)(
    "maps definite status/code %s %s without private details", async (status, code) => {
      const { session, api, fetcher } = auth([failure(status, code)]);
      await session.login("Synthetic Admin", "synthetic-only");
      const error = await api.create(input, key).catch((value: unknown) => value);
      expect(error).toBeInstanceOf(AdminUserCreateError);
      if (!(error instanceof AdminUserCreateError)) throw new Error("expected safe create error");
      expect(error.code).toBe(code);
      expect(error.uncertain).toBe(false);
      expect(String(error)).not.toContain("private");
      expect(fetcher).toHaveBeenCalledTimes(2);
    });

  it.each([[400, "REQUEST_MALFORMED"], [422, "VALIDATION_FAILED"]] as const)(
    "maps server validation rejection %s %s", async (status, code) => {
      const { session, api } = auth([failure(status, code)]);
      await session.login("Synthetic Admin", "synthetic-only");
      await expect(api.create(input, key)).rejects.toMatchObject({ code: "USER_CREATE_INVALID_INPUT", uncertain: false });
    });

  it.each([failure(503, "SYSTEM_UNAVAILABLE"), failure(403, "UNKNOWN"),
    response({ ...created, account_state: "DISABLED" }),
    response({ ...created, deployment_role: "DEPLOYMENT_ADMIN" }),
    response({ ...created, credential_version: 2 }),
    response({ ...created, username_display: "different" }),
    response({ ...created, created_at: "2026-09-28T08:30:00+08:00" }),
    response({ ...created, updated_at: "2026-09-28T08:29:00Z" }),
    response({ ...created, etag: '"v2"' }),
    response(created, 201, { ETag: '"v2"' }),
    response(created, 201, { Location: "/api/v1/admin/users/other" }),
    new Response("not-json", { status: 201, headers: { "Content-Type": "application/json" } }),
  ])("treats malformed or unknown result as potentially committed without retry", async (raw) => {
    const { session, api, fetcher } = auth([raw]);
    await session.login("Synthetic Admin", "synthetic-only");
    await expect(api.create(input, key)).rejects.toMatchObject({ code: "USER_CREATE_UNCERTAIN", uncertain: true });
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("treats transport loss as uncertain and retains only caller-owned recovery details", async () => {
    const { session, api, fetcher } = auth([]);
    await session.login("Synthetic Admin", "synthetic-only");
    fetcher.mockRejectedValueOnce(new Error("private network failure"));
    await expect(api.create(input, key)).rejects.toMatchObject({ code: "USER_CREATE_UNCERTAIN", uncertain: true });
    expect(session.canSubmit).toBe(true);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
});
