import { afterEach, describe, expect, it, vi } from "vitest";
import { EvidenceListClient } from "./evidenceListClient";

const projectId = "01234567-89ab-4cde-8123-456789abcdef";
const evidenceId = "11234567-89ab-4cde-8123-456789abcdef";
const documentId = "21234567-89ab-4cde-8123-456789abcdef";
const versionId = "31234567-89ab-4cde-8123-456789abcdef";
const traceId = "41234567-89ab-4cde-8123-456789abcdef";
const scope = { kind: "PROJECT" as const, projectId };
const entry = { evidence_id: evidenceId, document_id: documentId,
  document_version_id: versionId, display_label: "第 2 页", display_excerpt: "短提示",
  eligibility_state: "CANDIDATE", created_at: "2026-10-01T02:00:00Z" };
const cursor = `${"a".repeat(40)}.${"b".repeat(43)}`;
function response(data: unknown): Response {
  return new Response(JSON.stringify({ data, trace_id: traceId }), { status: 200,
    headers: { "Content-Type": "application/json" } });
}
function client(...results: Response[]) {
  const fetcher = vi.fn();
  for (const result of results) fetcher.mockResolvedValueOnce(result);
  return { api: new EvidenceListClient(fetcher as typeof fetch), fetcher };
}

describe("EvidenceListClient", () => {
  afterEach(() => vi.restoreAllMocks());

  it("uses the isolated global list path without a project identifier", async () => {
    const { api, fetcher } = client(response({ items: [entry], has_more: false,
      next_cursor: null }));
    expect((await api.list({ kind: "GLOBAL" })).items).toEqual([entry]);
    expect(fetcher.mock.calls[0]?.[0]).toBe("/api/v1/global/evidence?page_size=50");
  });

  it("lists minimal safe summaries and strips internal fields", async () => {
    const { api, fetcher } = client(response({ items: [{ ...entry, content_fingerprint: "x".repeat(64),
      locator: { locator_type: "PAGE", page_no: 2 }, storage_locator: "private/path" }],
      has_more: false, next_cursor: null }));
    const page = await api.list(scope);
    expect(fetcher).toHaveBeenCalledExactlyOnceWith(`/api/v1/projects/${projectId}/evidence?page_size=50`,
      expect.objectContaining({ method: "GET", credentials: "same-origin", cache: "no-store",
        redirect: "error", headers: { Accept: "application/json" } }));
    expect(page.items).toEqual([entry]);
    expect(JSON.stringify(page)).not.toContain("private/path");
    expect(JSON.stringify(page)).not.toContain("content_fingerprint");
  });

  it("binds signed pagination and rejects malformed or duplicate items", async () => {
    const { api, fetcher } = client(response({ items: [entry], has_more: true, next_cursor: cursor }),
      response({ items: [], has_more: false, next_cursor: null }));
    expect((await api.list(scope)).next_cursor).toBe(cursor);
    expect((await api.list(scope, cursor)).items).toEqual([]);
    expect(fetcher.mock.calls[1]?.[0]).toBe(
      `/api/v1/projects/${projectId}/evidence?page_size=50&cursor=${encodeURIComponent(cursor)}`);
    await expect(client(response({ items: [entry, entry], has_more: false, next_cursor: null }))
      .api.list(scope)).rejects.toMatchObject({ code: "EVIDENCE_LIST_UNAVAILABLE" });
    await expect(client(response({ items: [entry], has_more: true, next_cursor: "bad" }))
      .api.list(scope)).rejects.toMatchObject({ code: "EVIDENCE_LIST_UNAVAILABLE" });
  });

  it("rejects invalid scope and cursor without network", async () => {
    const { api, fetcher } = client();
    await expect(api.list({ kind: "PROJECT", projectId: "../x" }))
      .rejects.toMatchObject({ code: "EVIDENCE_INVALID_SCOPE" });
    await expect(api.list(scope, "bad"))
      .rejects.toMatchObject({ code: "EVIDENCE_INVALID_CURSOR" });
    expect(fetcher).not.toHaveBeenCalled();
  });
});
