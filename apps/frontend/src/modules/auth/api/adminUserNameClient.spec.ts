import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionClient } from "./sessionClient";
import { AdminUserNameClient, AdminUserNameError } from "./adminUserNameClient";

const adminId = "01234567-89ab-4cde-8123-456789abcdef";
const userId = "11234567-89ab-4cde-8123-456789abcdef";
const before = { user_id: userId, username_display: "旧名称", account_state: "ENABLED" as const,
  deployment_role: "NONE" as const, credential_version: 1,
  created_at: "2026-09-28T08:30:00Z", updated_at: "2026-09-28T09:30:00Z", etag: '"v0"' };
const after = { ...before, username_display: "新名称", updated_at: "2026-09-28T10:00:00Z", etag: '"v1"' };
function reply(data: unknown, status = 200, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify({ data, trace_id: adminId }), { status,
    headers: { "Content-Type": "application/json", ETag: '"v1"', ...headers } });
}
function failure(status: number, code: string) {
  return new Response(JSON.stringify({ error: { code, message: "private SQL" }, trace_id: adminId }),
    { status, headers: { "Content-Type": "application/json" } });
}
async function setup(responses: Response[]) {
  const login = reply({ user: { user_id: adminId, username_display: "管理员" },
    deployment_role: "DEPLOYMENT_ADMIN", password_change_required: false, authorized_projects: [],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64) });
  const fetcher = vi.fn();
  for (const response of [login, ...responses]) fetcher.mockResolvedValueOnce(response);
  const session = new SessionClient(fetcher as typeof fetch);
  await session.login("admin", "synthetic-only");
  return { api: new AdminUserNameClient(session), fetcher, session };
}

describe("AdminUserNameClient", () => {
  afterEach(() => vi.restoreAllMocks());

  it("accepts a bound v0-to-v1 rename and strips private server fields", async () => {
    const { api, fetcher } = await setup([reply({ ...after, password_hash: "private" })]);
    const result = await api.change(before, "  新名称  ");
    expect(result).toEqual(after);
    expect(Object.isFrozen(result)).toBe(true);
    expect(JSON.stringify(result)).not.toContain("private");
    expect(fetcher.mock.calls[1][0]).toBe(`/api/v1/admin/users/${userId}`);
    expect(fetcher.mock.calls[1][1].headers["If-Match"]).toBe('"v0"');
    expect(fetcher.mock.calls[1][1].body).toBe(JSON.stringify({ username: "新名称" }));
  });

  it("accepts a true no-op without inventing a version or audit event", async () => {
    const { api } = await setup([reply(before, 200, { ETag: '"v0"' })]);
    await expect(api.change(before, "旧名称")).resolves.toEqual(before);
  });

  it.each([[401, "AUTH_SESSION_EXPIRED"], [403, "AUTH_CSRF_INVALID"],
    [403, "LICENSE_OPERATION_DENIED"], [404, "RESOURCE_NOT_FOUND"],
    [409, "CONFLICT_VERSION"], [409, "CONFLICT_DUPLICATE"]] as const)(
    "maps only exact %s %s as a definite rejection", async (status, code) => {
      const { api } = await setup([failure(status, code)]);
      const error = await api.change(before, "新名称").catch((value: unknown) => value);
      expect(error).toBeInstanceOf(AdminUserNameError);
      expect(error).toMatchObject({ code, uncertain: false });
      expect(String(error)).not.toContain("private SQL");
    });

  it.each([[400, "REQUEST_MALFORMED"], [422, "VALIDATION_FAILED"],
    [428, "CONFLICT_VERSION_REQUIRED"]] as const)(
    "maps known input rejection %s %s", async (status, code) => {
      const { api } = await setup([failure(status, code)]);
      await expect(api.change(before, "新名称"))
        .rejects.toMatchObject({ code: "USER_NAME_INVALID_INPUT", uncertain: false });
    });

  it.each([reply({ ...after, user_id: adminId }), reply({ ...after, etag: '"v3"' }),
    reply(after, 200, { ETag: 'W/"v1"' }), reply({ ...after, account_state: "DISABLED" }),
    reply({ ...after, credential_version: 2 }), reply({ ...after, updated_at: "2026-09-28T09:00:00Z" }),
    reply({ ...before, username_display: "新名称" }, 200, { ETag: '"v0"' }),
    reply(after, 200, { ETag: '"v0"' }), failure(503, "SYSTEM_UNAVAILABLE"),
    failure(409, "SYSTEM_UNAVAILABLE")])(
    "treats malformed success or unproven failure as uncertain", async (response) => {
      const { api } = await setup([response]);
      await expect(api.change(before, "新名称"))
        .rejects.toMatchObject({ code: "USER_NAME_UNCERTAIN", uncertain: true });
    });

  it.each(["", "a".repeat(256), "新\u0000名", "\u202e名字"])(
    "rejects invalid proposed name %j before network", async (name) => {
      const { api, fetcher } = await setup([]);
      await expect(api.change(before, name))
        .rejects.toMatchObject({ code: "USER_NAME_INVALID_INPUT", uncertain: false });
      expect(fetcher).toHaveBeenCalledTimes(1);
    });

  it("refuses a malformed previous snapshot before sending PATCH", async () => {
    const { api, fetcher } = await setup([]);
    await expect(api.change({ ...before, etag: '"v00"' }, "新名称"))
      .rejects.toMatchObject({ code: "USER_NAME_INVALID_INPUT" });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});
