import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { DocumentUploadIntentClient, type ProjectUploadIntentInput } from "./documentUploadIntentClient";

const userId = "01234567-89ab-4cde-8123-456789abcdef";
const projectId = "11234567-89ab-4cde-8123-456789abcdef";
const uploadId = "21234567-89ab-4cde-8123-456789abcdef";
const documentId = "31234567-89ab-4cde-8123-456789abcdef";
const versionId = "41234567-89ab-4cde-8123-456789abcdef";
const key = "synthetic-upload-0001";
const token = "a".repeat(43);
const input: ProjectUploadIntentInput = { kind: "NEW", purpose: "SOURCE",
  category: "PROJECT_RECORD", title: "调研记录", displayName: "record.pdf",
  sizeHintBytes: 50, mimeHint: "application/pdf" };
function json(data: unknown, status = 201, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify({ data, trace_id: userId }), { status, headers: {
    "Content-Type": "application/json", "Cache-Control": "no-store",
    Location: `/api/v1/projects/${projectId}/document-uploads/${uploadId}`, ...headers,
  } });
}
function created(extra: Record<string, unknown> = {}, headers: Record<string, string> = {}) {
  return json({ upload_id: uploadId, upload_token: token, expires_at: "2030-01-01T12:00:00Z", ...extra }, 201, headers);
}
function rejection(status: number, code: string) {
  return new Response(JSON.stringify({ error: { code, message: "private details" }, trace_id: userId }),
    { status, headers: { "Content-Type": "application/json" } });
}
function harness(replies: Response[]) {
  const login = json({ user: { user_id: userId, username_display: "Synthetic User" },
    deployment_role: "NONE", password_change_required: false, authorized_projects: [],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64) }, 200);
  const fetcher = vi.fn();
  for (const reply of [login, ...replies]) fetcher.mockResolvedValueOnce(reply);
  const session = new SessionClient(fetcher as typeof fetch);
  return { session, api: new DocumentUploadIntentClient(session), fetcher };
}

describe("DocumentUploadIntentClient", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); });

  it("creates a new project Document with a short-lived whitelisted proof", async () => {
    const storage = vi.spyOn(Storage.prototype, "setItem");
    const { session, api, fetcher } = harness([created({ storage_locator: "private-not-public" })]);
    await session.login("user", "synthetic-only");
    const result = await api.createProject(projectId, input, key);
    expect(result).toEqual({ uploadId, uploadToken: token, expiresAt: "2030-01-01T12:00:00Z" });
    expect(result).not.toHaveProperty("storage_locator");
    expect(Object.isFrozen(result)).toBe(true);
    expect(fetcher.mock.calls[1][0]).toBe(`/api/v1/projects/${projectId}/document-uploads`);
    expect(JSON.parse(fetcher.mock.calls[1][1].body)).toEqual({ purpose: "SOURCE",
      category: "PROJECT_RECORD", title: "调研记录", display_name: "record.pdf",
      size_hint_bytes: 50, mime_hint: "application/pdf" });
    expect(fetcher.mock.calls[1][1].headers["Idempotency-Key"]).toBe(key);
    expect(JSON.stringify(api)).not.toContain(token);
    expect(storage).not.toHaveBeenCalled();
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("creates a version intent without new Document metadata", async () => {
    const { session, api, fetcher } = harness([created()]);
    await session.login("user", "synthetic-only");
    await api.createProject(projectId, { kind: "VERSION", purpose: "SOURCE", displayName: "v2.pdf",
      documentId, supersedesVersionId: versionId }, key);
    expect(JSON.parse(fetcher.mock.calls[1][1].body)).toEqual({ purpose: "SOURCE", display_name: "v2.pdf",
      document_id: documentId, supersedes_version_id: versionId });
  });

  it.each([
    ["invalid project", "bad", input, key],
    ["invalid key", projectId, input, "short"],
    ["invalid purpose", projectId, { ...input, purpose: "source" }, key],
    ["invalid file name", projectId, { ...input, displayName: "../\u0000file" }, key],
    ["oversize", projectId, { ...input, sizeHintBytes: 100_000_001 }, key],
    ["other without subtype", projectId, { ...input, category: "OTHER" }, key],
    ["invalid version", projectId, { kind: "VERSION", purpose: "SOURCE", displayName: "x.pdf",
      documentId: "bad" }, key],
    ["mixed metadata", projectId, { kind: "VERSION", purpose: "SOURCE", displayName: "x.pdf",
      documentId, title: "wrong" }, key],
  ] as const)("rejects %s before transport", async (_label, project, bad, operationKey) => {
    const { api, fetcher } = harness([]);
    await expect(api.createProject(project, bad as ProjectUploadIntentInput, operationKey))
      .rejects.toMatchObject({ code: "DOCUMENT_UPLOAD_INVALID_INPUT", uncertain: false });
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("requires the private writable Session", async () => {
    const { api, fetcher } = harness([]);
    await expect(api.createProject(projectId, input, key))
      .rejects.toMatchObject({ code: "AUTH_RELOGIN_REQUIRED", uncertain: false });
    expect(fetcher).not.toHaveBeenCalled();
  });

  it.each([
    [401, "AUTH_SESSION_EXPIRED"], [403, "AUTH_CSRF_INVALID"],
    [403, "LICENSE_OPERATION_DENIED"], [404, "RESOURCE_NOT_FOUND"],
    [409, "PROJECT_ARCHIVED"], [409, "CONFLICT_STATE"],
    [409, "CONFLICT_VERSION"], [409, "CONFLICT_IDEMPOTENCY"],
    [409, "FILE_UPLOAD_EXPIRED"], [422, "VALIDATION_FAILED"], [400, "REQUEST_MALFORMED"],
  ] as const)("maps definite %s %s without raw details", async (status, code) => {
    const { session, api } = harness([rejection(status, code)]);
    await session.login("user", "synthetic-only");
    const failure = await api.createProject(projectId, input, key).catch((value: unknown) => value);
    expect(failure).toMatchObject({ code: code === "VALIDATION_FAILED" || code === "REQUEST_MALFORMED"
      ? "DOCUMENT_UPLOAD_INVALID_INPUT" : code, uncertain: false });
    expect(String(failure)).not.toContain("private");
  });

  it.each([
    created({ upload_id: documentId }),
    created({ upload_token: "bad" }),
    created({ expires_at: "2020-01-01T12:00:00Z" }),
    created({}, { Location: `/api/v1/projects/${documentId}/document-uploads/${uploadId}` }),
    created({}, { "Cache-Control": "public" }),
    json({ upload_id: uploadId }, 200),
    rejection(409, "UNEXPECTED_CODE"),
    new Response("not-json", { status: 201, headers: { "Content-Type": "text/html" } }),
  ])("does not accept a forged or ambiguous response %#", async (reply) => {
    const { session, api, fetcher } = harness([reply]);
    await session.login("user", "synthetic-only");
    await expect(api.createProject(projectId, input, key))
      .rejects.toMatchObject({ code: "DOCUMENT_UPLOAD_CREATE_UNCERTAIN", uncertain: true });
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("does not retry transport failure or change the original key", async () => {
    const { session, api, fetcher } = harness([]);
    await session.login("user", "synthetic-only");
    fetcher.mockRejectedValueOnce(new Error("private network details"));
    await expect(api.createProject(projectId, input, key))
      .rejects.toMatchObject({ code: "DOCUMENT_UPLOAD_CREATE_UNCERTAIN", uncertain: true });
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(fetcher.mock.calls[1][1].headers["Idempotency-Key"]).toBe(key);
  });
});
