import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { DocumentReadClient } from "@/modules/document/api/documentReadClient";
import { DocumentUploadIntentClient, DocumentUploadIntentError } from "@/modules/document/api/documentUploadIntentClient";
import { DocumentUploadContentClient, DocumentUploadContentError } from "@/modules/document/api/documentUploadContentClient";
import { DocumentUploadFinalizeClient, DocumentUploadFinalizeError } from "@/modules/document/api/documentUploadFinalizeClient";
import GlobalCapabilityDocumentUploadView from "./GlobalCapabilityDocumentUploadView.vue";

const actor = "01234567-89ab-4cde-8123-456789abcdef";
const upload = "11234567-89ab-4cde-8123-456789abcdef";
const document = "21234567-89ab-4cde-8123-456789abcdef";
const version = "31234567-89ab-4cde-8123-456789abcdef";
const job = "41234567-89ab-4cde-8123-456789abcdef";
const intent = { uploadId: upload, uploadToken: "u".repeat(43), expiresAt: "2030-01-01T12:00:00Z" };
const received = { uploadId: upload, sizeBytes: 9, sha256: "a".repeat(64), detectedMime: "text/plain" };
const committed = { first_result: { uploadId: upload, documentId: document,
  documentVersionId: version, versionNo: 1, parseJobId: job }, is_current_state_proof: false as const };
const aborted = { first_result: { uploadId: upload, state: "ABORTED" as const,
  cleanupPending: true }, is_current_state_proof: false as const };
const source = { document_id: document, scope: "GLOBAL" as const, category: "STANDARD_CAPABILITY" as const,
  subtype: null, title: "标准能力", display_name: "standard.txt", state: "ACTIVE" as const,
  latest_version_ref: version, effective_version_ref: version,
  created_at: "2026-10-24T01:00:00Z", etag: '"v1"' };
const fixedVersion = { document_version_id: version, version_no: 1, content_sha256: "a".repeat(64),
  size_bytes: 9, detected_mime: "text/plain", availability_state: "AVAILABLE" as const,
  supersedes_version_ref: null, created_at: "2026-10-24T01:00:00Z", integrity_checked_at: null };
function response(data: unknown) { return new Response(JSON.stringify({ data, trace_id: actor }),
  { status: 200, headers: { "Content-Type": "application/json" } }); }
