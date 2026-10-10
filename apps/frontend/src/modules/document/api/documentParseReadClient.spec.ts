import { afterEach, describe, expect, it, vi } from "vitest";
import { DocumentReadClient } from "./documentReadClient";

const projectId = "01234567-89ab-4cde-8123-456789abcdef";
const documentId = "11234567-89ab-4cde-8123-456789abcdef";
const versionId = "31234567-89ab-4cde-8123-456789abcdef";
const recordId = "41234567-89ab-4cde-8123-456789abcdef";
const jobId = "51234567-89ab-4cde-8123-456789abcdef";
const resultId = "61234567-89ab-4cde-8123-456789abcdef";
const traceId = "21234567-89ab-4cde-8123-456789abcdef";
const cursor = `${"a".repeat(800)}.${"b".repeat(43)}`;
const nextCursor = `${"c".repeat(800)}.${"d".repeat(43)}`;
const project = { kind: "PROJECT" as const, projectId };
const globalScope = { kind: "GLOBAL" as const };
const pending = { parse_record_id: recordId, parser_profile: "default", parser_version: "1.0",
  parse_state: "PENDING", attempt_no: 1, job_ref: jobId, result_ref: null,
  error_code: null, retryable: null, created_at: "2026-09-30T01:00:00.123456Z",
  started_at: null, completed_at: null };
const started = "2026-09-30T01:01:00.123456Z";
const completed = "2026-09-30T01:02:00.123456Z";

function success(data: unknown): Response {
  return new Response(JSON.stringify({ data, trace_id: traceId }), { status: 200,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
}
function failure(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: "private details" }, trace_id: traceId }),
    { status, headers: { "Content-Type": "application/json" } });
}
function client(...responses: Response[]) {
  const fetcher = vi.fn();
  for (const response of responses) fetcher.mockResolvedValueOnce(response);
  return { api: new DocumentReadClient(fetcher as typeof fetch), fetcher };
}
function page(items: unknown[], next: string | null = null) {
  return { items, next_cursor: next, has_more: next !== null };
}

