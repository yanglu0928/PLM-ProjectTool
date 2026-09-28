import { afterEach, describe, expect, it, vi } from "vitest";
import { AdminUserDetailClient, AdminUserDetailError } from "./adminUserDetailClient";

const userId = "11234567-89ab-4cde-8123-456789abcdef";
const trace = "01234567-89ab-4cde-8123-456789abcdef";
const detail = { user_id: userId, username_display: "Synthetic Member", account_state: "ENABLED",
  deployment_role: "NONE", credential_version: 1, created_at: "2026-09-28T08:30:00Z",
  updated_at: "2026-09-28T09:30:00Z", etag: '"v3"' };
function response(data: unknown, status = 200, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify({ data, trace_id: trace }), { status,
    headers: { "Content-Type": "application/json", ETag: '"v3"', ...headers } });
}
function error(status: number, code: string) {
  return new Response(JSON.stringify({ error: { code, message: "private detail" }, trace_id: trace }),
    { status, headers: { "Content-Type": "application/json" } });
}

describe("AdminUserDetailClient", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); });

  it("reads only frozen safe User metadata and the strong version", async () => {
    const fetcher = vi.fn().mockResolvedValue(response({ ...detail, password_hash: "private",
      username_normalized: "private", csrf_hash: "private" }));
    const api = new AdminUserDetailClient(fetcher as typeof fetch);
    const result = await api.get(userId);
    expect(result).toEqual(detail);
    expect(Object.isFrozen(result)).toBe(true);
    expect(JSON.stringify(result)).not.toContain("private");
    expect(fetcher).toHaveBeenCalledWith(`/api/v1/admin/users/${userId}`, {
      method: "GET", credentials: "same-origin", cache: "no-store", redirect: "error",
      headers: { Accept: "application/json" }, signal: expect.any(AbortSignal),
    });
  });

  it("allows disabled safe metadata without a usable credential but does not invent write authority", async () => {
    const fetcher = vi.fn().mockResolvedValue(response({ ...detail, account_state: "DISABLED",
      credential_version: 0 }));
    const api = new AdminUserDetailClient(fetcher as typeof fetch);
    await expect(api.get(userId)).resolves.toMatchObject({ account_state: "DISABLED", credential_version: 0 });
  });

  it.each(["", "../other", "00000000-0000-0000-0000-000000000000"])(
    "rejects invalid target %j without a request", async (target) => {
      const fetcher = vi.fn();
      const api = new AdminUserDetailClient(fetcher as typeof fetch);
      await expect(api.get(target)).rejects.toMatchObject({ code: "USER_DETAIL_INVALID_ID" });
      expect(fetcher).not.toHaveBeenCalled();
    });

  it.each([[401, "AUTH_SESSION_EXPIRED"], [403, "LICENSE_OPERATION_DENIED"],
    [404, "RESOURCE_NOT_FOUND"]] as const)("maps only exact %s %s safe error", async (status, code) => {
    const fetcher = vi.fn().mockResolvedValue(error(status, code));
    const api = new AdminUserDetailClient(fetcher as typeof fetch);
    const failure = await api.get(userId).catch((value: unknown) => value);
    expect(failure).toBeInstanceOf(AdminUserDetailError);
    if (!(failure instanceof AdminUserDetailError)) throw new Error("expected safe detail error");
    expect(failure.code).toBe(code);
    expect(String(failure)).not.toContain("private");
  });

  it.each([response({ ...detail, user_id: trace }), response({ ...detail, etag: '"v4"' }),
    response(detail, 200, { ETag: 'W/"v3"' }), response({ ...detail, account_state: "UNKNOWN" }),
    response({ ...detail, credential_version: 0 }), response({ ...detail, updated_at: "2026-09-28T07:00:00Z" }),
    error(503, "SYSTEM_UNAVAILABLE"), error(403, "RESOURCE_NOT_FOUND")])(
    "rejects malformed, unauthorized or mismatched metadata", async (reply) => {
      const fetcher = vi.fn().mockResolvedValue(reply);
      const api = new AdminUserDetailClient(fetcher as typeof fetch);
      await expect(api.get(userId)).rejects.toMatchObject({ code: "USER_DETAIL_UNAVAILABLE" });
    });

  it("aborts a slow GET once and does not retry", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn().mockImplementation((_path: string, options: RequestInit) =>
      new Promise((_done, reject) => options.signal?.addEventListener("abort", () => reject(new Error("slow")))));
    const api = new AdminUserDetailClient(fetcher as typeof fetch, 100);
    const pending = expect(api.get(userId)).rejects.toMatchObject({ code: "USER_DETAIL_UNAVAILABLE" });
    await vi.advanceTimersByTimeAsync(101);
    await pending;
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});
