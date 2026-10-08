import { afterEach, describe, expect, it, vi } from "vitest";
import { GlobalReferenceReadClient, GlobalReferenceReadError,
  parseGlobalReferenceCurrent, parseGlobalReferencePage } from "./globalReferenceReadClient";

const reference = "11234567-89ab-4cde-8123-456789abcdef";
const version = "21234567-89ab-4cde-8123-456789abcdef";
const document = "31234567-89ab-4cde-8123-456789abcdef";
const documentVersion = "41234567-89ab-4cde-8123-456789abcdef";
const evidence = "51234567-89ab-4cde-8123-456789abcdef";
const actor = "61234567-89ab-4cde-8123-456789abcdef";
const trace = "71234567-89ab-4cde-8123-456789abcdef";
const token = `${"a".repeat(40)}.${"b".repeat(43)}`;
const date = "2026-10-09T00:00:00Z";
const item = { reference_solution_id: reference, reference_version_id: version, scope: "GLOBAL",
  project_id: null, name: "历史全局参考方案", eligibility_state: "REFERENCE_ONLY", version_no: 1,
  version_state: "DRAFT", created_at: date, etag: '"v0"' };
const detail = { ...item, eligibility_reason: null, source_project_class: "PLM",
  deidentification_class: "DEIDENTIFIED", applicability: { industry: "synthetic" },
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
  return { api: new GlobalReferenceReadClient(fetcher as typeof fetch), fetcher };
}

describe("GlobalReferenceReadClient", () => {
  afterEach(() => vi.restoreAllMocks());

  it("requests only the GLOBAL list and validates an opaque cursor", async () => {
    const { api, fetcher } = client(success({ items: [item], next_cursor: token, has_more: true }));
    const page = await api.list(25);
    expect(fetcher).toHaveBeenCalledExactlyOnceWith(
      "/api/v1/global/reference-solutions?page_size=25",
      expect.objectContaining({ method: "GET", credentials: "same-origin", cache: "no-store", redirect: "error" }));
    expect(page.items).toEqual([item]);
    expect(page.next_cursor).toBe(token);
    expect(Object.isFrozen(page.items[0])).toBe(true);
    expect(() => parseGlobalReferencePage({ items: [item, item], next_cursor: null, has_more: false }, 50))
      .toThrow(GlobalReferenceReadError);
    await expect(client(success({ items: [], next_cursor: null, has_more: false })).api.list(25, token))
      .resolves.toMatchObject({ items: [] });
  });

  it("invokes browser fetch without receiver binding", async () => {
    const fetcher = vi.fn(function (this: unknown) {
      expect(this).toBeUndefined();
      return Promise.resolve(success({ items: [], next_cursor: null, has_more: false }));
    });
    await expect(new GlobalReferenceReadClient(fetcher as typeof fetch).list()).resolves.toMatchObject({ items: [] });
  });

  it("requires fixed GLOBAL identity, ordered refs, safe applicability and ETag", async () => {
    const { api, fetcher } = client(success(detail, '"v0"'));
    const current = await api.current(reference);
    expect(fetcher.mock.calls[0]?.[0]).toBe(`/api/v1/global/reference-solutions/${reference}`);
    expect(current.document_refs).toEqual([{ document_id: document, document_version_id: documentVersion }]);
    expect(Object.isFrozen(current.document_refs[0])).toBe(true);
    expect(current).not.toHaveProperty("deidentification_confirmation_id");
    await expect(client(success(detail, '"v1"')).api.current(reference))
      .rejects.toMatchObject({ code: "GLOBAL_REFERENCE_UNAVAILABLE" });
    for (const corrupt of [
      { ...detail, scope: "PROJECT" },
      { ...detail, project_id: actor },
      { ...detail, reference_solution_id: actor },
      { ...detail, document_refs: [] },
      { ...detail, document_refs: [{ document_id: document, document_version_id: evidence }] },
      { ...detail, evidence_ids: [evidence, evidence] },
      { ...detail, deidentification_confirmation_id: actor },
      { ...detail, applicability: { href: "https://example.test" } },
    ]) expect(() => parseGlobalReferenceCurrent(corrupt, reference)).toThrow(GlobalReferenceReadError);
    expect(() => parseGlobalReferencePage({ items: [{ ...item, project_id: actor }],
      next_cursor: null, has_more: false }, 50)).toThrow(GlobalReferenceReadError);
  });

  it("rejects malformed inputs before network and maps only matching errors", async () => {
    const { api, fetcher } = client();
    await expect(api.current("../projects")).rejects.toMatchObject({ code: "GLOBAL_REFERENCE_INVALID_INPUT" });
    await expect(api.list(0)).rejects.toMatchObject({ code: "GLOBAL_REFERENCE_INVALID_INPUT" });
    await expect(api.list(101)).rejects.toMatchObject({ code: "GLOBAL_REFERENCE_INVALID_INPUT" });
    await expect(api.list(25, "plain-id")).rejects.toMatchObject({ code: "GLOBAL_REFERENCE_INVALID_INPUT" });
    expect(fetcher).not.toHaveBeenCalled();
    await expect(client(failure(404, "RESOURCE_NOT_FOUND")).api.current(reference))
      .rejects.toMatchObject({ code: "RESOURCE_NOT_FOUND" });
    await expect(client(failure(403, "LICENSE_OPERATION_DENIED")).api.list())
      .rejects.toMatchObject({ code: "LICENSE_OPERATION_DENIED" });
    await expect(client(failure(403, "AUTH_SESSION_EXPIRED")).api.list())
      .rejects.toMatchObject({ code: "GLOBAL_REFERENCE_UNAVAILABLE" });
  });
});
