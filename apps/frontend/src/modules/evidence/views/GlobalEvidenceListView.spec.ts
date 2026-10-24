import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { EvidenceListClient } from "@/modules/evidence/api/evidenceListClient";
import { EvidenceViewerClient } from "@/modules/evidence/api/evidenceViewerClient";
import { EvidenceEligibilityClient } from "@/modules/evidence/api/evidenceEligibilityClient";
import { EvidenceEligibilityOperationLookupClient } from "@/modules/evidence/api/evidenceEligibilityOperationLookupClient";
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
async function view(admin: boolean, lists: object, viewers: object, eligibility: object,
                    lookup?: object) {
  const router = createAppRouter(createMemoryHistory());
  await router.push("/admin/evidence"); await router.isReady();
  const wrapper = mount(GlobalEvidenceListView, { props: { session: await session(admin),
    listClient: lists as EvidenceListClient, viewerClient: viewers as EvidenceViewerClient,
    eligibilityClient: eligibility as EvidenceEligibilityClient,
    eligibilityLookupClient: lookup as EvidenceEligibilityOperationLookupClient | undefined },
  global: { plugins: [router] } });
  await flushPromises();
  return wrapper;
}

describe("GlobalEvidenceListView", () => {
  afterEach(() => { vi.restoreAllMocks(); window.sessionStorage.clear(); });

  it("requires the original receipt and a fresh current GET before manual reminder clearance", async () => {
    const pendingKey = `plm.evidence.global.eligibility.pending.${actorId}`;
    window.sessionStorage.setItem(pendingKey, JSON.stringify({ actorId, evidenceId, key: "k".repeat(16) }));
    const lists = { list: vi.fn().mockResolvedValue({ items: [item], next_cursor: null, has_more: false }) };
    const lookup = { lookupGlobal: vi.fn().mockResolvedValue({ status: "COMPLETED",
      evidence_id: evidenceId, first_status_code: 200, is_current_state_proof: false }) };
    const eligibility = { currentGlobal: vi.fn().mockResolvedValue({ evidence_id: evidenceId,
      document_id: documentId, document_version_id: versionId,
      eligibility_state: "REVOKED", etag: '"v2"' }), setGlobal: vi.fn() };
    const wrapper = await view(true, lists, { get: vi.fn() }, eligibility, lookup);
    await wrapper.findAll("button").find((button) => button.text() === "按原操作号回查")!.trigger("click");
    await flushPromises();
    expect(lookup.lookupGlobal).toHaveBeenCalledWith(evidenceId, "k".repeat(16));
    expect(eligibility.currentGlobal).toHaveBeenCalledWith(evidenceId);
    expect(wrapper.text()).toContain("仅证明历史提交");
    expect(wrapper.text()).toContain("当前资格：已撤销");
    expect(window.sessionStorage.getItem(pendingKey)).not.toBeNull();
    await wrapper.findAll("button").find((button) => button.text() === "已核对当前资格，清除待核对提醒")!
      .trigger("click");
    expect(window.sessionStorage.getItem(pendingKey)).toBeNull();
    expect(eligibility.setGlobal).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it("keeps the global operation locked on unconfirmed receipt or current GET failure", async () => {
    const pendingKey = `plm.evidence.global.eligibility.pending.${actorId}`;
    window.sessionStorage.setItem(pendingKey, JSON.stringify({ actorId, evidenceId, key: "k".repeat(16) }));
    const lists = { list: vi.fn().mockResolvedValue({ items: [item], next_cursor: null, has_more: false }) };
    const lookup = { lookupGlobal: vi.fn().mockResolvedValueOnce({ status: "UNCONFIRMED",
      is_current_state_proof: false }).mockResolvedValueOnce({ status: "COMPLETED",
      evidence_id: evidenceId, first_status_code: 200, is_current_state_proof: false }) };
    const eligibility = { currentGlobal: vi.fn().mockRejectedValue(new Error("read failed")),
      setGlobal: vi.fn() };
    const wrapper = await view(true, lists, { get: vi.fn() }, eligibility, lookup);
    await wrapper.findAll("button").find((button) => button.text() === "按原操作号回查")!.trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("尚不能确认原操作是否提交");
    expect(eligibility.currentGlobal).not.toHaveBeenCalled();
    await wrapper.findAll("button").find((button) => button.text() === "按原操作号回查")!.trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("暂时无法核对原操作");
    expect(wrapper.text()).not.toContain("已核对当前资格，清除待核对提醒");
    expect(window.sessionStorage.getItem(pendingKey)).not.toBeNull();
    wrapper.unmount();
  });

  it("saves a global operation key before the human POST and clears it on a verified receipt", async () => {
    const lists = { list: vi.fn().mockResolvedValue({ items: [item], next_cursor: null, has_more: false }) };
    const viewers = { get: vi.fn().mockResolvedValue(descriptor) };
    const eligibility = { currentGlobal: vi.fn().mockResolvedValue({ evidence_id: evidenceId,
      document_id: documentId, document_version_id: versionId,
      eligibility_state: "CANDIDATE", etag: '"v0"' }),
    setGlobal: vi.fn().mockImplementation(async () => {
      expect(window.sessionStorage.length).toBe(1);
      return { evidence_id: evidenceId, eligibility_state: "ELIGIBLE",
        eligibility_reason: "核对标准说明第2页", etag: '"v1"', is_current_state_proof: false };
    }) };
    const wrapper = await view(true, lists, viewers, eligibility);
    await wrapper.findAll("button").find((button) => button.text() === "定位固定原文")!.trigger("click");
    await flushPromises();
    const submit = wrapper.findAll("button").find((button) => button.text() === "提交资格裁定")!;
    expect(submit.attributes("disabled")).toBeDefined();
    await wrapper.find('input[value="ELIGIBLE"]').setValue();
    await wrapper.get("textarea").setValue("核对标准说明第2页");
    await wrapper.find('input[type="checkbox"]').setValue(true);
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(eligibility.setGlobal).toHaveBeenCalledOnce();
    expect(eligibility.setGlobal.mock.calls[0]?.[0]).toMatchObject({ etag: '"v0"' });
    expect(eligibility.setGlobal.mock.calls[0]?.[1]).toEqual(descriptor);
    expect(eligibility.setGlobal.mock.calls[0]?.[4]).toMatch(/^[\x20-\x7e]{16,128}$/);
    expect(window.sessionStorage.length).toBe(0);
    expect(wrapper.text()).toContain("回执不代表当前状态");
    wrapper.unmount();
  });

  it("retains an uncertain global key across a page reload and blocks new decisions", async () => {
    const lists = { list: vi.fn().mockResolvedValue({ items: [item], next_cursor: null, has_more: false }) };
    const viewers = { get: vi.fn().mockResolvedValue(descriptor) };
    const eligibility = { currentGlobal: vi.fn().mockResolvedValue({ evidence_id: evidenceId,
      document_id: documentId, document_version_id: versionId,
      eligibility_state: "CANDIDATE", etag: '"v0"' }),
    setGlobal: vi.fn().mockRejectedValue(new Error("network gone")) };
    const wrapper = await view(true, lists, viewers, eligibility);
    await wrapper.findAll("button").find((button) => button.text() === "定位固定原文")!.trigger("click");
    await flushPromises();
    await wrapper.find('input[value="INELIGIBLE"]').setValue();
    await wrapper.get("textarea").setValue("实际来源不支持");
    await wrapper.find('input[type="checkbox"]').setValue(true);
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(wrapper.text()).toContain("结果尚未确认");
    expect(window.sessionStorage.length).toBe(1);
    wrapper.unmount();
    const reloaded = await view(true, lists, viewers, eligibility);
    expect(reloaded.text()).toContain("一项 GLOBAL 资格操作结果尚未确认");
    await reloaded.findAll("button").find((button) => button.text() === "定位固定原文")!.trigger("click");
    await flushPromises();
    expect(reloaded.find("form").exists()).toBe(false);
    expect(eligibility.setGlobal).toHaveBeenCalledOnce();
    reloaded.unmount();
  });

  it("does not send a global decision when operation storage fails", async () => {
    const lists = { list: vi.fn().mockResolvedValue({ items: [item], next_cursor: null, has_more: false }) };
    const viewers = { get: vi.fn().mockResolvedValue(descriptor) };
    const eligibility = { currentGlobal: vi.fn().mockResolvedValue({ evidence_id: evidenceId,
      document_id: documentId, document_version_id: versionId,
      eligibility_state: "CANDIDATE", etag: '"v0"' }), setGlobal: vi.fn() };
    const wrapper = await view(true, lists, viewers, eligibility);
    await wrapper.findAll("button").find((button) => button.text() === "定位固定原文")!.trigger("click");
    await flushPromises();
    await wrapper.find('input[value="ELIGIBLE"]').setValue();
    await wrapper.get("textarea").setValue("核对标准说明");
    await wrapper.find('input[type="checkbox"]').setValue(true);
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("storage unavailable"); });
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(eligibility.setGlobal).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("资格请求未发送");
    wrapper.unmount();
  });
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
