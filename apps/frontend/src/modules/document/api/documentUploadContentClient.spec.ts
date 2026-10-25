import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { DocumentUploadContentClient } from "./documentUploadContentClient";

const userId = "01234567-89ab-4cde-8123-456789abcdef";
const projectId = "11234567-89ab-4cde-8123-456789abcdef";
const uploadId = "21234567-89ab-4cde-8123-456789abcdef";
const contentText = "synthetic file bytes";
const expectedHash = "75718f205b1951080757f2d5fdf5b0295da678358ad25604f72312d14bf664ea";
const intent = { uploadId, uploadToken: "u".repeat(43), expiresAt: "2030-01-01T12:00:00Z" };
function content(): Blob {
  const blob = new Blob([contentText]);
  Object.defineProperty(blob, "arrayBuffer", {
    value: async () => new TextEncoder().encode(contentText).buffer,
  });
  return blob;
}
function digest() {
  const hashBytes = Uint8Array.from(expectedHash.match(/../g) ?? [], (pair) => Number.parseInt(pair, 16));
  const run = vi.fn(async (algorithm: string, bytes: ArrayBuffer) => {
    expect(algorithm).toBe("SHA-256");
    expect(new TextDecoder().decode(bytes)).toBe(contentText);
    return hashBytes.buffer;
  });
  vi.stubGlobal("crypto", { subtle: { digest: run } });
  return run;
}
function reply(data: unknown, status = 200, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify({ data, trace_id: userId }), { status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store", ...headers } });
}
function received(extra: Record<string, unknown> = {}, headers: Record<string, string> = {}) {
  return reply({ upload_id: uploadId, size_bytes: contentText.length,
    sha256: expectedHash, detected_mime: "text/plain", ...extra }, 200, headers);
}
function rejection(status: number, code: string) {
  return new Response(JSON.stringify({ error: { code, message: "private details" }, trace_id: userId }),
    { status, headers: { "Content-Type": "application/json" } });
}
function harness(replies: Response[]) {
  const login = reply({ user: { user_id: userId, username_display: "Synthetic User" },
    deployment_role: "NONE", password_change_required: false, authorized_projects: [],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64) });
  const fetcher = vi.fn();
  for (const item of [login, ...replies]) fetcher.mockResolvedValueOnce(item);
  const session = new SessionClient(fetcher as typeof fetch);
  return { session, api: new DocumentUploadContentClient(session), fetcher };
}

