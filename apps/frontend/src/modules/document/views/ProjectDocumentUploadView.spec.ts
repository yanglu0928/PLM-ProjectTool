import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { DocumentReadClient } from "@/modules/document/api/documentReadClient";
import { DocumentUploadIntentClient, DocumentUploadIntentError } from "@/modules/document/api/documentUploadIntentClient";
import { DocumentUploadContentClient, DocumentUploadContentError } from "@/modules/document/api/documentUploadContentClient";
import { DocumentUploadFinalizeClient, DocumentUploadFinalizeError } from "@/modules/document/api/documentUploadFinalizeClient";
import ProjectDocumentUploadView from "./ProjectDocumentUploadView.vue";

const actor = "01234567-89ab-4cde-8123-456789abcdef";
const project = "11234567-89ab-4cde-8123-456789abcdef";
const document = "21234567-89ab-4cde-8123-456789abcdef";
const upload = "31234567-89ab-4cde-8123-456789abcdef";
const version = "41234567-89ab-4cde-8123-456789abcdef";
const job = "51234567-89ab-4cde-8123-456789abcdef";
const intent = { uploadId: upload, uploadToken: "u".repeat(43), expiresAt: "2030-01-01T12:00:00Z" };
const received = { uploadId: upload, sizeBytes: 9, sha256: "a".repeat(64), detectedMime: "text/plain" };
const committed = { first_result: { uploadId: upload, documentId: document,
  documentVersionId: version, versionNo: 1, parseJobId: job }, is_current_state_proof: false as const };
const aborted = { first_result: { uploadId: upload, state: "ABORTED" as const,
  cleanupPending: true }, is_current_state_proof: false as const };
const source = { document_id: document, scope: "PROJECT" as const, category: "PROJECT_RECORD" as const,
  subtype: null, title: "调研记录", display_name: "old.txt", state: "ACTIVE" as const,
  latest_version_ref: version, effective_version_ref: version,
  created_at: "2026-09-29T02:00:00Z", etag: '"v2"' };
function response(data: unknown) {
  return new Response(JSON.stringify({ data, trace_id: actor }), { status: 200,
    headers: { "Content-Type": "application/json" } });
}
async function session(role = "PROJECT_MANAGER", login = true) {
  const auth = new SessionClient(vi.fn().mockResolvedValue(response({
    user: { user_id: actor, username_display: "合成用户" }, deployment_role: "NONE",
    password_change_required: false,
    authorized_projects: [{ project_id: project, name: "演示项目", role }],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64),
  })) as typeof fetch);
  if (login) await auth.login("user", "synthetic-only");
  return auth;
}
async function view(auth: SessionClient, path = `/projects/${project}/documents/new`) {
  const documents = new DocumentReadClient(vi.fn() as typeof fetch);
  const get = vi.spyOn(documents, "get").mockResolvedValue(source);
  const creator = new DocumentUploadIntentClient(auth);
  const create = vi.spyOn(creator, "createProject").mockResolvedValue(intent);
  const receiver = new DocumentUploadContentClient(auth);
  const put = vi.spyOn(receiver, "putProject").mockResolvedValue(received);
  const finalizer = new DocumentUploadFinalizeClient(auth);
  const commit = vi.spyOn(finalizer, "commitProject").mockResolvedValue(committed);
  const abort = vi.spyOn(finalizer, "abortProject").mockResolvedValue(aborted);
  const router = createAppRouter(createMemoryHistory());
  await router.push(path); await router.isReady();
  const wrapper = mount(ProjectDocumentUploadView, { props: { session: auth, documents,
    creator, receiver, finalizer }, global: { plugins: [router] } });
  await flushPromises();
  return { wrapper, router, get, create, put, commit, abort };
}
async function fill(wrapper: Awaited<ReturnType<typeof view>>["wrapper"], versionMode = false) {
  if (!versionMode) await wrapper.get("#upload-title-input").setValue("新调研记录");
  const file = new File(["synthetic"], "record.txt", { type: "text/plain" });
  Object.defineProperty(wrapper.get("#upload-file").element, "files", { configurable: true,
    value: { item: (index: number) => index === 0 ? file : null } });
  await wrapper.get("#upload-file").trigger("change");
  await wrapper.get('input[type="checkbox"]').setValue(true);
  return file;
}

