import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { DocumentUploadIntentClient } from "./documentUploadIntentClient";
import { DocumentUploadContentClient } from "./documentUploadContentClient";
import { DocumentUploadFinalizeClient } from "./documentUploadFinalizeClient";

const actor = "01234567-89ab-4cde-8123-456789abcdef";
const upload = "11234567-89ab-4cde-8123-456789abcdef";
const document = "21234567-89ab-4cde-8123-456789abcdef";
const version = "31234567-89ab-4cde-8123-456789abcdef";
const job = "41234567-89ab-4cde-8123-456789abcdef";
const hash = "75718f205b1951080757f2d5fdf5b0295da678358ad25604f72312d14bf664ea";
const contentText = "synthetic file bytes";
const input = { kind: "NEW" as const, purpose: "CAPABILITY_SOURCE", category: "STANDARD_CAPABILITY",
  title: "标准能力", displayName: "standard.txt", sizeHintBytes: contentText.length, mimeHint: "text/plain" };
function reply(data: unknown, status: number, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify({ data, trace_id: actor }), { status, headers: {
    "Content-Type": "application/json", "Cache-Control": "no-store", ...headers } });
}
function auth(): Response { return reply({ user: { user_id: actor, username_display: "合成管理员" },
  deployment_role: "DEPLOYMENT_ADMIN", password_change_required: false, authorized_projects: [],
  absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
  csrf_token: "a".repeat(64) }, 200); }
function harness(...results: Response[]) {
  const fetcher = vi.fn(); [auth(), ...results].forEach(result => fetcher.mockResolvedValueOnce(result));
  const session = new SessionClient(fetcher as typeof fetch);
  return { session, fetcher, intent: new DocumentUploadIntentClient(session),
    content: new DocumentUploadContentClient(session), finalize: new DocumentUploadFinalizeClient(session) };
}
function file(): Blob {
  const blob = new Blob([contentText]);
  Object.defineProperty(blob, "arrayBuffer", { value: async () => new TextEncoder().encode(contentText).buffer });
  const bytes = Uint8Array.from(hash.match(/../g) ?? [], pair => Number.parseInt(pair, 16));
  vi.stubGlobal("crypto", { subtle: { digest: vi.fn().mockResolvedValue(bytes.buffer) } });
  return blob;
}
describe("GLOBAL STANDARD_CAPABILITY upload", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });
  it("uses only GLOBAL CSRF-protected create/content/commit paths and exact first-result receipts", async () => {
    const bundle = harness(
      reply({ upload_id: upload, upload_token: "u".repeat(43), expires_at: "2030-01-01T12:00:00Z" },
        201, { Location: `/api/v1/global/document-uploads/${upload}` }),
      reply({ upload_id: upload, size_bytes: contentText.length, sha256: hash,
        detected_mime: "text/plain" }, 200),
      reply({ upload_id: upload, document_id: document, document_version_id: version,
        version_no: 1, parse_job_id: job }, 201,
        { Location: `/api/v1/global/documents/${document}/versions/${version}` }),
    );
    await bundle.session.login("synthetic", "synthetic-only");
    const intent = await bundle.intent.createGlobal(input, "synthetic-global-create-0001");
    const received = await bundle.content.putGlobal(intent, file());
    const committed = await bundle.finalize.commitGlobal(received, "synthetic-global-commit-0001");
    expect(committed).toEqual({ first_result: { uploadId: upload, documentId: document,
      documentVersionId: version, versionNo: 1, parseJobId: job }, is_current_state_proof: false });
    expect(bundle.fetcher.mock.calls.slice(1).map(call => call[0])).toEqual([
      "/api/v1/global/document-uploads", `/api/v1/global/document-uploads/${upload}/content`,
      `/api/v1/global/document-uploads/${upload}:commit` ]);
    expect(JSON.parse(bundle.fetcher.mock.calls[1][1].body)).toMatchObject({
      category: "STANDARD_CAPABILITY", purpose: "CAPABILITY_SOURCE" });
    expect(bundle.fetcher.mock.calls[2][1].headers["X-Upload-Token"]).toBe("u".repeat(43));
    expect(bundle.fetcher.mock.calls[2][1].headers["X-Content-SHA256"]).toBe(hash);
    expect(bundle.fetcher.mock.calls[3][1].headers["Idempotency-Key"]).toBe("synthetic-global-commit-0001");
    expect(bundle.fetcher.mock.calls[3][1].headers).not.toHaveProperty("If-Match");
  });
  it("rejects non-standard category locally and rejects a wrong GLOBAL receipt location", async () => {
    const bundle = harness(reply({ upload_id: upload, upload_token: "u".repeat(43),
      expires_at: "2030-01-01T12:00:00Z" }, 201,
      { Location: `/api/v1/projects/${actor}/document-uploads/${upload}` }));
    await bundle.session.login("synthetic", "synthetic-only");
    expect(() => bundle.intent.createGlobal({ ...input, category: "PROJECT_RECORD" }, "synthetic-global-create-0002"))
      .toThrowError();
    await expect(bundle.intent.createGlobal(input, "synthetic-global-create-0002"))
      .rejects.toMatchObject({ code: "DOCUMENT_UPLOAD_CREATE_UNCERTAIN", uncertain: true });
    expect(bundle.fetcher).toHaveBeenCalledTimes(2);
  });
  it("uses a separate GLOBAL abort path and preserves the original key", async () => {
    const bundle = harness(reply({ upload_id: upload, state: "ABORTED", cleanup_pending: true }, 200));
    await bundle.session.login("synthetic", "synthetic-only");
    const result = await bundle.finalize.abortGlobal(upload, "synthetic-global-abort-0001");
    expect(result.first_result).toMatchObject({ uploadId: upload, state: "ABORTED", cleanupPending: true });
    expect(bundle.fetcher.mock.calls[1][0]).toBe(`/api/v1/global/document-uploads/${upload}:abort`);
    expect(bundle.fetcher.mock.calls[1][1].headers["Idempotency-Key"]).toBe("synthetic-global-abort-0001");
  });
});
