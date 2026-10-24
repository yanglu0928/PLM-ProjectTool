import { afterEach, describe, expect, it, vi } from "vitest";
import { ProjectMemberReadClient, ProjectMemberReadError } from "./projectMemberReadClient";

const projectId = "01234567-89ab-4cde-8123-456789abcdef";
const memberId = "11234567-89ab-4cde-8123-456789abcdef";
const userId = "21234567-89ab-4cde-8123-456789abcdef";
const departmentId = "31234567-89ab-4cde-8123-456789abcdef";
const traceId = "41234567-89ab-4cde-8123-456789abcdef";
const cursor = `${"a".repeat(40)}.${"b".repeat(43)}`;
const nextCursor = `${"c".repeat(40)}.${"d".repeat(43)}`;
const entry = { member_id: memberId, user: { user_id: userId, display_name: "成员甲" },
  role: "PROJECT_MANAGER", department: { department_id: departmentId, name: "研发部" },
  state: "ACTIVE", effective_at: "2026-09-28T08:30:00.123456Z", ended_at: null, etag: '"v0"' };
function success(data: unknown): Response {
  return new Response(JSON.stringify({ data, trace_id: traceId }), { status: 200,
    headers: { "Content-Type": "application/json" } });
}
function failure(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: "private details" }, trace_id: traceId }),
    { status, headers: { "Content-Type": "application/json" } });
}
function client(...results: Response[]) {
  const fetcher = vi.fn();
  for (const result of results) fetcher.mockResolvedValueOnce(result);
  return { api: new ProjectMemberReadClient(fetcher as typeof fetch), fetcher };
}

