import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { EvidenceListClient } from "@/modules/evidence/api/evidenceListClient";
import { EvidenceViewerClient } from "@/modules/evidence/api/evidenceViewerClient";
import ProjectEvidenceListView from "./ProjectEvidenceListView.vue";

const projectId = "01234567-89ab-4cde-8123-456789abcdef";
const evidenceId = "11234567-89ab-4cde-8123-456789abcdef";
const documentId = "21234567-89ab-4cde-8123-456789abcdef";
const versionId = "31234567-89ab-4cde-8123-456789abcdef";
const traceId = "41234567-89ab-4cde-8123-456789abcdef";
const item = { evidence_id: evidenceId, document_id: documentId,
  document_version_id: versionId, display_label: "第 2 页", display_excerpt: "短提示",
  eligibility_state: "CANDIDATE", created_at: "2026-10-01T02:00:00Z" };
const descriptor = { evidence_id: evidenceId, document_id: documentId,
  document_version_id: versionId, document_version_no: 2, detected_mime: "application/pdf",
  size_bytes: 120, locator: { locator_type: "PAGE", page_no: 2 }, precision: "PARSED_NODE",
  display_label: "第 2 页", short_preview: "第 2 页的提示",
  content_url: `/api/v1/projects/${projectId}/documents/${documentId}/versions/${versionId}/content` };
function response(data: unknown): Response {
  return new Response(JSON.stringify({ data, trace_id: traceId }), { status: 200,
    headers: { "Content-Type": "application/json" } });
}
function failure(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: "private" }, trace_id: traceId }),
    { status, headers: { "Content-Type": "application/json" } });
}
async function session(restricted = false): Promise<SessionClient> {
  const auth = new SessionClient(vi.fn().mockResolvedValue(response({
    user: { user_id: projectId, username_display: "合成用户" }, deployment_role: "NONE",
    password_change_required: restricted,
    authorized_projects: restricted ? [] : [{ project_id: projectId, name: "演示项目", role: "PROJECT_MANAGER" }],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64),
  })) as typeof fetch);
  await auth.login("user", "synthetic-only");
  return auth;
}
async function view(auth: SessionClient, listFetcher: typeof fetch, viewerFetcher: typeof fetch,
                    previewFetch?: typeof fetch) {
  const router = createAppRouter(createMemoryHistory());
  await router.push(`/projects/${projectId}/evidence`);
  await router.isReady();
  const wrapper = mount(ProjectEvidenceListView, { props: { session: auth,
    listClient: new EvidenceListClient(listFetcher), viewerClient: new EvidenceViewerClient(viewerFetcher),
    previewFetch },
  global: { plugins: [router] } });
  await flushPromises();
  return { wrapper, router };
}

