import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { describe, expect, it, vi } from "vitest";

import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { EvidenceListClient } from "@/modules/evidence/api/evidenceListClient";
import { EvidenceViewerClient } from "@/modules/evidence/api/evidenceViewerClient";
import { EvidenceEligibilityClient } from "@/modules/evidence/api/evidenceEligibilityClient";
import GlobalEvidenceListView from "./GlobalEvidenceListView.vue";

const actorId = "01234567-89ab-4cde-8123-456789abcdef";
const evidenceId = "11234567-89ab-4cde-8123-456789abcdef";
const documentId = "21234567-89ab-4cde-8123-456789abcdef";
const versionId = "31234567-89ab-4cde-8123-456789abcdef";
const traceId = "41234567-89ab-4cde-8123-456789abcdef";
const item = { evidence_id: evidenceId, document_id: documentId,
  document_version_id: versionId, display_label: "标准说明第 2 页", display_excerpt: "短提示",
  eligibility_state: "CANDIDATE", created_at: "2026-10-01T02:00:00Z" };
const descriptor = { evidence_id: evidenceId, document_id: documentId,
  document_version_id: versionId, document_version_no: 2, detected_mime: "application/pdf",
  size_bytes: 120, locator: { locator_type: "PAGE", page_no: 2 }, precision: "PARSED_NODE",
  display_label: "第 2 页", short_preview: "提示",
  content_url: `/api/v1/global/documents/${documentId}/versions/${versionId}/content` };
function response(data: unknown): Response {
  return new Response(JSON.stringify({ data, trace_id: traceId }), { status: 200,
    headers: { "Content-Type": "application/json" } });
}
async function session(admin: boolean): Promise<SessionClient> {
  const view = { user: { user_id: actorId, username_display: "合成用户" },
    deployment_role: admin ? "DEPLOYMENT_ADMIN" : "NONE", password_change_required: false,
    authorized_projects: [], absolute_expires_at: "2030-01-01T12:00:00Z",
    idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "a".repeat(64) };
  const result = new SessionClient(vi.fn().mockResolvedValue(response(view)) as typeof fetch);
  await result.login("user", "synthetic-only");
  return result;
}
async function view(admin: boolean, lists: object, viewers: object, eligibility: object) {
  const router = createAppRouter(createMemoryHistory());
  await router.push("/admin/evidence"); await router.isReady();
  const wrapper = mount(GlobalEvidenceListView, { props: { session: await session(admin),
    listClient: lists as EvidenceListClient, viewerClient: viewers as EvidenceViewerClient,
    eligibilityClient: eligibility as EvidenceEligibilityClient }, global: { plugins: [router] } });
  await flushPromises();
  return wrapper;
}

describe("GlobalEvidenceListView", () => {
  it("makes no Evidence request for a non-admin identity", async () => {
    const lists = { list: vi.fn() }; const viewers = { get: vi.fn() };
    const eligibility = { currentGlobal: vi.fn() };
    const wrapper = await view(false, lists, viewers, eligibility);
    expect(wrapper.text()).toContain("当前身份无权查看全局证据");
    expect(lists.list).not.toHaveBeenCalled();
    expect(viewers.get).not.toHaveBeenCalled();
    expect(eligibility.currentGlobal).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it("lists global summaries and only exposes fixed content after Viewer and current GET", async () => {
    const lists = { list: vi.fn().mockResolvedValue({ items: [item], next_cursor: null, has_more: false }) };
    const viewers = { get: vi.fn().mockResolvedValue(descriptor) };
    const eligibility = { currentGlobal: vi.fn().mockResolvedValue({ evidence_id: evidenceId,
      document_id: documentId, document_version_id: versionId,
      eligibility_state: "ELIGIBLE", etag: '"v1"' }) };
    const wrapper = await view(true, lists, viewers, eligibility);
    expect(lists.list).toHaveBeenCalledWith({ kind: "GLOBAL" }, null);
    expect(wrapper.find(`a[href="${descriptor.content_url}"]`).exists()).toBe(false);
    await wrapper.findAll("button").find((button) => button.text() === "定位固定原文")!.trigger("click");
    await flushPromises();
    expect(viewers.get).toHaveBeenCalledWith({ kind: "GLOBAL" }, evidenceId);
    expect(eligibility.currentGlobal).toHaveBeenCalledWith(evidenceId);
    expect(wrapper.text()).toContain("当前资格：可用");
    expect(wrapper.get(`a[href="${descriptor.content_url}"]`).text()).toContain("下载受权固定版本原文");
    wrapper.unmount();
  });

  it("rejects a Viewer source mismatch without reading current state or exposing content", async () => {
    const lists = { list: vi.fn().mockResolvedValue({ items: [item], next_cursor: null, has_more: false }) };
    const viewers = { get: vi.fn().mockResolvedValue({ ...descriptor, document_version_id: evidenceId }) };
    const eligibility = { currentGlobal: vi.fn() };
    const wrapper = await view(true, lists, viewers, eligibility);
    await wrapper.findAll("button").find((button) => button.text() === "定位固定原文")!.trigger("click");
    await flushPromises();
    expect(eligibility.currentGlobal).not.toHaveBeenCalled();
    expect(wrapper.find(`a[href="${descriptor.content_url}"]`).exists()).toBe(false);
    expect(wrapper.get("[role=alert]").text()).toContain("无法定位原文");
    wrapper.unmount();
  });

  it("hides fixed content when current Evidence source no longer matches the Viewer", async () => {
    const lists = { list: vi.fn().mockResolvedValue({ items: [item], next_cursor: null, has_more: false }) };
    const viewers = { get: vi.fn().mockResolvedValue(descriptor) };
    const eligibility = { currentGlobal: vi.fn().mockResolvedValue({ evidence_id: evidenceId,
      document_id: documentId, document_version_id: actorId,
      eligibility_state: "ELIGIBLE", etag: '"v1"' }) };
    const wrapper = await view(true, lists, viewers, eligibility);
    await wrapper.findAll("button").find((button) => button.text() === "定位固定原文")!.trigger("click");
    await flushPromises();
    expect(wrapper.find(`a[href="${descriptor.content_url}"]`).exists()).toBe(false);
    expect(wrapper.get("[role=alert]").text()).toContain("暂无法确认");
    wrapper.unmount();
  });

  it("drops a previously verified link when the list is refreshed", async () => {
    const lists = { list: vi.fn().mockResolvedValue({ items: [item], next_cursor: null, has_more: false }) };
    const viewers = { get: vi.fn().mockResolvedValue(descriptor) };
    const eligibility = { currentGlobal: vi.fn().mockResolvedValue({ evidence_id: evidenceId,
      document_id: documentId, document_version_id: versionId,
      eligibility_state: "CANDIDATE", etag: '"v0"' }) };
    const wrapper = await view(true, lists, viewers, eligibility);
    await wrapper.findAll("button").find((button) => button.text() === "定位固定原文")!.trigger("click");
    await flushPromises();
    expect(wrapper.find(`a[href="${descriptor.content_url}"]`).exists()).toBe(true);
    await wrapper.findAll("button").find((button) => button.text() === "刷新全局证据")!.trigger("click");
    await flushPromises();
    expect(wrapper.find(`a[href="${descriptor.content_url}"]`).exists()).toBe(false);
    wrapper.unmount();
  });
});
