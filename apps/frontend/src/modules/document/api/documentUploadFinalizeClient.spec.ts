import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { DocumentUploadFinalizeClient, type ProjectUploadCommitTarget } from "./documentUploadFinalizeClient";

const actorId = "01234567-89ab-4cde-8123-456789abcdef";
const projectId = "11234567-89ab-4cde-8123-456789abcdef";
const uploadId = "21234567-89ab-4cde-8123-456789abcdef";
const documentId = "31234567-89ab-4cde-8123-456789abcdef";
const versionId = "41234567-89ab-4cde-8123-456789abcdef";
const jobId = "51234567-89ab-4cde-8123-456789abcdef";
const content = { uploadId, sizeBytes: 19, sha256: "a".repeat(64), detectedMime: "text/plain" };
const key = "synthetic-finalize-0001";
const location = `/api/v1/projects/${projectId}/documents/${documentId}/versions/${versionId}`;
function response(data: unknown, status: number, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify({ data, trace_id: actorId }), { status, headers: {
    "Content-Type": "application/json", "Cache-Control": "no-store", ...headers,
  } });
}
function committed(extra: Record<string, unknown> = {}, headers: Record<string, string> = {}) {
  return response({ upload_id: uploadId, document_id: documentId, document_version_id: versionId,
    version_no: 1, parse_job_id: jobId, ...extra }, 201, { Location: location, ...headers });
}
function aborted(extra: Record<string, unknown> = {}, headers: Record<string, string> = {}) {
  return response({ upload_id: uploadId, state: "ABORTED", cleanup_pending: true, ...extra }, 200, headers);
}
function rejected(status: number, code: string) {
  return new Response(JSON.stringify({ error: { code, message: "private details" }, trace_id: actorId }),
    { status, headers: { "Content-Type": "application/json" } });
}
function harness(replies: Response[]) {
  const login = response({ user: { user_id: actorId, username_display: "Synthetic User" },
    deployment_role: "NONE", password_change_required: false, authorized_projects: [],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64) }, 200);
  const fetcher = vi.fn();
  for (const item of [login, ...replies]) fetcher.mockResolvedValueOnce(item);
  const session = new SessionClient(fetcher as typeof fetch);
  return { session, api: new DocumentUploadFinalizeClient(session), fetcher };
}

