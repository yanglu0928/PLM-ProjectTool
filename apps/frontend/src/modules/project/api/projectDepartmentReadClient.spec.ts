import { afterEach, describe, expect, it, vi } from "vitest";
import { ProjectDepartmentReadClient, ProjectDepartmentReadError } from "./projectDepartmentReadClient";

const projectId = "01234567-89ab-4cde-8123-456789abcdef";
const departmentId = "11234567-89ab-4cde-8123-456789abcdef";
const traceId = "21234567-89ab-4cde-8123-456789abcdef";
const cursor = `${"a".repeat(40)}.${"b".repeat(43)}`;
const nextCursor = `${"c".repeat(40)}.${"d".repeat(43)}`;
const entry = { department_id: departmentId, code: "RD", name: "研发部", state: "ACTIVE",
  created_at: "2026-09-29T02:00:00.123456Z", etag: '"v0"' };
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
  return { api: new ProjectDepartmentReadClient(fetcher as typeof fetch), fetcher };
}

describe("ProjectDepartmentReadClient", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); });

  it("does not request data on construction", () => {
    const { api, fetcher } = client();
    expect(fetcher).not.toHaveBeenCalled();
    expect(JSON.stringify(api)).not.toContain(departmentId);
  });

  it("reads safe projection, including inactive history, with fixed same-origin page", async () => {
    const inactive = { ...entry, state: "INACTIVE", etag: '"v1"' };
    const { api, fetcher } = client(success({ items: [{ ...inactive, private: "hidden" }],
      next_cursor: null, has_more: false, private: "hidden" }));
    const page = await api.list(projectId);
    expect(fetcher).toHaveBeenCalledExactlyOnceWith(`/api/v1/projects/${projectId}/departments?page_size=50`,
      expect.objectContaining({ method: "GET", credentials: "same-origin", cache: "no-store",
        redirect: "error", headers: { Accept: "application/json" } }));
    expect(page).toEqual({ items: [inactive], next_cursor: null, has_more: false });
    expect(Object.isFrozen(page.items[0])).toBe(true);
    expect(JSON.stringify(page)).not.toContain("hidden");
  });

  it("keeps the opaque cursor encoded and never interprets it", async () => {
    const { api, fetcher } = client(success({ items: [entry], next_cursor: nextCursor, has_more: true }));
    await expect(api.list(projectId, cursor)).resolves.toMatchObject({ next_cursor: nextCursor, has_more: true });
    expect(fetcher.mock.calls[0]?.[0]).toBe(`/api/v1/projects/${projectId}/departments?page_size=50&cursor=${cursor}`);
  });

  it.each(["", "../admin", projectId.toUpperCase(), "00000000-0000-0000-0000-000000000000"])(
    "rejects unsafe project id without network %s", async (value) => {
      const { api, fetcher } = client();
      await expect(api.list(value)).rejects.toMatchObject({ code: "PROJECT_DEPARTMENT_INVALID_PROJECT" });
      expect(fetcher).not.toHaveBeenCalled();
    });

  it.each(["", "x", "a/../admin", `${"a".repeat(513)}.${"b".repeat(43)}`])(
    "rejects bad cursor without network %s", async (value) => {
      const { api, fetcher } = client();
      await expect(api.list(projectId, value)).rejects.toMatchObject({ code: "PROJECT_DEPARTMENT_INVALID_CURSOR" });
      expect(fetcher).not.toHaveBeenCalled();
    });

  it.each([{ ...entry, department_id: "bad" }, { ...entry, code: " " }, { ...entry, name: "\u0000" },
    { ...entry, state: "REMOVED" }, { ...entry, created_at: "2026-02-30T02:00:00Z" },
    { ...entry, etag: 'W/"v1"' }, { ...entry, etag: '"v999999999999999999999"' }])(
    "rejects malformed department projection %#", async (value) => {
      const { api } = client(success({ items: [value], next_cursor: null, has_more: false }));
      await expect(api.list(projectId)).rejects.toMatchObject({ code: "PROJECT_DEPARTMENT_CLIENT_UNAVAILABLE" });
    });

  it.each([{ items: [entry], next_cursor: null, has_more: true },
    { items: [], next_cursor: nextCursor, has_more: true },
    { items: [entry], next_cursor: nextCursor, has_more: false },
    { items: [entry, entry], next_cursor: null, has_more: false },
    { items: [entry], next_cursor: "bad", has_more: true }])(
    "rejects invalid page %#", async (data) => {
      const { api } = client(success(data));
      await expect(api.list(projectId)).rejects.toMatchObject({ code: "PROJECT_DEPARTMENT_CLIENT_UNAVAILABLE" });
    });

  it("rejects a repeated next cursor", async () => {
    const { api } = client(success({ items: [entry], next_cursor: cursor, has_more: true }));
    await expect(api.list(projectId, cursor)).rejects.toMatchObject({ code: "PROJECT_DEPARTMENT_CLIENT_UNAVAILABLE" });
  });

  it.each([[401, "AUTH_SESSION_EXPIRED"], [403, "LICENSE_OPERATION_DENIED"],
    [404, "RESOURCE_NOT_FOUND"]] as const)("maps known error %s %s safely", async (status, code) => {
    const { api } = client(failure(status, code));
    const error = await api.list(projectId).catch((value: unknown) => value);
    expect(error).toBeInstanceOf(ProjectDepartmentReadError);
    expect(error).toMatchObject({ code });
    expect(String(error)).not.toContain("private");
  });

  it.each([failure(503, "SYSTEM_UNAVAILABLE"), new Response("<html>private</html>",
    { headers: { "Content-Type": "text/html" } }), new Response("invalid json",
    { headers: { "Content-Type": "application/json" } })])("fails closed on unavailable responses", async (result) => {
    const { api } = client(result);
    await expect(api.list(projectId)).rejects.toMatchObject({ code: "PROJECT_DEPARTMENT_CLIENT_UNAVAILABLE" });
  });

  it("does not bind native fetch to a client object", async () => {
    const fetcher = function (this: unknown): Promise<Response> {
      expect(this).toBeUndefined();
      return Promise.resolve(success({ items: [], next_cursor: null, has_more: false }));
    } as typeof fetch;
    await expect(new ProjectDepartmentReadClient(fetcher).list(projectId)).resolves.toMatchObject({ items: [] });
  });

  it("aborts timeout once without leaking transport details", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn().mockImplementation((_path: string, options: RequestInit) => new Promise((_resolve, reject) => {
      options.signal?.addEventListener("abort", () => reject(new Error("private timeout")));
    }));
    const api = new ProjectDepartmentReadClient(fetcher as typeof fetch, 100);
    const pending = expect(api.list(projectId)).rejects.toMatchObject({ code: "PROJECT_DEPARTMENT_CLIENT_UNAVAILABLE" });
    await vi.advanceTimersByTimeAsync(101);
    await pending;
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it.each([0, -1, 30_001, 1.5, NaN])("rejects invalid timeout %s", (timeout) => {
    expect(() => new ProjectDepartmentReadClient(fetch, timeout)).toThrow(ProjectDepartmentReadError);
  });
});