async function session(admin: boolean, login = true) {
  const auth = new SessionClient(vi.fn().mockResolvedValue(response({
    user: { user_id: actor, username_display: "合成用户" }, deployment_role: admin ? "DEPLOYMENT_ADMIN" : "NONE",
    password_change_required: false, authorized_projects: admin ? [] : [{ project_id: actor,
      name: "合成项目", role: "PROJECT_MANAGER" }], absolute_expires_at: "2030-01-01T12:00:00Z",
    idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "a".repeat(64) })) as typeof fetch);
  if (login) await auth.login("synthetic", "synthetic-only"); return auth;
}
async function view(auth: SessionClient) {
  const documents = new DocumentReadClient(vi.fn() as typeof fetch);
  const get = vi.spyOn(documents, "get").mockResolvedValue(source);
  const versions = vi.spyOn(documents, "listVersions").mockResolvedValue({ items: [fixedVersion],
    next_cursor: null, has_more: false });
  const creator = new DocumentUploadIntentClient(auth);
  const create = vi.spyOn(creator, "createGlobal").mockResolvedValue(intent);
  const receiver = new DocumentUploadContentClient(auth);
  const put = vi.spyOn(receiver, "putGlobal").mockResolvedValue(received);
  const finalizer = new DocumentUploadFinalizeClient(auth);
  const commit = vi.spyOn(finalizer, "commitGlobal").mockResolvedValue(committed);
  const abort = vi.spyOn(finalizer, "abortGlobal").mockResolvedValue(aborted);
  const router = createAppRouter(createMemoryHistory());
  await router.push("/admin/capability-documents/new"); await router.isReady();
  const wrapper = mount(GlobalCapabilityDocumentUploadView, { props: { session: auth, documents,
    creator, receiver, finalizer }, global: { plugins: [router] } });
  await flushPromises();
  return { wrapper, get, versions, create, put, commit, abort };
}
async function fill(wrapper: Awaited<ReturnType<typeof view>>["wrapper"]) {
  await wrapper.get("#capability-document-title").setValue("标准能力");
  const file = new File(["synthetic"], "standard.txt", { type: "text/plain" });
  Object.defineProperty(wrapper.get("#capability-document-file").element, "files", { configurable: true,
    value: { item: (index: number) => index === 0 ? file : null } });
  await wrapper.get("#capability-document-file").trigger("change");
  await wrapper.get('input[type="checkbox"]').setValue(true);
  return file;
}
describe("GlobalCapabilityDocumentUploadView", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });
  it("blocks anonymous and ordinary project members before creating a GLOBAL intent", async () => {
    for (const auth of [await session(true, false), await session(false)]) {
      const result = await view(auth);
      expect(result.wrapper.find("form").exists()).toBe(false);
      expect(result.create).not.toHaveBeenCalled(); result.wrapper.unmount();
    }
  });
  it("uploads only STANDARD_CAPABILITY and distinguishes a receipt from an observed AVAILABLE version", async () => {
    const result = await view(await session(true)); const file = await fill(result.wrapper);
    await result.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(result.create).toHaveBeenCalledWith(expect.objectContaining({ kind: "NEW",
      category: "STANDARD_CAPABILITY", purpose: "CAPABILITY_SOURCE", displayName: file.name }), expect.any(String));
    expect(result.put).toHaveBeenCalledWith(intent, file);
    expect(result.commit).toHaveBeenCalledWith(received, expect.any(String));
    expect(result.wrapper.text()).toContain("这不是当前可用性证明");
    expect(result.get).not.toHaveBeenCalled();
    await result.wrapper.get("button[type=button]").trigger("click"); await flushPromises();
    expect(result.get).toHaveBeenCalledWith({ kind: "GLOBAL" }, document);
    expect(result.versions).toHaveBeenCalledWith({ kind: "GLOBAL" }, document, null);
    expect(result.wrapper.text()).toContain("AVAILABLE 固定版本"); result.wrapper.unmount();
  });
  it("keeps the original intent key after an unknown result and requires explicit confirmation", async () => {
    const result = await view(await session(true));
    result.create.mockRejectedValueOnce(new DocumentUploadIntentError("DOCUMENT_UPLOAD_CREATE_UNCERTAIN"));
    await fill(result.wrapper); await result.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(result.wrapper.text()).toContain("结果未知：CREATE");
    expect(result.put).not.toHaveBeenCalled();
    const firstKey = result.create.mock.calls[0]?.[1];
    const retry = result.wrapper.get("button[type=button]");
    expect(retry.attributes("disabled")).toBeDefined();
    await result.wrapper.get('input[type="checkbox"]').setValue(true);
    await retry.trigger("click"); await flushPromises();
    expect(result.create.mock.calls[1]?.[1]).toBe(firstKey);
    expect(result.commit).toHaveBeenCalledTimes(1); result.wrapper.unmount();
  });
  it("offers explicit abort on a definite content failure, without committing", async () => {
    const result = await view(await session(true));
    result.put.mockRejectedValueOnce(new DocumentUploadContentError("FILE_TYPE_UNSUPPORTED"));
    await fill(result.wrapper); await result.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(result.commit).not.toHaveBeenCalled();
    await result.wrapper.get('input[type="checkbox"]').setValue(true);
    await result.wrapper.get("button[type=button]").trigger("click"); await flushPromises();
    expect(result.abort).toHaveBeenCalledWith(upload, expect.any(String));
    expect(result.wrapper.text()).toContain("物理清理仍待执行"); result.wrapper.unmount();
  });
  it("retries an uncertain commit with the same key and no second intent", async () => {
    const result = await view(await session(true));
    result.commit.mockRejectedValueOnce(new DocumentUploadFinalizeError("DOCUMENT_UPLOAD_FINALIZE_UNCERTAIN"));
    await fill(result.wrapper); await result.wrapper.get("form").trigger("submit"); await flushPromises();
    const firstKey = result.commit.mock.calls[0]?.[1];
    await result.wrapper.get('input[type="checkbox"]').setValue(true);
    await result.wrapper.get("button[type=button]").trigger("click"); await flushPromises();
    expect(result.create).toHaveBeenCalledTimes(1);
    expect(result.commit.mock.calls[1]?.[1]).toBe(firstKey); result.wrapper.unmount();
  });
  it("clears in-memory file and token when the session changes", async () => {
    const auth = await session(true); const result = await view(auth);
    result.create.mockImplementationOnce(async () => {
      try { await auth.logout("synthetic-logout-0001"); } catch { /* Synthetic reply is not a logout receipt. */ }
      throw new DocumentUploadIntentError("AUTH_SESSION_EXPIRED");
    });
    await fill(result.wrapper); await result.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(result.put).not.toHaveBeenCalled();
    expect(result.wrapper.text()).toContain("原操作记录不再可用");
    expect(result.wrapper.text()).not.toContain("正在执行 建立上传意图"); result.wrapper.unmount();
  });
});