describe("ProjectMemberReadClient", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); });

  it("does not request or retain a member on construction", () => {
    const { api, fetcher } = client();
    expect(fetcher).not.toHaveBeenCalled();
    expect(JSON.stringify(api)).not.toContain(memberId);
  });

  it("reads only safe projection by fixed page size and same-origin Cookie GET", async () => {
    const { api, fetcher } = client(success({ items: [{ ...entry, password_hash: "secret",
      user: { ...entry.user, email: "private" } }], next_cursor: null, has_more: false, private: "hidden" }));
    const page = await api.list(projectId);
    expect(fetcher).toHaveBeenCalledExactlyOnceWith(`/api/v1/projects/${projectId}/members?page_size=50`,
      expect.objectContaining({ method: "GET", credentials: "same-origin", cache: "no-store",
        redirect: "error", headers: { Accept: "application/json" } }));
    expect(page).toEqual({ items: [entry], next_cursor: null, has_more: false });
    expect(Object.isFrozen(page)).toBe(true);
    expect(Object.isFrozen(page.items)).toBe(true);
    expect(Object.isFrozen(page.items[0]?.user)).toBe(true);
    expect(JSON.stringify(page)).not.toMatch(/password_hash|email|private/);
  });

  it("keeps opaque cursor in an encoded query and never decodes it locally", async () => {
    const { api, fetcher } = client(success({ items: [entry], next_cursor: nextCursor, has_more: true }));
    await expect(api.list(projectId, cursor)).resolves.toEqual({ items: [entry], next_cursor: nextCursor, has_more: true });
    expect(fetcher.mock.calls[0]?.[0]).toBe(`/api/v1/projects/${projectId}/members?page_size=50&cursor=${cursor}`);
  });

  it("accepts empty final page without inventing members", async () => {
    const { api } = client(success({ items: [], next_cursor: null, has_more: false }));
    await expect(api.list(projectId)).resolves.toEqual({ items: [], next_cursor: null, has_more: false });
  });

  it.each(["", "../admin", projectId.toUpperCase(), "00000000-0000-0000-0000-000000000000"])(
    "rejects unsafe project id without network: %s", async (value) => {
      const { api, fetcher } = client();
      await expect(api.list(value)).rejects.toMatchObject({ code: "PROJECT_MEMBER_INVALID_PROJECT" });
      expect(fetcher).not.toHaveBeenCalled();
    });

  it.each(["", "x", "a/../admin", `${"a".repeat(513)}.${"b".repeat(43)}`])(
    "rejects malformed cursor without network: %s", async (value) => {
      const { api, fetcher } = client();
      await expect(api.list(projectId, value)).rejects.toMatchObject({ code: "PROJECT_MEMBER_INVALID_CURSOR" });
      expect(fetcher).not.toHaveBeenCalled();
    });

  it.each([
    { ...entry, member_id: "bad" }, { ...entry, user: { ...entry.user, user_id: "bad" } },
    { ...entry, user: { ...entry.user, display_name: " " } },
    { ...entry, role: "DEPLOYMENT_ADMIN" }, { ...entry, department: { ...entry.department, name: " " } },
    { ...entry, state: "UNKNOWN" }, { ...entry, state: "REMOVED" },
    { ...entry, state: "REMOVED", ended_at: "2026-09-28T09:00:00Z", effective_at: "bad" },
    { ...entry, ended_at: "2026-09-28T09:00:00Z" },
    { ...entry, effective_at: "2026-02-30T08:30:00Z" },
    { ...entry, etag: 'W/"v1"' },
  ])("rejects malformed member projection %#", async (value) => {
    const { api } = client(success({ items: [value], next_cursor: null, has_more: false }));
    await expect(api.list(projectId)).rejects.toMatchObject({ code: "PROJECT_MEMBER_CLIENT_UNAVAILABLE" });
  });

  it("accepts removed history only with an end time", async () => {
    const removed = { ...entry, state: "REMOVED", ended_at: "2026-09-28T09:00:00Z" };
    const { api } = client(success({ items: [removed], next_cursor: null, has_more: false }));
    await expect(api.list(projectId)).resolves.toMatchObject({ items: [removed] });
  });

  it.each([
    { items: [entry], next_cursor: null, has_more: true },
    { items: [], next_cursor: nextCursor, has_more: true },
    { items: [entry], next_cursor: nextCursor, has_more: false },
    { items: [entry], next_cursor: "bad", has_more: true },
    { items: [entry, entry], next_cursor: null, has_more: false },
    { items: null, next_cursor: null, has_more: false },
    { items: [], next_cursor: null, has_more: "false" },
  ])("fails closed on invalid page %#", async (data) => {
    const { api } = client(success(data));
    await expect(api.list(projectId)).rejects.toMatchObject({ code: "PROJECT_MEMBER_CLIENT_UNAVAILABLE" });
  });

  it("rejects a cursor repeated as next position", async () => {
    const { api } = client(success({ items: [entry], next_cursor: cursor, has_more: true }));
    await expect(api.list(projectId, cursor)).rejects.toMatchObject({ code: "PROJECT_MEMBER_CLIENT_UNAVAILABLE" });
  });

  it.each([[401, "AUTH_SESSION_EXPIRED"], [403, "LICENSE_OPERATION_DENIED"],
    [404, "RESOURCE_NOT_FOUND"]] as const)("maps known errors %s %s safely", async (status, code) => {
    const { api, fetcher } = client(failure(status, code));
    const error = await api.list(projectId).catch((value: unknown) => value);
    expect(error).toBeInstanceOf(ProjectMemberReadError);
    expect(error).toMatchObject({ code });
    expect(String(error)).not.toContain("private");
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it.each([[400, "REQUEST_MALFORMED"], [403, "RESOURCE_NOT_FOUND"],
    [503, "SYSTEM_UNAVAILABLE"]] as const)("rejects unexpected status/code %s %s", async (status, code) => {
    const { api } = client(failure(status, code));
    await expect(api.list(projectId)).rejects.toMatchObject({ code: "PROJECT_MEMBER_CLIENT_UNAVAILABLE" });
  });

  it.each([
    new Response("<html>private</html>", { headers: { "Content-Type": "text/html" } }),
    new Response("invalid json", { headers: { "Content-Type": "application/json" } }),
    new Response(JSON.stringify({ data: { items: [], next_cursor: null, has_more: false } }),
      { headers: { "Content-Type": "application/json" } }),
  ])("rejects malformed envelope without leaking raw response", async (result) => {
    const { api } = client(result);
    await expect(api.list(projectId)).rejects.toMatchObject({ code: "PROJECT_MEMBER_CLIENT_UNAVAILABLE" });
  });

  it("does not bind native fetch to client object", async () => {
    const fetcher = function (this: unknown): Promise<Response> {
      expect(this).toBeUndefined();
      return Promise.resolve(success({ items: [], next_cursor: null, has_more: false }));
    } as typeof fetch;
    await expect(new ProjectMemberReadClient(fetcher).list(projectId)).resolves.toMatchObject({ items: [] });
  });

  it("aborts timeout without leaking transport details or retrying", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn().mockImplementation((_path: string, options: RequestInit) => new Promise((_resolve, reject) => {
      options.signal?.addEventListener("abort", () => reject(new Error("private timeout")));
    }));
    const api = new ProjectMemberReadClient(fetcher as typeof fetch, 100);
    const pending = expect(api.list(projectId)).rejects.toMatchObject({ code: "PROJECT_MEMBER_CLIENT_UNAVAILABLE" });
    await vi.advanceTimersByTimeAsync(101);
    await pending;
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it.each([0, -1, 30_001, 1.5, NaN])("rejects invalid timeout %s", (timeout) => {
    expect(() => new ProjectMemberReadClient(fetch, timeout)).toThrow(ProjectMemberReadError);
  });
});