describe("ProjectDocumentUploadView", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

  it("does not expose upload form to anonymous or read-only project users", async () => {
    const anonymous = await view(await session("PROJECT_MANAGER", false));
    expect(anonymous.wrapper.find("form").exists()).toBe(false);
    expect(anonymous.create).not.toHaveBeenCalled();
    anonymous.wrapper.unmount();
    const reader = await view(await session("CUSTOMER_MEMBER"));
    expect(reader.wrapper.find("form").exists()).toBe(false);
    expect(reader.create).not.toHaveBeenCalled();
    reader.wrapper.unmount();
  });

  it("creates, uploads and commits once after explicit confirmation, then requires fresh detail read", async () => {
    const { wrapper, create, put, commit } = await view(await session());
    const file = await fill(wrapper);
    await wrapper.get("form").trigger("submit"); await flushPromises();
    expect(create).toHaveBeenCalledTimes(1);
    expect(create.mock.calls[0]?.[0]).toBe(project);
    expect(create.mock.calls[0]?.[1]).toMatchObject({ kind: "NEW", purpose: "SOURCE",
      category: "PROJECT_RECORD", title: "新调研记录", displayName: file.name,
      sizeHintBytes: file.size, mimeHint: file.type });
    expect(put).toHaveBeenCalledWith(project, intent, file);
    expect(commit).toHaveBeenCalledWith(project, received, { kind: "NEW" }, expect.any(String));
    expect(wrapper.text()).toContain("这不是当前状态证明");
    expect(wrapper.get(`a[href$="/documents/${document}"]`).text()).toContain("重新读取文档详情");
    expect(wrapper.find("form").exists()).toBe(false);
    wrapper.unmount();
  });

  it("reads an ACTIVE source and binds version upload to its original Document/ETag", async () => {
    const { wrapper, get, create, commit } = await view(await session("IMPLEMENTATION_MEMBER"),
      `/projects/${project}/documents/${document}/upload`);
    expect(get).toHaveBeenCalledWith({ kind: "PROJECT", projectId: project }, document);
    const file = await fill(wrapper, true);
    await wrapper.get("form").trigger("submit"); await flushPromises();
    expect(create.mock.calls[0]?.[1]).toMatchObject({ kind: "VERSION", documentId: document,
      supersedesVersionId: version, displayName: file.name });
    expect(commit.mock.calls[0]?.[2]).toEqual({ kind: "VERSION", documentId: document, parentEtag: '"v2"' });
    wrapper.unmount();
  });

  it("halts an uncertain Create and only reuses the original key after confirmation", async () => {
    const { wrapper, create, put } = await view(await session());
    create.mockRejectedValueOnce(new DocumentUploadIntentError("DOCUMENT_UPLOAD_CREATE_UNCERTAIN"));
    await fill(wrapper);
    await wrapper.get("form").trigger("submit"); await flushPromises();
    expect(wrapper.text()).toContain("未知阶段：CREATE");
    expect(put).not.toHaveBeenCalled();
    const originalKey = create.mock.calls[0]?.[2];
    const retry = wrapper.get("button[type=button]");
    expect(retry.attributes("disabled")).toBeDefined();
    await wrapper.get('input[type="checkbox"]').setValue(true);
    await retry.trigger("click"); await flushPromises();
    expect(create).toHaveBeenCalledTimes(2);
    expect(create.mock.calls[1]?.[2]).toBe(originalKey);
    expect(put).toHaveBeenCalledTimes(1);
    wrapper.unmount();
  });

  it("stops after a lost Session and shows recovery guidance instead of staying busy", async () => {
    const auth = await session();
    const { wrapper, create, put } = await view(auth);
    create.mockImplementationOnce(async () => {
      try { await auth.logout("synthetic-logout-0001"); } catch { /* synthetic response has no revoked flag */ }
      throw new DocumentUploadIntentError("AUTH_SESSION_EXPIRED");
    });
    await fill(wrapper);
    await wrapper.get("form").trigger("submit"); await flushPromises();
    expect(put).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("当前会话已失效或切换");
    expect(wrapper.text()).toContain("重新登录后继续核对");
    expect(wrapper.text()).not.toContain("正在执行 创建上传意图");
    wrapper.unmount();
  });

  it("offers explicit Abort after a definite content rejection and preserves pending cleanup", async () => {
    const { wrapper, put, commit, abort } = await view(await session());
    put.mockRejectedValueOnce(new DocumentUploadContentError("FILE_TYPE_UNSUPPORTED"));
    await fill(wrapper);
    await wrapper.get("form").trigger("submit"); await flushPromises();
    expect(commit).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("当前上传意图需显式终止");
    await wrapper.get('input[type="checkbox"]').setValue(true);
    await wrapper.get("button[type=button]").trigger("click"); await flushPromises();
    expect(abort).toHaveBeenCalledWith(project, upload, expect.any(String));
    expect(wrapper.text()).toContain("物理清理仍待执行");
    wrapper.unmount();
  });

  it("keeps the Commit key after an unknown result and never creates a second intent", async () => {
    const { wrapper, create, commit } = await view(await session());
    commit.mockRejectedValueOnce(new DocumentUploadFinalizeError("DOCUMENT_UPLOAD_FINALIZE_UNCERTAIN"));
    await fill(wrapper);
    await wrapper.get("form").trigger("submit"); await flushPromises();
    expect(wrapper.text()).toContain("未知阶段：COMMIT");
    const originalKey = commit.mock.calls[0]?.[3];
    await wrapper.get('input[type="checkbox"]').setValue(true);
    await wrapper.get("button[type=button]").trigger("click"); await flushPromises();
    expect(create).toHaveBeenCalledTimes(1);
    expect(commit).toHaveBeenCalledTimes(2);
    expect(commit.mock.calls[1]?.[3]).toBe(originalKey);
    wrapper.unmount();
  });

  it("discards a late Create result after switching projects", async () => {
    const { wrapper, router, create, put } = await view(await session());
    let finish!: (value: typeof intent) => void;
    create.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve; }));
    await fill(wrapper);
    await wrapper.get("form").trigger("submit");
    await router.push(`/projects/${actor}/documents/new`); await flushPromises();
    finish(intent); await flushPromises();
    expect(put).not.toHaveBeenCalled();
    expect(wrapper.text()).not.toContain("首次提交回执");
    wrapper.unmount();
  });
});
