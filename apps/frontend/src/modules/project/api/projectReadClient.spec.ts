import { afterEach, describe, expect, it, vi } from "vitest";
import { ProjectReadClient, ProjectReadError } from "./projectReadClient";

const id = "01234567-89ab-4cde-8123-456789abcdef";
const otherId = "11234567-89ab-4cde-8123-456789abcdef";
const project = { project_id: id, code: "DEMO", name: "演示项目", state: "ACTIVE",
  created_at: "2026-09-28T08:30:00.123456Z", etag: '"v0"' };
function response(data: unknown, headerEtag?: string): Response {
  return new Response(JSON.stringify({ data, trace_id: id }), { status: 200,
    headers: { "Content-Type": "application/json", ...(headerEtag ? { ETag: headerEtag } : {}) } });
}
function failure(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: "private server details" }, trace_id: id }),
    { status, headers: { "Content-Type": "application/json" } });
}
function client(...results: Response[]) {
  const fetcher = vi.fn();
  for (const result of results) fetcher.mockResolvedValueOnce(result);
  return { api: new ProjectReadClient(fetcher as typeof fetch), fetcher };
}

describe("ProjectReadClient", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); });

  it("does not request or persist anything on construction", () => {
    const { api, fetcher } = client();
    expect(api).toBeDefined();
    expect(fetcher).not.toHaveBeenCalled();
    expect(JSON.stringify(api)).not.toContain("project_id");
  });

  it("lists only server-authorized projection via relative same-origin Cookie GET", async () => {
    const { api, fetcher } = client(response({ items: [{ ...project, secret: "not-public" }],
      next_cursor: null, has_more: false, private: "hidden" }));
    const page = await api.list();
    expect(fetcher).toHaveBeenCalledExactlyOnceWith("/api/v1/projects", expect.objectContaining({
      method: "GET", credentials: "same-origin", cache: "no-store", redirect: "error",
      headers: { Accept: "application/json" },
    }));
    expect(page).toEqual({ items: [project], next_cursor: null, has_more: false });
    expect(Object.isFrozen(page)).toBe(true);
    expect(Object.isFrozen(page.items)).toBe(true);
    expect(Object.isFrozen(page.items[0])).toBe(true);
    expect(JSON.stringify(page)).not.toContain("secret");
  });

  it("accepts empty list without inventing project access", async () => {
    const { api } = client(response({ items: [], next_cursor: null, has_more: false }));
    await expect(api.list()).resolves.toEqual({ items: [], next_cursor: null, has_more: false });
  });

  it("reads detail only by canonical id and matching strong ETag", async () => {
    const { api, fetcher } = client(response({ ...project, internal: "hidden" }, project.etag));
    await expect(api.get(id)).resolves.toEqual(project);
    expect(fetcher.mock.calls[0][0]).toBe(`/api/v1/projects/${id}`);
    expect(fetcher.mock.calls[0][1]).toMatchObject({ method: "GET", credentials: "same-origin" });
  });

  it.each(["", "../admin", id.toUpperCase(), "00000000-0000-0000-0000-000000000000"])(
    "rejects unsafe detail identifier without network: %s", async (value) => {
      const { api, fetcher } = client();
      await expect(api.get(value)).rejects.toMatchObject({ code: "PROJECT_INVALID_ID" });
      expect(fetcher).not.toHaveBeenCalled();
    });

  it.each([undefined, '"v1"']) ("rejects absent or mismatched detail ETag %s", async (header) => {
    const { api } = client(response(project, header));
    await expect(api.get(id)).rejects.toMatchObject({ code: "PROJECT_CLIENT_UNAVAILABLE" });
  });

  it("rejects a different project even when the server returns 200", async () => {
    const { api } = client(response({ ...project, project_id: otherId }, project.etag));
    await expect(api.get(id)).rejects.toMatchObject({ code: "PROJECT_CLIENT_UNAVAILABLE" });
  });

  it.each([
    [{ ...project, project_id: "bad" }], [{ ...project, code: " " }],
    [{ ...project, state: "UNKNOWN" }], [{ ...project, created_at: "2026-02-30T08:30:00Z" }],
    [{ ...project, created_at: "2026-09-28T08:30:00+08:00" }],
    [{ ...project, etag: 'W/"v1"' }],
    [project, project],
  ].map((items) => [items]))("fails closed on malformed or unsupported list items %j", async (items) => {
    const { api } = client(response({ items, next_cursor: null, has_more: false }));
    await expect(api.list()).rejects.toMatchObject({ code: "PROJECT_CLIENT_UNAVAILABLE" });
  });

  it.each([{ items: [], next_cursor: "x", has_more: false },
    { items: [], next_cursor: null, has_more: true }, { items: null, next_cursor: null, has_more: false }])(
    "rejects malformed page %j", async (data) => {
      const { api } = client(response(data));
      await expect(api.list()).rejects.toMatchObject({ code: "PROJECT_CLIENT_UNAVAILABLE" });
    });

  it.each([[401, "AUTH_SESSION_EXPIRED"], [403, "LICENSE_OPERATION_DENIED"],
    [404, "RESOURCE_NOT_FOUND"]] as const)("maps known status/code %s %s safely", async (status, code) => {
    const { api, fetcher } = client(failure(status, code));
    const error = await api.list().catch((value: unknown) => value);
    expect(error).toBeInstanceOf(ProjectReadError);
    if (!(error instanceof ProjectReadError)) throw new Error("expected safe project error");
    expect(error.code).toBe(code);
    expect(String(error)).not.toContain("private");
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it.each([[503, "SYSTEM_UNAVAILABLE"], [403, "RESOURCE_NOT_FOUND"],
    [401, "PRIVATE_ERROR"]] as const)("does not trust wrong or unknown error %s %s", async (status, code) => {
    const { api, fetcher } = client(failure(status, code));
    await expect(api.list()).rejects.toMatchObject({ code: "PROJECT_CLIENT_UNAVAILABLE" });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it.each([
    new Response("<html>private</html>", { headers: { "Content-Type": "text/html" } }),
    new Response("not-json", { headers: { "Content-Type": "application/json" } }),
    new Response(JSON.stringify({ data: project }), { headers: { "Content-Type": "application/json" } }),
  ])("rejects malformed envelope without raw details", async (raw) => {
    const { api } = client(raw);
    await expect(api.list()).rejects.toMatchObject({ code: "PROJECT_CLIENT_UNAVAILABLE" });
  });

  it("does not bind native fetch to client object", async () => {
    const fetcher = function (this: unknown): Promise<Response> {
      expect(this).toBeUndefined();
      return Promise.resolve(response({ items: [], next_cursor: null, has_more: false }));
    } as typeof fetch;
    await expect(new ProjectReadClient(fetcher).list()).resolves.toMatchObject({ items: [] });
  });

  it("aborts timeout, reveals no transport details and does not retry", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn().mockImplementation((_path: string, options: RequestInit) => new Promise((_resolve, reject) => {
      options.signal?.addEventListener("abort", () => reject(new Error("private timeout")));
    }));
    const api = new ProjectReadClient(fetcher as typeof fetch, 100);
    const pending = expect(api.list()).rejects.toMatchObject({ code: "PROJECT_CLIENT_UNAVAILABLE" });
    await vi.advanceTimersByTimeAsync(101);
    await pending;
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it.each([0, -1, 30_001, 1.5, NaN])("rejects invalid timeout %s", (timeout) => {
    expect(() => new ProjectReadClient(fetch, timeout)).toThrow(ProjectReadError);
  });
});
