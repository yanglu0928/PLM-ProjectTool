import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionClient } from "./sessionClient";
import { AdminUserStateClient, AdminUserStateError } from "./adminUserStateClient";

const adminId = "01234567-89ab-4cde-8123-456789abcdef";
const userId = "11234567-89ab-4cde-8123-456789abcdef";
const key = "synthetic-user-state-0001";
const view = { user_id: userId, username_display: "Synthetic Member", account_state: "DISABLED",
  deployment_role: "NONE", credential_version: 1, created_at: "2026-09-28T08:30:00Z",
  updated_at: "2026-09-28T09:30:00.123456Z", etag: '"v2"' };
function response(data: unknown, status = 200, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify({ data, trace_id: adminId }), { status,
    headers: { "Content-Type": "application/json", ETag: '"v2"', ...headers } });
}
function failure(status: number, code: string) {
  return new Response(JSON.stringify({ error: { code, message: "private detail" }, trace_id: adminId }),
    { status, headers: { "Content-Type": "application/json" } });
}
function auth(replies: Response[]) {
  const login = response({ user: { user_id: adminId, username_display: "Synthetic Admin" },
    deployment_role: "DEPLOYMENT_ADMIN", password_change_required: false, authorized_projects: [],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64) });
  const fetcher = vi.fn();
  for (const reply of [login, ...replies]) fetcher.mockResolvedValueOnce(reply);
  const session = new SessionClient(fetcher as typeof fetch);
  return { session, api: new AdminUserStateClient(session), fetcher };
}

describe("AdminUserStateClient", () => {
  afterEach(() => vi.restoreAllMocks());

  it("accepts only immutable safe first metadata for a bound disable result", async () => {
    const { session, api, fetcher } = auth([response({ ...view, private_revoked_count: 9,
      password_hash: "private", username_normalized: "private" })]);
    await session.login("admin", "synthetic-only");
    const result = await api.change(userId, "disable", '"v1"', key);
    expect(result).toEqual(view);
    expect(Object.isFrozen(result)).toBe(true);
    expect(JSON.stringify(result)).not.toContain("private");
    expect(fetcher.mock.calls[1][0]).toBe(`/api/v1/admin/users/${userId}:disable`);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("accepts a bound enable first result without asserting present-day state", async () => {
    const { session, api } = auth([response({ ...view, account_state: "ENABLED", etag: '"v6"' }, 200,
      { ETag: '"v6"' })]);
    await session.login("admin", "synthetic-only");
    await expect(api.change(userId, "enable", '"v5"', key)).resolves.toMatchObject({
      user_id: userId, account_state: "ENABLED", etag: '"v6"',
    });
  });

  it.each([[401, "AUTH_SESSION_EXPIRED"], [403, "AUTH_CSRF_INVALID"],
    [403, "LICENSE_OPERATION_DENIED"], [404, "RESOURCE_NOT_FOUND"],
    [409, "AUTH_USER_DISABLED"], [409, "CONFLICT_VERSION"],
    [409, "CONFLICT_IDEMPOTENCY"]] as const)("maps only matching definite %s %s", async (status, code) => {
    const { session, api } = auth([failure(status, code)]);
    await session.login("admin", "synthetic-only");
    const error = await api.change(userId, "disable", '"v1"', key).catch((value: unknown) => value);
    expect(error).toBeInstanceOf(AdminUserStateError);
    if (!(error instanceof AdminUserStateError)) throw new Error("expected safe state error");
    expect(error).toMatchObject({ code, uncertain: false });
    expect(String(error)).not.toContain("private");
  });

  it.each([[400, "REQUEST_MALFORMED"], [422, "VALIDATION_FAILED"],
    [428, "CONFLICT_VERSION_REQUIRED"]] as const)("maps request rejection %s %s", async (status, code) => {
    const { session, api } = auth([failure(status, code)]);
    await session.login("admin", "synthetic-only");
    await expect(api.change(userId, "disable", '"v1"', key))
      .rejects.toMatchObject({ code: "USER_STATE_INVALID_INPUT", uncertain: false });
  });

  it.each([response({ ...view, user_id: adminId }), response({ ...view, account_state: "ENABLED" }),
    response({ ...view, etag: '"v3"' }), response(view, 200, { ETag: 'W/"v2"' }),
    response({ ...view, credential_version: 0 }), response({ ...view, updated_at: "2026-09-28T07:00:00Z" }),
    failure(503, "SYSTEM_UNAVAILABLE"), failure(409, "SYSTEM_UNAVAILABLE")])(
    "treats malformed success or unproven failure as uncertain", async (reply) => {
      const { session, api } = auth([reply]);
      await session.login("admin", "synthetic-only");
      await expect(api.change(userId, "disable", '"v1"', key))
        .rejects.toMatchObject({ code: "USER_STATE_UNCERTAIN", uncertain: true });
    });

  it("rejects invalid target/version/key and read-only sessions before state POST", async () => {
    const { session, api, fetcher } = auth([]);
    await session.login("admin", "synthetic-only");
    await expect(api.change("../admin", "disable", '"v1"', key))
      .rejects.toMatchObject({ code: "USER_STATE_INVALID_INPUT", uncertain: false });
    await expect(api.change(userId, "disable", '"v9007199254740991"', key))
      .rejects.toMatchObject({ code: "USER_STATE_INVALID_INPUT", uncertain: false });
    await expect(api.change(userId, "disable", '"v1"', "short"))
      .rejects.toMatchObject({ code: "USER_STATE_INVALID_INPUT", uncertain: false });
    expect(fetcher).toHaveBeenCalledTimes(1);
    const readOnly = response({ user: { user_id: adminId, username_display: "Synthetic Admin" },
      deployment_role: "DEPLOYMENT_ADMIN", password_change_required: false, authorized_projects: [],
      absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z" });
    fetcher.mockResolvedValueOnce(readOnly);
    await session.current();
    await expect(api.change(userId, "disable", '"v1"', key))
      .rejects.toMatchObject({ code: "AUTH_RELOGIN_REQUIRED", uncertain: false });
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
});