describe("DocumentUploadContentClient", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

  it("hashes the same Blob, sends once and only returns whitelisted matching receipt", async () => {
    const run = digest();
    const file = content();
    const { session, api, fetcher } = harness([received({ private_locator: "never-public" })]);
    await session.login("user", "synthetic-only");
    const result = await api.putProject(projectId, intent, file);
    expect(result).toEqual({ uploadId, sizeBytes: file.size, sha256: expectedHash, detectedMime: "text/plain" });
    expect(Object.isFrozen(result)).toBe(true);
    expect(result).not.toHaveProperty("private_locator");
    expect(run).toHaveBeenCalledTimes(1);
    expect(fetcher.mock.calls[1][0]).toBe(`/api/v1/projects/${projectId}/document-uploads/${uploadId}/content`);
    expect(fetcher.mock.calls[1][1].body).toBe(file);
    expect(fetcher.mock.calls[1][1].headers["X-Content-SHA256"]).toBe(expectedHash);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it.each([
    ["invalid project", "bad", intent, content()],
    ["invalid ID", projectId, { ...intent, uploadId: "bad" }, content()],
    ["invalid token", projectId, { ...intent, uploadToken: "bad" }, content()],
    ["expired", projectId, { ...intent, expiresAt: "2020-01-01T12:00:00Z" }, content()],
    ["empty Blob", projectId, intent, new Blob([])],
  ] as const)("rejects %s before hashing or network", async (_label, project, proof, file) => {
    const run = digest();
    const { api, fetcher } = harness([]);
    await expect(api.putProject(project, proof, file))
      .rejects.toMatchObject({ code: "DOCUMENT_UPLOAD_CONTENT_INVALID", uncertain: false });
    expect(run).not.toHaveBeenCalled();
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("reports missing Web Crypto before sending", async () => {
    vi.stubGlobal("crypto", { subtle: null });
    const { api, fetcher } = harness([]);
    await expect(api.putProject(projectId, intent, content()))
      .rejects.toMatchObject({ code: "DOCUMENT_UPLOAD_HASH_UNAVAILABLE", uncertain: false });
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("checks expiry again after a slow digest", async () => {
    const file = content();
    const run = digest();
    run.mockImplementationOnce(async () => {
      vi.spyOn(Date, "now").mockReturnValue(Date.parse(intent.expiresAt) + 1);
      return Uint8Array.from(expectedHash.match(/../g) ?? [], (pair) => Number.parseInt(pair, 16)).buffer;
    });
    const { api, fetcher } = harness([]);
    await expect(api.putProject(projectId, intent, file))
      .rejects.toMatchObject({ code: "FILE_UPLOAD_EXPIRED", uncertain: false });
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("requires a writable Session after hashing", async () => {
    digest();
    const { api, fetcher } = harness([]);
    await expect(api.putProject(projectId, intent, content()))
      .rejects.toMatchObject({ code: "AUTH_RELOGIN_REQUIRED", uncertain: false });
    expect(fetcher).not.toHaveBeenCalled();
  });

  it.each([
    [401, "AUTH_SESSION_EXPIRED"], [403, "AUTH_CSRF_INVALID"],
    [403, "LICENSE_OPERATION_DENIED"], [404, "RESOURCE_NOT_FOUND"],
    [409, "PROJECT_ARCHIVED"], [409, "CONFLICT_STATE"], [409, "FILE_UPLOAD_EXPIRED"],
    [413, "FILE_TOO_LARGE"], [415, "FILE_TYPE_UNSUPPORTED"],
    [409, "FILE_INTEGRITY_MISMATCH"], [422, "VALIDATION_FAILED"], [400, "REQUEST_MALFORMED"],
  ] as const)("maps definite %s %s without raw details", async (status, code) => {
    digest();
    const { session, api } = harness([rejection(status, code)]);
    await session.login("user", "synthetic-only");
    const failure = await api.putProject(projectId, intent, content()).catch((value: unknown) => value);
    expect(failure).toMatchObject({ code: code === "VALIDATION_FAILED" || code === "REQUEST_MALFORMED"
      ? "DOCUMENT_UPLOAD_CONTENT_INVALID" : code, uncertain: false });
    expect(String(failure)).not.toContain("private");
  });

  it.each([
    received({ upload_id: userId }), received({ size_bytes: 1 }),
    received({ sha256: "0".repeat(64) }), received({ detected_mime: "" }),
    received({}, { "Cache-Control": "public" }),
    reply({ upload_id: uploadId }, 201), rejection(503, "FILE_CONTENT_UNAVAILABLE"),
    new Response("html", { status: 200, headers: { "Content-Type": "text/html" } }),
  ])("treats a mismatched or ambiguous receipt as uncertain %#", async (server) => {
    digest();
    const { session, api, fetcher } = harness([server]);
    await session.login("user", "synthetic-only");
    await expect(api.putProject(projectId, intent, content()))
      .rejects.toMatchObject({ code: "DOCUMENT_UPLOAD_CONTENT_UNCERTAIN", uncertain: true });
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("does not retry a transport failure", async () => {
    digest();
    const { session, api, fetcher } = harness([]);
    await session.login("user", "synthetic-only");
    fetcher.mockRejectedValueOnce(new Error("private network detail"));
    await expect(api.putProject(projectId, intent, content()))
      .rejects.toMatchObject({ code: "DOCUMENT_UPLOAD_CONTENT_UNCERTAIN", uncertain: true });
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
});