describe("DocumentReadClient fixed-version ParseRecord list", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); });

  it("uses an authorized fixed project path and strips server-only fields", async () => {
    const { api, fetcher } = client(success(page([{ ...pending, storage_locator: "private",
      result_sha256: "private", payload_refs: "private" }])));
    const result = await api.listParses(project, documentId, versionId);
    expect(fetcher).toHaveBeenCalledExactlyOnceWith(
      `/api/v1/projects/${projectId}/documents/${documentId}/versions/${versionId}/parses?page_size=50`,
      expect.objectContaining({ method: "GET", credentials: "same-origin", cache: "no-store",
        redirect: "error", headers: { Accept: "application/json" } }));
    expect(result).toEqual(page([pending]));
    expect(Object.isFrozen(result)).toBe(true);
    expect(Object.isFrozen(result.items[0])).toBe(true);
    expect(JSON.stringify(result)).not.toContain("private");
  });

  it("uses the distinct GLOBAL route and accepts the longer signed Parse cursor", async () => {
    const { api, fetcher } = client(success(page([pending], nextCursor)));
    await expect(api.listParses(globalScope, documentId, versionId, cursor))
      .resolves.toMatchObject({ next_cursor: nextCursor, has_more: true });
    expect(fetcher.mock.calls[0]?.[0]).toBe(
      `/api/v1/global/documents/${documentId}/versions/${versionId}/parses?page_size=50&cursor=${cursor}`);
  });

  it.each([{ kind: "PROJECT", projectId: "../other" }, { kind: "GLOBAL", projectId },
    { kind: "OTHER" }])("rejects hostile scope before network %#", async (scope) => {
    const { api, fetcher } = client();
    await expect(api.listParses(scope as typeof project, documentId, versionId))
      .rejects.toMatchObject({ code: "DOCUMENT_INVALID_SCOPE" });
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("rejects document/version/cursor injection before network", async () => {
    const { api, fetcher } = client();
    await expect(api.listParses(project, "../admin", versionId))
      .rejects.toMatchObject({ code: "DOCUMENT_INVALID_ID" });
    await expect(api.listParses(project, documentId, "../admin"))
      .rejects.toMatchObject({ code: "DOCUMENT_INVALID_VERSION_ID" });
    await expect(api.listParses(project, documentId, versionId, "../admin"))
      .rejects.toMatchObject({ code: "DOCUMENT_INVALID_CURSOR" });
    await expect(api.listParses(project, documentId, versionId,
      `${"a".repeat(1025)}.${"b".repeat(43)}`))
      .rejects.toMatchObject({ code: "DOCUMENT_INVALID_CURSOR" });
    expect(fetcher).not.toHaveBeenCalled();
  });

  it.each([
    { ...pending, parse_state: "RUNNING", started_at: started },
    { ...pending, parse_state: "SUCCEEDED", started_at: started, completed_at: completed,
      result_ref: resultId, retryable: false },
    { ...pending, parse_state: "FAILED", started_at: started, completed_at: completed,
      error_code: "PARSER_FAILED", retryable: true },
    { ...pending, parse_state: "CANCELLED", completed_at: completed, retryable: false },
  ])("accepts a safe %s state without implying parsed content", async (item) => {
    await expect(client(success(page([item]))).api.listParses(project, documentId, versionId))
      .resolves.toEqual(page([item]));
  });

  it.each([
    { ...pending, parse_record_id: "bad" },
    { ...pending, parser_profile: "bad\u0000profile" },
    { ...pending, parser_version: " " },
    { ...pending, parse_state: "DONE" },
    { ...pending, parse_state: { toString: (): string => "PENDING" } },
    { ...pending, attempt_no: 0 },
    { ...pending, job_ref: "bad" },
    { ...pending, result_ref: resultId },
    { ...pending, error_code: "private error" },
    { ...pending, retryable: false },
    { ...pending, created_at: "2026-02-30T01:00:00Z" },
    { ...pending, parse_state: "RUNNING" },
    { ...pending, parse_state: "SUCCEEDED", started_at: started, completed_at: completed },
    { ...pending, parse_state: "FAILED", started_at: started, completed_at: completed,
      error_code: "PARSER_FAILED" },
    { ...pending, parse_state: "CANCELLED", completed_at: completed, retryable: true },
    { ...pending, parse_state: "FAILED", started_at: completed, completed_at: started,
      error_code: "PARSER_FAILED", retryable: false },
  ])("rejects invalid Parse metadata %#", async (item) => {
    await expect(client(success(page([item]))).api.listParses(project, documentId, versionId))
      .rejects.toMatchObject({ code: "DOCUMENT_CLIENT_UNAVAILABLE" });
  });

  it.each([
    { items: [pending], has_more: true, next_cursor: null },
    { items: [], has_more: true, next_cursor: nextCursor },
    { items: [pending, pending], has_more: false, next_cursor: null },
    { items: [pending], has_more: false, next_cursor: nextCursor },
    { items: [pending], has_more: true, next_cursor: cursor },
    { items: Array.from({ length: 51 }, () => pending), has_more: false, next_cursor: null },
  ])("rejects malformed or duplicate page %#", async (data) => {
    await expect(client(success(data)).api.listParses(project, documentId, versionId,
      data.next_cursor === cursor ? cursor : null))
      .rejects.toMatchObject({ code: "DOCUMENT_CLIENT_UNAVAILABLE" });
  });

  it.each([[401, "AUTH_SESSION_EXPIRED"], [403, "LICENSE_OPERATION_DENIED"],
    [404, "RESOURCE_NOT_FOUND"]] as const)("maps %i %s without server details", async (status, code) => {
    const error = await client(failure(status, code)).api.listParses(project, documentId, versionId)
      .catch((value: unknown) => value);
    expect(error).toMatchObject({ code });
    expect(String(error)).not.toContain("private details");
  });

  it("fails closed on unexpected server response", async () => {
    const error = await client(failure(503, "PRIVATE_BACKEND_ERROR")).api
      .listParses(project, documentId, versionId).catch((value: unknown) => value);
    expect(error).toMatchObject({ code: "DOCUMENT_CLIENT_UNAVAILABLE" });
    expect(String(error)).not.toContain("PRIVATE_BACKEND_ERROR");
  });
});
