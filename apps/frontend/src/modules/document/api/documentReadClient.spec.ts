import { afterEach, describe, expect, it, vi } from "vitest";
import { DocumentReadClient, DocumentReadError } from "./documentReadClient";

const projectId = "01234567-89ab-4cde-8123-456789abcdef";
const documentId = "11234567-89ab-4cde-8123-456789abcdef";
const versionId = "31234567-89ab-4cde-8123-456789abcdef";
const traceId = "21234567-89ab-4cde-8123-456789abcdef";
const cursor = `${"a".repeat(40)}.${"b".repeat(43)}`;
const nextCursor = `${"c".repeat(40)}.${"d".repeat(43)}`;
const project = { kind: "PROJECT" as const, projectId };
const globalScope = { kind: "GLOBAL" as const };
const entry = { document_id: documentId, scope: "PROJECT", category: "PROJECT_RECORD", subtype: null,
  title: "调研记录", display_name: "调研记录.pdf", state: "ACTIVE", latest_version_ref: null,
  effective_version_ref: null, created_at: "2026-09-29T02:00:00.123456Z", etag: '"v0"' };
const version = { document_version_id: versionId, version_no: 2,
  content_sha256: "a".repeat(64), size_bytes: 4096, detected_mime: "application/pdf",
  availability_state: "AVAILABLE", supersedes_version_ref: documentId,
  created_at: "2026-09-29T02:00:00Z", integrity_checked_at: null };
function success(data: unknown, etag?: string): Response {
  return new Response(JSON.stringify({ data, trace_id: traceId }), { status: 200,
    headers: { "Content-Type": "application/json", ...(etag ? { ETag: etag } : {}) } });
}
function failure(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: "private details" }, trace_id: traceId }),
    { status, headers: { "Content-Type": "application/json" } });
}
function client(...results: Response[]) {
  const fetcher = vi.fn();
  for (const result of results) fetcher.mockResolvedValueOnce(result);
  return { api: new DocumentReadClient(fetcher as typeof fetch), fetcher };
}

