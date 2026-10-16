import { afterEach, describe, expect, it, vi } from "vitest";
import { EvidenceViewerClient, EvidenceViewerClientError, parseEvidenceViewer } from "./evidenceViewerClient";

const projectId = "01234567-89ab-4cde-8123-456789abcdef";
const evidenceId = "11234567-89ab-4cde-8123-456789abcdef";
const documentId = "21234567-89ab-4cde-8123-456789abcdef";
const versionId = "31234567-89ab-4cde-8123-456789abcdef";
const traceId = "41234567-89ab-4cde-8123-456789abcdef";
const scope = { kind: "PROJECT" as const, projectId };
const descriptor = { evidence_id: evidenceId, document_id: documentId,
  document_version_id: versionId, document_version_no: 2, detected_mime: "application/pdf",
  size_bytes: 120, locator: { locator_type: "PAGE", page_no: 2 }, precision: "PARSED_NODE",
  display_label: "第 2 页", short_preview: "原文提示",
  content_url: `/api/v1/projects/${projectId}/documents/${documentId}/versions/${versionId}/content` };
function success(data: unknown): Response {
  return new Response(JSON.stringify({ data, trace_id: traceId }), { status: 200,
    headers: { "Content-Type": "application/json" } });
}
function failure(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: "private" }, trace_id: traceId }),
    { status, headers: { "Content-Type": "application/json" } });
}
function client(response: Response) {
  const fetcher = vi.fn().mockResolvedValue(response);
  return { api: new EvidenceViewerClient(fetcher as typeof fetch), fetcher };
}

describe("EvidenceViewerClient", () => {
  afterEach(() => { vi.restoreAllMocks(); });

  it("binds fixed Evidence and DocumentVersion and strips unknown fields", async () => {
    const { api, fetcher } = client(success({ ...descriptor, storage_locator: "private/path" }));
    const result = await api.get(scope, evidenceId);
    expect(fetcher).toHaveBeenCalledExactlyOnceWith(
      `/api/v1/projects/${projectId}/evidence/${evidenceId}/viewer`,
      expect.objectContaining({ method: "GET", credentials: "same-origin", cache: "no-store",
        redirect: "error", headers: { Accept: "application/json" } }));
    expect(result).toEqual(descriptor);
    expect(JSON.stringify(result)).not.toContain("private/path");
    expect(Object.isFrozen(result)).toBe(true);
  });

  it("invokes browser fetch without binding the client as its receiver", async () => {
    let receiver: unknown = Symbol("not-called");
    const fetcher = function (this: unknown): Promise<Response> {
      receiver = this;
      return Promise.resolve(success(descriptor));
    };
    await new EvidenceViewerClient(fetcher as typeof fetch).get(scope, evidenceId);
    expect(receiver).toBeUndefined();
  });

  it("rejects URL or source-identity substitution and malformed locator", async () => {
    for (const changed of [
      { ...descriptor, content_url: "https://evil.example/file" },
      { ...descriptor, content_url: `/api/v1/projects/${projectId}/documents/${documentId}/versions/${evidenceId}/content` },
      { ...descriptor, evidence_id: documentId },
      { ...descriptor, locator: { locator_type: "PAGE", page_no: 2, storage_path: "private" } },
      { ...descriptor, locator: { locator_type: "PAGE", page_no: 0 } },
      { ...descriptor, locator: { locator_type: "SHEET_RANGE", sheet_name: "Sheet1",
        start_cell: "C2", end_cell: "B3" } },
      { ...descriptor, short_preview: "x".repeat(501) },
    ]) {
      await expect(client(success(changed)).api.get(scope, evidenceId)).rejects
        .toMatchObject({ code: "EVIDENCE_CLIENT_UNAVAILABLE" });
    }
  });

  it("handles global URL, structured locator, and known errors", async () => {
    const global = { kind: "GLOBAL" as const };
    const value = { ...descriptor,
      content_url: `/api/v1/global/documents/${documentId}/versions/${versionId}/content`,
      locator: { locator_type: "STRUCTURED_NODE", parse_record_id: evidenceId,
        node_id: "n1", source_locator: { locator_type: "PAGE", page_no: 1 } } };
    await expect(client(success(value)).api.get(global, evidenceId))
      .resolves.toMatchObject({ content_url: value.content_url });
    for (const [code, status] of [["AUTH_SESSION_EXPIRED", 401], ["LICENSE_OPERATION_DENIED", 403],
      ["RESOURCE_NOT_FOUND", 404], ["EVIDENCE_FINGERPRINT_MISMATCH", 409]] as const) {
      await expect(client(failure(status, code)).api.get(scope, evidenceId))
        .rejects.toMatchObject({ code });
    }
    await expect(client(failure(500, "SYSTEM_INTERNAL")).api.get(scope, evidenceId))
      .rejects.toBeInstanceOf(EvidenceViewerClientError);
  });

  it("rejects invalid IDs before network and unsupported precision", async () => {
    const { api, fetcher } = client(success(descriptor));
    await expect(api.get(scope, "../file")).rejects.toMatchObject({ code: "EVIDENCE_INVALID_ID" });
    expect(fetcher).not.toHaveBeenCalled();
    expect(() => parseEvidenceViewer({ ...descriptor, precision: "EXACT_HIGHLIGHT" }, scope, evidenceId))
      .toThrowError(EvidenceViewerClientError);
  });
});
