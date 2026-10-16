import { afterEach, describe, expect, it, vi } from "vitest";
import { AdminUserListClient, UserCandidateError } from "./adminUserListClient";

const id = "01234567-89ab-4cde-8123-456789abcdef";
const otherId = "11234567-89ab-4cde-8123-456789abcdef";
const cursor = "u1.synthetic_cursor";
const enabled = { user_id: id, username_display: "测试负责人", account_state: "ENABLED",
  deployment_role: "NONE", email: "private@example.invalid" };
const disabled = { ...enabled, user_id: otherId, username_display: "停用用户", account_state: "DISABLED" };
function response(data: unknown): Response {
  return new Response(JSON.stringify({ data, trace_id: id }), { status: 200,
    headers: { "Content-Type": "application/json" } });
}
function failure(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: "private server details" }, trace_id: id }),
    { status, headers: { "Content-Type": "application/json" } });
}
function client(...results: Response[]) {
  const fetcher = vi.fn();
  for (const result of results) fetcher.mockResolvedValueOnce(result);
  return { api: new AdminUserListClient(fetcher as typeof fetch), fetcher };
}

describe("AdminUserListClient", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); });

  it("is inert on construction and reads one same-origin page with a safe frozen projection", async () => {
    const { api, fetcher } = client(response({ items: [enabled, disabled], next_cursor: null,
      has_more: false, internal: "private" }));
    expect(fetcher).not.toHaveBeenCalled();
    const page = await api.page();
    expect(fetcher).toHaveBeenCalledExactlyOnceWith("/api/v1/admin/users?page_size=50", expect.objectContaining({
      method: "GET", credentials: "same-origin", cache: "no-store", redirect: "error",
      headers: { Accept: "application/json" },
    }));
    expect(page).toEqual({ items: [
      { user_id: id, username_display: "测试负责人", account_state: "ENABLED" },
      { user_id: otherId, username_display: "停用用户", account_state: "DISABLED" },
    ], next_cursor: null, has_more: false });
    expect(Object.isFrozen(page)).toBe(true);
    expect(Object.isFrozen(page.items)).toBe(true);
    expect(Object.isFrozen(page.items[0])).toBe(true);
    expect(JSON.stringify(page)).not.toContain("private");
  });

  it("does not automatically fetch another page and passes only a bounded opaque cursor", async () => {
    const items = Array.from({ length: 50 }, (_, index) => ({ ...enabled,
      user_id: `01234567-89ab-4cde-8123-${String(index).padStart(12, "0")}` }));
    const { api, fetcher } = client(response({ items, next_cursor: cursor, has_more: true }),
      response({ items: [], next_cursor: null, has_more: false }));
    const first = await api.page();
    expect(first.has_more).toBe(true);
    expect(fetcher).toHaveBeenCalledTimes(1);
    await expect(api.page(first.next_cursor)).resolves.toMatchObject({ items: [], has_more: false });
    expect(fetcher.mock.calls[1][0]).toBe(`/api/v1/admin/users?page_size=50&cursor=${cursor}`);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it.each(["", "u2.bad", "u1.a/b", `u1.${"a".repeat(1537)}`])(
    "rejects invalid cursor before network %s", async (value) => {
      const { api, fetcher } = client();
      await expect(api.page(value)).rejects.toMatchObject({ code: "USER_LIST_CURSOR_INVALID" });
      expect(fetcher).not.toHaveBeenCalled();
    });

  it.each([
    { items: [{ ...enabled, user_id: "bad" }], next_cursor: null, has_more: false },
    { items: [{ ...enabled, account_state: "UNKNOWN" }], next_cursor: null, has_more: false },
    { items: [{ ...enabled, username_display: " " }], next_cursor: null, has_more: false },
    { items: [{ ...enabled, deployment_role: "SUPERUSER" }], next_cursor: null, has_more: false },
    { items: [enabled, enabled], next_cursor: null, has_more: false },
    { items: [], next_cursor: cursor, has_more: true },
    { items: [], next_cursor: cursor, has_more: false },
    { items: [], next_cursor: null, has_more: true },
    { items: Array.from({ length: 51 }, () => enabled), next_cursor: null, has_more: false },
  ])("fails closed on malformed list/page %j", async (data) => {
    const { api } = client(response(data));
    await expect(api.page()).rejects.toMatchObject({ code: "USER_LIST_UNAVAILABLE" });
  });

  it.each([[401, "AUTH_SESSION_EXPIRED"], [403, "LICENSE_OPERATION_DENIED"],
    [404, "RESOURCE_NOT_FOUND"], [400, "REQUEST_MALFORMED"]] as const)(
    "maps exact status and code safely %s %s", async (status, code) => {
      const { api, fetcher } = client(failure(status, code));
      const error = await api.page().catch((value: unknown) => value);
      expect(error).toBeInstanceOf(UserCandidateError);
      if (!(error instanceof UserCandidateError)) throw new Error("expected safe user-list error");
      expect(error.code).toBe(code === "REQUEST_MALFORMED" ? "USER_LIST_CURSOR_INVALID" : code);
      expect(String(error)).not.toContain("private");
      expect(fetcher).toHaveBeenCalledTimes(1);
    });

  it.each([[403, "RESOURCE_NOT_FOUND"], [503, "SYSTEM_UNAVAILABLE"],
    [401, "PRIVATE_ERROR"]] as const)("does not trust wrong error %s %s", async (status, code) => {
    const { api } = client(failure(status, code));
    await expect(api.page()).rejects.toMatchObject({ code: "USER_LIST_UNAVAILABLE" });
  });

  it.each([
    new Response("<html>private</html>", { headers: { "Content-Type": "text/html" } }),
    new Response("not-json", { headers: { "Content-Type": "application/json" } }),
    new Response(JSON.stringify({ data: { items: [] } }), { headers: { "Content-Type": "application/json" } }),
  ])("rejects malformed envelope without raw details", async (raw) => {
    const { api } = client(raw);
    await expect(api.page()).rejects.toMatchObject({ code: "USER_LIST_UNAVAILABLE" });
  });

  it("does not bind native fetch to the client object", async () => {
    const fetcher = function (this: unknown): Promise<Response> {
      expect(this).toBeUndefined();
      return Promise.resolve(response({ items: [], next_cursor: null, has_more: false }));
    } as typeof fetch;
    await expect(new AdminUserListClient(fetcher).page()).resolves.toMatchObject({ items: [] });
  });

  it("aborts timeout and never retries or reveals transport details", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn().mockImplementation((_path: string, options: RequestInit) => new Promise((_resolve, reject) => {
      options.signal?.addEventListener("abort", () => reject(new Error("private timeout")));
    }));
    const pending = expect(new AdminUserListClient(fetcher as typeof fetch, 100).page())
      .rejects.toMatchObject({ code: "USER_LIST_UNAVAILABLE" });
    await vi.advanceTimersByTimeAsync(101);
    await pending;
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it.each([0, -1, 30_001, 1.5, NaN])("rejects invalid timeout %s", (timeout) => {
    expect(() => new AdminUserListClient(fetch, timeout)).toThrow(UserCandidateError);
  });
});