describe("DocumentUploadFinalizeClient", () => {
  afterEach(() => vi.restoreAllMocks());

  it("commits a new Document with the original key and first-result-only projection", async () => {
    const { session, api, fetcher } = harness([committed({ private_path: "never-public" })]);
    await session.login("user", "synthetic-only");
    const result = await api.commitProject(projectId, content, { kind: "NEW" }, key);
    expect(result).toEqual({ first_result: { uploadId, documentId, documentVersionId: versionId,
      versionNo: 1, parseJobId: jobId }, is_current_state_proof: false });
    expect(Object.isFrozen(result)).toBe(true);
    expect(Object.isFrozen(result.first_result)).toBe(true);
    expect(result.first_result).not.toHaveProperty("private_path");
    expect(fetcher.mock.calls[1][0]).toBe(`/api/v1/projects/${projectId}/document-uploads/${uploadId}:commit`);
    expect(fetcher.mock.calls[1][1].headers["Idempotency-Key"]).toBe(key);
    expect(fetcher.mock.calls[1][1].headers).not.toHaveProperty("If-Match");
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("binds version commit to its original Document and parent ETag", async () => {
    const { session, api, fetcher } = harness([committed({ version_no: 2 })]);
    await session.login("user", "synthetic-only");
    const target: ProjectUploadCommitTarget = { kind: "VERSION", documentId, parentEtag: '"v0"' };
    const result = await api.commitProject(projectId, content, target, key);
    expect(result.first_result.versionNo).toBe(2);
    expect(fetcher.mock.calls[1][1].headers["If-Match"]).toBe('"v0"');
  });

  it("rejects a version receipt for another Document even when Location agrees with it", async () => {
    const other = actorId;
    const { session, api } = harness([committed({ document_id: other }, {
      Location: `/api/v1/projects/${projectId}/documents/${other}/versions/${versionId}` })]);
    await session.login("user", "synthetic-only");
    await expect(api.commitProject(projectId, content,
      { kind: "VERSION", documentId, parentEtag: '"v0"' }, key))
      .rejects.toMatchObject({ code: "DOCUMENT_UPLOAD_FINALIZE_UNCERTAIN", uncertain: true });
  });

  it("preserves cleanup_pending without claiming physical cleanup", async () => {
    const { session, api, fetcher } = harness([aborted()]);
    await session.login("user", "synthetic-only");
    const result = await api.abortProject(projectId, uploadId, key);
    expect(result).toEqual({ first_result: { uploadId, state: "ABORTED", cleanupPending: true },
      is_current_state_proof: false });
    expect(Object.isFrozen(result.first_result)).toBe(true);
    expect(fetcher.mock.calls[1][0]).toBe(`/api/v1/projects/${projectId}/document-uploads/${uploadId}:abort`);
    expect(fetcher.mock.calls[1][1].headers).not.toHaveProperty("If-Match");
  });

  it("maps a definite Abort conflict without treating it as a successful cleanup", async () => {
    const { session, api } = harness([rejected(409, "CONFLICT_STATE")]);
    await session.login("user", "synthetic-only");
    await expect(api.abortProject(projectId, uploadId, key))
      .rejects.toMatchObject({ code: "CONFLICT_STATE", uncertain: false });
  });

  it.each([
    ["bad project", "bad", content, { kind: "NEW" }, key],
    ["bad content ID", projectId, { ...content, uploadId: "bad" }, { kind: "NEW" }, key],
    ["bad content hash", projectId, { ...content, sha256: "bad" }, { kind: "NEW" }, key],
    ["bad target", projectId, content, { kind: "VERSION", documentId: "bad", parentEtag: '"v0"' }, key],
    ["missing parent", projectId, content, { kind: "VERSION", documentId }, key],
    ["mixed new", projectId, content, { kind: "NEW", documentId }, key],
    ["bad ETag", projectId, content, { kind: "VERSION", documentId, parentEtag: '"v01"' }, key],
    ["bad key", projectId, content, { kind: "NEW" }, "short"],
  ] as const)("rejects commit %s before network", async (_label, project, file, target, operationKey) => {
    const { api, fetcher } = harness([]);
    await expect(api.commitProject(project, file, target as ProjectUploadCommitTarget, operationKey))
      .rejects.toMatchObject({ code: "DOCUMENT_UPLOAD_FINALIZE_INVALID", uncertain: false });
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("rejects malformed Abort before network and requires a writable Session", async () => {
    const { api, fetcher } = harness([]);
    await expect(api.abortProject(projectId, uploadId, key))
      .rejects.toMatchObject({ code: "AUTH_RELOGIN_REQUIRED", uncertain: false });
    await expect(api.abortProject(projectId, "bad", key))
      .rejects.toMatchObject({ code: "DOCUMENT_UPLOAD_FINALIZE_INVALID", uncertain: false });
    expect(fetcher).not.toHaveBeenCalled();
  });

  it.each([
    [401, "AUTH_SESSION_EXPIRED"], [403, "AUTH_CSRF_INVALID"],
    [403, "LICENSE_OPERATION_DENIED"], [404, "RESOURCE_NOT_FOUND"],
    [409, "PROJECT_ARCHIVED"], [409, "CONFLICT_VERSION"],
    [409, "CONFLICT_STATE"], [409, "CONFLICT_IDEMPOTENCY"],
    [409, "FILE_UPLOAD_EXPIRED"], [409, "FILE_INTEGRITY_MISMATCH"],
    [428, "CONFLICT_VERSION_REQUIRED"], [422, "VALIDATION_FAILED"],
    [400, "REQUEST_MALFORMED"],
  ] as const)("maps definite finalize %s %s without raw details", async (status, code) => {
    const { session, api } = harness([rejected(status, code)]);
    await session.login("user", "synthetic-only");
    const failure = await api.commitProject(projectId, content, { kind: "NEW" }, key).catch((value: unknown) => value);
    expect(failure).toMatchObject({ code: ["CONFLICT_VERSION_REQUIRED", "VALIDATION_FAILED",
      "REQUEST_MALFORMED"].includes(code) ? "DOCUMENT_UPLOAD_FINALIZE_INVALID" : code, uncertain: false });
    expect(String(failure)).not.toContain("private");
  });

  it.each([
    committed({ upload_id: actorId }), committed({ document_id: actorId }),
    committed({ document_version_id: actorId }), committed({ parse_job_id: "bad" }),
    committed({ version_no: 0 }), committed({}, { Location: "/wrong" }),
    committed({}, { "Cache-Control": "public" }),
    response({ upload_id: uploadId }, 200), rejected(503, "FILE_CONTENT_UNAVAILABLE"),
    new Response("not-json", { status: 201, headers: { "Content-Type": "text/html" } }),
  ])("does not trust mismatched or ambiguous Commit %#", async (server) => {
    const { session, api, fetcher } = harness([server]);
    await session.login("user", "synthetic-only");
    await expect(api.commitProject(projectId, content, { kind: "VERSION", documentId, parentEtag: '"v0"' }, key))
      .rejects.toMatchObject({ code: "DOCUMENT_UPLOAD_FINALIZE_UNCERTAIN", uncertain: true });
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it.each([
    aborted({ upload_id: actorId }), aborted({ state: "COMMITTED" }),
    aborted({ cleanup_pending: "yes" }), aborted({}, { "Cache-Control": "public" }),
    response({ upload_id: uploadId }, 201), rejected(503, "FILE_CONTENT_UNAVAILABLE"),
  ])("does not trust mismatched or ambiguous Abort %#", async (server) => {
    const { session, api, fetcher } = harness([server]);
    await session.login("user", "synthetic-only");
    await expect(api.abortProject(projectId, uploadId, key))
      .rejects.toMatchObject({ code: "DOCUMENT_UPLOAD_FINALIZE_UNCERTAIN", uncertain: true });
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("does not replay Commit after a transport failure", async () => {
    const { session, api, fetcher } = harness([]);
    await session.login("user", "synthetic-only");
    fetcher.mockRejectedValueOnce(new Error("private network details"));
    await expect(api.commitProject(projectId, content, { kind: "NEW" }, key))
      .rejects.toMatchObject({ code: "DOCUMENT_UPLOAD_FINALIZE_UNCERTAIN", uncertain: true });
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(fetcher.mock.calls[1][1].headers["Idempotency-Key"]).toBe(key);
  });
});