describe("DocumentReadClient", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); });

  it("does not make a request on construction", () => {
    const { api, fetcher } = client();
    expect(fetcher).not.toHaveBeenCalled();
    expect(JSON.stringify(api)).not.toContain(documentId);
  });

  it("projects only safe metadata from a fixed project list", async () => {
    const { api, fetcher } = client(success({ items: [{ ...entry, storage_locator: "private" }],
      next_cursor: null, has_more: false, secret: "private" }));
    const page = await api.list(project);
    expect(fetcher).toHaveBeenCalledExactlyOnceWith(`/api/v1/projects/${projectId}/documents?page_size=50`,
      expect.objectContaining({ method: "GET", credentials: "same-origin", cache: "no-store",
        redirect: "error", headers: { Accept: "application/json" } }));
    expect(page).toEqual({ items: [entry], next_cursor: null, has_more: false });
    expect(Object.isFrozen(page.items[0])).toBe(true);
    expect(JSON.stringify(page)).not.toContain("private");
  });

  it("uses the distinct global path, preserves an opaque cursor, and requires scope match", async () => {
    const globalEntry = { ...entry, scope: "GLOBAL", category: "STANDARD_CAPABILITY" };
    const { api, fetcher } = client(success({ items: [globalEntry], next_cursor: nextCursor, has_more: true }));
    await expect(api.list(globalScope, cursor)).resolves.toMatchObject({ next_cursor: nextCursor });
    expect(fetcher.mock.calls[0]?.[0]).toBe(`/api/v1/global/documents?page_size=50&cursor=${cursor}`);
    const wrong = client(success({ items: [entry], next_cursor: null, has_more: false }));
    await expect(wrong.api.list(globalScope)).rejects.toMatchObject({ code: "DOCUMENT_CLIENT_UNAVAILABLE" });
  });

  it("binds detail identity, scope and strong response ETag", async () => {
    const detail = { ...entry, latest_version_ref: versionId, effective_version_ref: versionId, etag: '"v1"' };
    const { api, fetcher } = client(success({ ...detail, storage_path: "private" }, '"v1"'));
    await expect(api.get(project, documentId)).resolves.toEqual(detail);
    expect(fetcher.mock.calls[0]?.[0]).toBe(`/api/v1/projects/${projectId}/documents/${documentId}`);
    const mismatch = client(success(detail, '"v0"'));
    await expect(mismatch.api.get(project, documentId)).rejects.toMatchObject({ code: "DOCUMENT_CLIENT_UNAVAILABLE" });
  });

  it("reads only safe AVAILABLE version metadata using the fixed project path", async () => {
    const { api, fetcher } = client(success({ items: [{ ...version, storage_locator: "private" }],
      next_cursor: null, has_more: false }));
    const page = await api.listVersions(project, documentId);
    expect(fetcher).toHaveBeenCalledExactlyOnceWith(
      `/api/v1/projects/${projectId}/documents/${documentId}/versions?page_size=50`,
      expect.objectContaining({ method: "GET", credentials: "same-origin", cache: "no-store",
        redirect: "error", headers: { Accept: "application/json" } }));
    expect(page).toEqual({ items: [version], next_cursor: null, has_more: false });
    expect(JSON.stringify(page)).not.toContain("private");
    expect(Object.isFrozen(page.items[0])).toBe(true);
  });

  it("keeps the global version path distinct and preserves opaque cursor", async () => {
    const { api, fetcher } = client(success({ items: [version], next_cursor: nextCursor, has_more: true }));
    await expect(api.listVersions(globalScope, documentId, cursor)).resolves.toMatchObject({ has_more: true });
    expect(fetcher.mock.calls[0]?.[0]).toBe(
      `/api/v1/global/documents/${documentId}/versions?page_size=50&cursor=${cursor}`);
  });

  it("binds version detail to the requested identity and strips unknown fields", async () => {
    const { api, fetcher } = client(success({ ...version, local_path: "private" }));
    await expect(api.getVersion(project, documentId, versionId)).resolves.toEqual(version);
    expect(fetcher.mock.calls[0]?.[0]).toBe(
      `/api/v1/projects/${projectId}/documents/${documentId}/versions/${versionId}`);
    expect(JSON.stringify(await client(success(version)).api.getVersion(project, documentId, versionId)))
      .not.toContain("local_path");
    await expect(client(success({ ...version, document_version_id: documentId }))
      .api.getVersion(project, documentId, versionId)).rejects.toMatchObject({ code: "DOCUMENT_CLIENT_UNAVAILABLE" });
  });

  it.each(["", "../admin", versionId.toUpperCase(), "00000000-0000-0000-0000-000000000000"])(
    "rejects malformed version id without network %s", async (id) => {
      const { api, fetcher } = client();
      await expect(api.getVersion(project, documentId, id)).rejects
        .toMatchObject({ code: "DOCUMENT_INVALID_VERSION_ID" });
      expect(fetcher).not.toHaveBeenCalled();
    });

  it("rejects malformed document id or cursor before version-list network", async () => {
    const { api, fetcher } = client();
    await expect(api.listVersions(project, "../admin")).rejects.toMatchObject({ code: "DOCUMENT_INVALID_ID" });
    await expect(api.listVersions(project, documentId, "../admin")).rejects
      .toMatchObject({ code: "DOCUMENT_INVALID_CURSOR" });
    expect(fetcher).not.toHaveBeenCalled();
  });

  it.each([{ ...version, availability_state: "RESTRICTED" },
    { ...version, content_sha256: "A".repeat(64) }, { ...version, size_bytes: -1 },
    { ...version, version_no: 0 }, { ...version, detected_mime: "bad\u0000mime" },
    { ...version, created_at: "2026-02-30T02:00:00Z" },
    { ...version, integrity_checked_at: "not a time" }])(
    "rejects invalid version projection %#", async (item) => {
      await expect(client(success({ items: [item], next_cursor: null, has_more: false }))
        .api.listVersions(project, documentId)).rejects.toMatchObject({ code: "DOCUMENT_CLIENT_UNAVAILABLE" });
    });

  it.each([{ items: [version], next_cursor: null, has_more: true },
    { items: [], next_cursor: nextCursor, has_more: true },
    { items: [version, version], next_cursor: null, has_more: false },
    { items: [{ ...version, version_no: 1 }, version], next_cursor: null, has_more: false },
    { items: [version], next_cursor: nextCursor, has_more: false }])(
    "rejects invalid version page %#", async (data) => {
      await expect(client(success(data)).api.listVersions(project, documentId))
        .rejects.toMatchObject({ code: "DOCUMENT_CLIENT_UNAVAILABLE" });
    });

  it("does not expose unexpected server errors in version reads", async () => {
    const { api } = client(failure(503, "PRIVATE_BACKEND_ERROR"));
    const error = await api.listVersions(project, documentId).catch((value: unknown) => value);
    expect(error).toMatchObject({ code: "DOCUMENT_CLIENT_UNAVAILABLE" });
    expect(String(error)).not.toContain("PRIVATE_BACKEND_ERROR");
  });

  it.each([{ kind: "GLOBAL", projectId }, { kind: "PROJECT", projectId: "../admin" },
    { kind: "PROJECT", projectId: projectId.toUpperCase() }, { kind: "anything" }])(
    "rejects arbitrary or malformed scope without network %#", async (scope) => {
      const { api, fetcher } = client();
      await expect(api.list(scope as typeof project)).rejects.toMatchObject({ code: "DOCUMENT_INVALID_SCOPE" });
      expect(fetcher).not.toHaveBeenCalled();
    });

  it.each(["", "../admin", documentId.toUpperCase(), "00000000-0000-0000-0000-000000000000"])(
    "rejects invalid detail id %s", async (id) => {
      const { api, fetcher } = client();
      await expect(api.get(project, id)).rejects.toMatchObject({ code: "DOCUMENT_INVALID_ID" });
      expect(fetcher).not.toHaveBeenCalled();
    });

  it.each(["", "x", "a/../admin", `${"a".repeat(513)}.${"b".repeat(43)}`])(
    "rejects malformed cursor without network %s", async (value) => {
      const { api, fetcher } = client();
      await expect(api.list(project, value)).rejects.toMatchObject({ code: "DOCUMENT_INVALID_CURSOR" });
      expect(fetcher).not.toHaveBeenCalled();
    });

  it.each([{ ...entry, document_id: "bad" }, { ...entry, category: "UNKNOWN" },
    { ...entry, category: "OTHER" }, { ...entry, subtype: " " }, { ...entry, title: "\u0000" },
    { ...entry, state: "RESTRICTED" }, { ...entry, effective_version_ref: documentId },
    { ...entry, created_at: "2026-02-30T02:00:00Z" }, { ...entry, etag: 'W/"v1"' },
    { ...entry, etag: '"v999999999999999999999"' }])("rejects invalid projection %#", async (value) => {
    const { api } = client(success({ items: [value], next_cursor: null, has_more: false }));
    await expect(api.list(project)).rejects.toMatchObject({ code: "DOCUMENT_CLIENT_UNAVAILABLE" });
  });

  it.each([{ items: [entry], next_cursor: null, has_more: true },
    { items: [], next_cursor: nextCursor, has_more: true },
    { items: [entry], next_cursor: nextCursor, has_more: false },
    { items: [entry, entry], next_cursor: null, has_more: false },
    { items: [entry], next_cursor: "bad", has_more: true }])("rejects invalid page %#", async (data) => {
    const { api } = client(success(data));
    await expect(api.list(project)).rejects.toMatchObject({ code: "DOCUMENT_CLIENT_UNAVAILABLE" });
  });

  it("rejects a repeated next cursor", async () => {
    const { api } = client(success({ items: [entry], next_cursor: cursor, has_more: true }));
    await expect(api.list(project, cursor)).rejects.toMatchObject({ code: "DOCUMENT_CLIENT_UNAVAILABLE" });
  });

  it.each([[401, "AUTH_SESSION_EXPIRED"], [403, "LICENSE_OPERATION_DENIED"],
    [404, "RESOURCE_NOT_FOUND"]] as const)("maps only known status and code %s %s", async (status, code) => {
    const { api } = client(failure(status, code));
    const error = await api.list(project).catch((value: unknown) => value);
    expect(error).toBeInstanceOf(DocumentReadError);
    expect(error).toMatchObject({ code });
    expect(String(error)).not.toContain("private");
  });

  it.each([failure(503, "SYSTEM_UNAVAILABLE"), failure(404, "AUTH_SESSION_EXPIRED"),
    new Response("<html>private</html>", { headers: { "Content-Type": "text/html" } }),
    new Response("invalid json", { headers: { "Content-Type": "application/json" } })])(
    "fails closed on unavailable or malformed response", async (result) => {
      const { api } = client(result);
      await expect(api.list(project)).rejects.toMatchObject({ code: "DOCUMENT_CLIENT_UNAVAILABLE" });
    });

  it("calls native fetch without binding this", async () => {
    const fetcher = function (this: unknown): Promise<Response> {
      expect(this).toBeUndefined();
      return Promise.resolve(success({ items: [], next_cursor: null, has_more: false }));
    } as typeof fetch;
    await expect(new DocumentReadClient(fetcher).list(project)).resolves.toMatchObject({ items: [] });
  });

  it("aborts timeout without leaking transport details", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn().mockImplementation((_path: string, options: RequestInit) => new Promise((_resolve, reject) => {
      options.signal?.addEventListener("abort", () => reject(new Error("private timeout")));
    }));
    const api = new DocumentReadClient(fetcher as typeof fetch, 100);
    const pending = expect(api.list(project)).rejects.toMatchObject({ code: "DOCUMENT_CLIENT_UNAVAILABLE" });
    await vi.advanceTimersByTimeAsync(101);
    await pending;
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it.each([0, -1, 30_001, 1.5, NaN])("rejects invalid timeout %s", (timeout) => {
    expect(() => new DocumentReadClient(fetch, timeout)).toThrow(DocumentReadError);
  });
});