describe("ProjectEvidenceListView", () => {
  afterEach(() => vi.restoreAllMocks());

  it("does not load without identity or before required password change", async () => {
    const listFetcher = vi.fn();
    const viewerFetcher = vi.fn();
    const absent = await view(new SessionClient(listFetcher as typeof fetch),
      listFetcher as typeof fetch, viewerFetcher as typeof fetch);
    expect(absent.wrapper.text()).toContain("尚未读取当前身份");
    absent.wrapper.unmount();
    const restricted = await view(await session(true), listFetcher as typeof fetch,
      viewerFetcher as typeof fetch);
    expect(restricted.wrapper.text()).toContain("须先修改密码");
    expect(listFetcher).not.toHaveBeenCalled();
    expect(viewerFetcher).not.toHaveBeenCalled();
    restricted.wrapper.unmount();
  });

  it("requires a fresh Viewer proof before showing fixed content link", async () => {
    const listFetcher = vi.fn().mockResolvedValue(response({ items: [item], next_cursor: null,
      has_more: false }));
    const viewerFetcher = vi.fn().mockResolvedValue(response(descriptor));
    const { wrapper } = await view(await session(), listFetcher as typeof fetch,
      viewerFetcher as typeof fetch);
    expect(wrapper.text()).toContain("短提示");
    expect(wrapper.find(`a[href="${descriptor.content_url}"]`).exists()).toBe(false);
    await wrapper.findAll("button").find((button) => button.text() === "定位原文")!.trigger("click");
    await flushPromises();
    expect(viewerFetcher.mock.calls[0]?.[0]).toBe(
      `/api/v1/projects/${projectId}/evidence/${evidenceId}/viewer`);
    expect(wrapper.text()).toContain("第 2 页");
    expect(wrapper.text()).toContain("解析节点已核验");
    expect(wrapper.get(`a[href="${descriptor.content_url}"]`).text()).toContain("下载固定版本原文");
    expect(wrapper.text()).toContain("精确高亮尚未提供");
    expect(wrapper.text()).not.toContain("storage_locator");
    wrapper.unmount();
  });

  it("does not show a content link after integrity failure", async () => {
    const listFetcher = vi.fn().mockResolvedValue(response({ items: [item], next_cursor: null,
      has_more: false }));
    const viewerFetcher = vi.fn().mockResolvedValue(failure(409, "EVIDENCE_FINGERPRINT_MISMATCH"));
    const { wrapper } = await view(await session(), listFetcher as typeof fetch,
      viewerFetcher as typeof fetch);
    await wrapper.findAll("button").find((button) => button.text() === "定位原文")!.trigger("click");
    await flushPromises();
    expect(wrapper.get("[role=alert]").text()).toContain("完整性验证未通过");
    expect(wrapper.find(`a[href="${descriptor.content_url}"]`).exists()).toBe(false);
    wrapper.unmount();
  });

  it("loads only the verified fixed PDF as a bounded page-level blob and revokes it", async () => {
    const listFetcher = vi.fn().mockResolvedValue(response({ items: [item], next_cursor: null,
      has_more: false }));
    const viewerFetcher = vi.fn().mockResolvedValue(response(descriptor));
    const pdf = new Uint8Array(120); pdf.set(new TextEncoder().encode("%PDF-1.7"));
    const previewFetch = vi.fn().mockResolvedValue(new Response(pdf, { status: 200,
      headers: { "Content-Type": "application/pdf", "Content-Length": "120" } }));
    const create = vi.fn().mockReturnValue("blob:https://plm.example.test/fixed");
    const revoke = vi.fn();
    Object.defineProperty(URL, "createObjectURL", { configurable: true, value: create });
    Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: revoke });
    const { wrapper } = await view(await session(), listFetcher as typeof fetch,
      viewerFetcher as typeof fetch, previewFetch as typeof fetch);
    await wrapper.findAll("button").find((button) => button.text() === "定位原文")!.trigger("click");
    await flushPromises();
    await wrapper.findAll("button").find((button) => button.text() === "预览固定版本 PDF")!.trigger("click");
    await flushPromises();
    expect(previewFetch).toHaveBeenCalledExactlyOnceWith(descriptor.content_url,
      expect.objectContaining({ credentials: "same-origin", redirect: "error",
        headers: { Accept: "application/pdf" } }));
    expect(wrapper.get("iframe").attributes("src")).toBe("blob:https://plm.example.test/fixed#page=2");
    expect(wrapper.get("iframe").attributes("sandbox")).toBe("allow-same-origin");
    wrapper.unmount();
    expect(revoke).toHaveBeenCalledWith("blob:https://plm.example.test/fixed");
  });

  it("keeps the fixed download when PDF inline preview is too large", async () => {
    const listFetcher = vi.fn().mockResolvedValue(response({ items: [item], next_cursor: null,
      has_more: false }));
    const viewerFetcher = vi.fn().mockResolvedValue(response({ ...descriptor, size_bytes: 20_000_001 }));
    const previewFetch = vi.fn();
    const { wrapper } = await view(await session(), listFetcher as typeof fetch,
      viewerFetcher as typeof fetch, previewFetch as typeof fetch);
    await wrapper.findAll("button").find((button) => button.text() === "定位原文")!.trigger("click");
    await flushPromises();
    await wrapper.findAll("button").find((button) => button.text() === "预览固定版本 PDF")!.trigger("click");
    await flushPromises();
    expect(previewFetch).not.toHaveBeenCalled();
    expect(wrapper.find("iframe").exists()).toBe(false);
    expect(wrapper.text()).toContain("超过 20 MB");
    expect(wrapper.find(`a[href="${descriptor.content_url}"]`).exists()).toBe(true);
    wrapper.unmount();
  });

  it("rejects wrong PDF response type without embedding bytes", async () => {
    const listFetcher = vi.fn().mockResolvedValue(response({ items: [item], next_cursor: null,
      has_more: false }));
    const viewerFetcher = vi.fn().mockResolvedValue(response(descriptor));
    const previewFetch = vi.fn().mockResolvedValue(new Response("not a PDF", { status: 200,
      headers: { "Content-Type": "text/plain", "Content-Length": "9" } }));
    const { wrapper } = await view(await session(), listFetcher as typeof fetch,
      viewerFetcher as typeof fetch, previewFetch as typeof fetch);
    await wrapper.findAll("button").find((button) => button.text() === "定位原文")!.trigger("click");
    await flushPromises();
    await wrapper.findAll("button").find((button) => button.text() === "预览固定版本 PDF")!.trigger("click");
    await flushPromises();
    expect(wrapper.find("iframe").exists()).toBe(false);
    expect(wrapper.text()).toContain("PDF 页级预览不可用");
    expect(wrapper.find(`a[href="${descriptor.content_url}"]`).exists()).toBe(true);
    wrapper.unmount();
  });
});
