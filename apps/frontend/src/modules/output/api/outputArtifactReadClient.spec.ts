import { afterEach, describe, expect, it, vi } from "vitest";
import {
  OutputArtifactReadClient, OutputArtifactReadError,
  parseOutputArtifactReference,
} from "./outputArtifactReadClient";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const request = "21234567-89ab-4cde-8123-456789abcdef";
const artifact = "31234567-89ab-4cde-8123-456789abcdef";
const document = "41234567-89ab-4cde-8123-456789abcdef";
const version = "51234567-89ab-4cde-8123-456789abcdef";
const trace = "61234567-89ab-4cde-8123-456789abcdef";
const mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
function reference() {
  return {
    output_artifact_id: artifact, output_request_id: request, project_id: project,
    document_id: document, document_version_id: version, artifact_kind: "DOCX",
    media_type: mime, content_sha256: "a".repeat(64), size_bytes: 128,
    content_url: "/api/v1/projects/" + project + "/documents/" + document
      + "/versions/" + version + "/content",
  };
}
function ok(data: unknown): Response {
  return new Response(JSON.stringify({ data, trace_id: trace }), {
    status: 200, headers: { "Content-Type": "application/json" },
  });
}
function bad(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: "private" }, trace_id: trace }), {
    status, headers: { "Content-Type": "application/json" },
  });
}
describe("OutputArtifactReadClient", () => {
  afterEach(() => vi.restoreAllMocks());

  it("fetches the project/request reference with same-origin protected options", async () => {
    const fetcher = vi.fn().mockResolvedValue(ok(reference()));
    const api = new OutputArtifactReadClient(fetcher as typeof fetch);
    const value = await api.get(project, request);
    expect(fetcher).toHaveBeenCalledExactlyOnceWith(
      "/api/v1/projects/" + project + "/output-requests/" + request + "/artifact",
      expect.objectContaining({ method: "GET", credentials: "same-origin",
        cache: "no-store", redirect: "error" }),
    );
    expect(value.content_url).toBe(reference().content_url);
    expect(Object.isFrozen(value)).toBe(true);
  });

  it("rejects cross-scope, external URLs, extra fields and inconsistent content", () => {
    for (const corrupt of [
      { ...reference(), project_id: request },
      { ...reference(), output_request_id: artifact },
      { ...reference(), content_url: "https://evil.example/file" },
      { ...reference(), content_url: reference().content_url + "?path=x" },
      { ...reference(), media_type: "image/png" },
      { ...reference(), content_sha256: "bad" },
      { ...reference(), size_bytes: 134217729 },
      { ...reference(), extra: "storage locator" },
    ]) expect(() => parseOutputArtifactReference(corrupt, project, request))
      .toThrow(OutputArtifactReadError);
  });

  it("maps only authorized service errors and rejects malformed input before fetch", async () => {
    const fetcher = vi.fn();
    const api = new OutputArtifactReadClient(fetcher as typeof fetch);
    await expect(api.get("../project", request)).rejects.toMatchObject({
      code: "OUTPUT_ARTIFACT_UNAVAILABLE",
    });
    expect(fetcher).not.toHaveBeenCalled();
    const denied = new OutputArtifactReadClient(
      vi.fn().mockResolvedValue(bad(404, "RESOURCE_NOT_FOUND")) as typeof fetch,
    );
    await expect(denied.get(project, request)).rejects.toMatchObject({
      code: "RESOURCE_NOT_FOUND",
    });
    const malformed = new OutputArtifactReadClient(
      vi.fn().mockResolvedValue(bad(403, "AUTH_SESSION_EXPIRED")) as typeof fetch,
    );
    await expect(malformed.get(project, request)).rejects.toMatchObject({
      code: "OUTPUT_ARTIFACT_UNAVAILABLE",
    });
  });
});
