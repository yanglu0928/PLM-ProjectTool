import { afterEach, describe, expect, it, vi } from "vitest";
import { ReferenceReadClient, ReferenceReadError, parseReferenceCurrent, parseReferencePage } from "./referenceReadClient";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const reference = "11234567-89ab-4cde-8123-456789abcdef";
const version = "21234567-89ab-4cde-8123-456789abcdef";
const document = "31234567-89ab-4cde-8123-456789abcdef";
const documentVersion = "41234567-89ab-4cde-8123-456789abcdef";
const evidence = "51234567-89ab-4cde-8123-456789abcdef";
const actor = "61234567-89ab-4cde-8123-456789abcdef";
const trace = "71234567-89ab-4cde-8123-456789abcdef";
const token = `${"a".repeat(40)}.${"b".repeat(43)}`;
const date = "2026-10-09T00:00:00Z";
const item = { reference_solution_id: reference, reference_version_id: version, scope: "PROJECT",
  project_id: project, name: "历史参考方案", eligibility_state: "REFERENCE_ONLY", version_no: 1,
  version_state: "DRAFT", created_at: date, etag: '"v0"' };
const detail = { ...item, eligibility_reason: null, source_project_class: "PLM",
  deidentification_class: "PROJECT_INTERNAL", applicability: { industry: "synthetic" },
  document_version_ids: [documentVersion], document_refs: [{ document_id: document,
    document_version_id: documentVersion }], evidence_ids: [evidence],
  source_fingerprint: "a".repeat(64), content_fingerprint: "b".repeat(64),
  created_by: actor, version_created_by: actor, version_created_at: date };
function success(data: unknown, header?: string): Response {
  return new Response(JSON.stringify({ data, trace_id: trace }), { status: 200,
    headers: { "Content-Type": "application/json", ...(header ? { ETag: header } : {}) } });
}
function failure(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: "internal" }, trace_id: trace }),
    { status, headers: { "Content-Type": "application/json" } });
}
function client(...responses: Response[]) {
  const fetcher = vi.fn();
  for (const response of responses) fetcher.mockResolvedValueOnce(response);
  return { api: new ReferenceReadClient(fetcher as typeof fetch), fetcher };
}

describe("ReferenceReadClient", () => {
  afterEach(() => vi.restoreAllMocks());

  it("requests the project-only page with a bound opaque cursor", async () => {
    const { api, fetcher } = client(success({ items: [item], next_cursor: token, has_more: true }));
    const page = await api.list(project, 25);
    expect(fetcher).toHaveBeenCalledExactlyOnceWith(
      `/api/v1/projects/${project}/reference-solutions?page_size=25`,
      expect.objectContaining({ method: "GET", credentials: "same-origin", cache: "no-store", redirect: "error" }));
    expect(page.items).toEqual([item]);
    expect(page.next_cursor).toBe(token);
    expect(Object.isFrozen(page.items[0])).toBe(true);
    expect(() => parseReferencePage({ items: [item, item], next_cursor: null, has_more: false }, project, 50))
      .toThrow(ReferenceReadError);
  });

  it("invokes browser fetch without binding the client as receiver", async () => {
    const fetcher = vi.fn(function (this: unknown) {
      expect(this).toBeUndefined();
      return Promise.resolve(success({ items: [], next_cursor: null, has_more: false }));
    });
    await expect(new ReferenceReadClient(fetcher as typeof fetch).list(project)).resolves.toMatchObject({ items: [] });
  });

  it("requires fixed root/version matching and detail ETag", async () => {
    const { api, fetcher } = client(success(detail, '"v0"'));
    const current = await api.current(project, reference);
    expect(current.document_refs).toEqual([{ document_id: document, document_version_id: documentVersion }]);
    expect(Object.isFrozen(current.document_refs[0])).toBe(true);
    expect(fetcher.mock.calls[0]?.[0]).toBe(`/api/v1/projects/${project}/reference-solutions/${reference}`);
    await expect(client(success(detail, '"v1"')).api.current(project, reference))
      .rejects.toMatchObject({ code: "REFERENCE_UNAVAILABLE" });
    for (const corrupt of [
      { ...detail, document_refs: [] },
      { ...detail, document_refs: [{ document_id: document, document_version_id: evidence }] },
      { ...detail, project_id: evidence },
      { ...detail, storage_path: "private" },
      { ...detail, applicability: { href: "https://example.test" } },
    ]) expect(() => parseReferenceCurrent(corrupt, project, reference)).toThrow(ReferenceReadError);
  });

  it("rejects malformed input before network and maps only known errors", async () => {
    const { api, fetcher } = client();
    await expect(api.list("../global")).rejects.toMatchObject({ code: "REFERENCE_INVALID_INPUT" });
    await expect(api.current(project, "../global")).rejects.toMatchObject({ code: "REFERENCE_INVALID_INPUT" });
    await expect(api.list(project, 101)).rejects.toMatchObject({ code: "REFERENCE_INVALID_INPUT" });
    expect(fetcher).not.toHaveBeenCalled();
    await expect(client(failure(404, "RESOURCE_NOT_FOUND")).api.current(project, reference))
      .rejects.toMatchObject({ code: "RESOURCE_NOT_FOUND" });
    await expect(client(failure(403, "AUTH_SESSION_EXPIRED")).api.list(project))
      .rejects.toMatchObject({ code: "REFERENCE_UNAVAILABLE" });
  });
});
