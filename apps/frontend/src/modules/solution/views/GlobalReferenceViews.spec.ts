import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { GlobalReferenceReadClient } from "@/modules/solution/api/globalReferenceReadClient";
import { EvidenceViewerClient } from "@/modules/evidence/api/evidenceViewerClient";
import GlobalReferenceListView from "./GlobalReferenceListView.vue";
import GlobalReferenceDetailView from "./GlobalReferenceDetailView.vue";

const reference = "11234567-89ab-4cde-8123-456789abcdef";
const version = "21234567-89ab-4cde-8123-456789abcdef";
const document = "31234567-89ab-4cde-8123-456789abcdef";
const documentVersion = "41234567-89ab-4cde-8123-456789abcdef";
const evidence = "51234567-89ab-4cde-8123-456789abcdef";
const actor = "61234567-89ab-4cde-8123-456789abcdef";
const item = { reference_solution_id: reference, reference_version_id: version, scope: "GLOBAL",
  project_id: null, name: "历史全局方案", eligibility_state: "REFERENCE_ONLY", version_no: 1,
  version_state: "DRAFT", created_at: "2026-10-09T00:00:00Z", etag: '"v0"' };
const detail = { ...item, eligibility_reason: null, source_project_class: "PLM",
  deidentification_class: "DEIDENTIFIED", applicability: {}, document_version_ids: [documentVersion],
  document_refs: [{ document_id: document, document_version_id: documentVersion }],
  evidence_ids: [evidence], source_fingerprint: "a".repeat(64), content_fingerprint: "b".repeat(64),
  created_by: actor, version_created_by: actor, version_created_at: "2026-10-09T00:00:00Z" };
function success(data: unknown): Response {
  return new Response(JSON.stringify({ data, trace_id: actor }), { status: 200,
    headers: { "Content-Type": "application/json" } });
}
async function session(role: "DEPLOYMENT_ADMIN" | "NONE"): Promise<SessionClient> {
  const api = new SessionClient(vi.fn().mockResolvedValue(success({
    user: { user_id: actor, username_display: "合成用户" }, deployment_role: role,
    password_change_required: false, authorized_projects: [],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64),
  })) as typeof fetch);
  await api.login("user", "synthetic-only"); return api;
}

describe("GLOBAL Reference pages", () => {
  afterEach(() => vi.restoreAllMocks());
  it("resolves admin candidate/detail routes", () => {
    const router = createAppRouter(createMemoryHistory());
    expect(router.resolve("/admin/reference-solutions").name).toBe("global-references");
    expect(router.resolve(`/admin/reference-solutions/${reference}`).name).toBe("global-reference-detail");
  });

  it("lets only an admin read candidates and open historical detail", async () => {
    const router = createAppRouter(createMemoryHistory());
    await router.push("/admin/reference-solutions"); await router.isReady();
    const reader = { list: vi.fn().mockResolvedValue({ items: [item], next_cursor: null, has_more: false }) };
    const wrapper = mount(GlobalReferenceListView, { props: { session: await session("DEPLOYMENT_ADMIN"),
      reader: reader as unknown as GlobalReferenceReadClient }, global: { plugins: [router] } });
    expect(reader.list).not.toHaveBeenCalled();
    await wrapper.get("button").trigger("click"); await flushPromises();
    expect(reader.list).toHaveBeenCalledWith(50, null);
    expect(wrapper.text()).toContain("历史固定来源");
    expect(wrapper.get(`a[href="/admin/reference-solutions/${reference}"]`).text()).toContain("固定来源");
    wrapper.unmount();

    const denied = { list: vi.fn() };
    const no = mount(GlobalReferenceListView, { props: { session: await session("NONE"),
      reader: denied as unknown as GlobalReferenceReadClient }, global: { plugins: [router] } });
    expect(no.text()).toContain("无权查看");
    expect(no.find("button").exists()).toBe(false);
    expect(denied.list).not.toHaveBeenCalled();
    no.unmount();
  });

  it("opens fixed document content and resolves evidence only through GLOBAL viewer", async () => {
    const router = createAppRouter(createMemoryHistory());
    await router.push(`/admin/reference-solutions/${reference}`); await router.isReady();
    const reader = { current: vi.fn().mockResolvedValue(detail) };
    const viewer = { get: vi.fn().mockResolvedValue({ evidence_id: evidence, document_id: document,
      document_version_id: documentVersion, document_version_no: 1, detected_mime: "application/pdf",
      size_bytes: 128, locator: { locator_type: "PAGE", page_no: 3 }, precision: "PARSED_NODE",
      display_label: "第三页", short_preview: "合成提示",
      content_url: `/api/v1/global/evidence/${evidence}/content` }) };
    const wrapper = mount(GlobalReferenceDetailView, { props: { session: await session("DEPLOYMENT_ADMIN"),
      reader: reader as unknown as GlobalReferenceReadClient, viewer: viewer as unknown as EvidenceViewerClient },
      global: { plugins: [router] } });
    await flushPromises();
    expect(reader.current).toHaveBeenCalledWith(reference);
    expect(wrapper.get(`a[href="/api/v1/global/documents/${document}/versions/${documentVersion}/content"]`).text())
      .toContain("固定文档版本原文");
    expect(wrapper.text()).toContain("历史固定引用");
    expect(viewer.get).not.toHaveBeenCalled();
    await wrapper.findAll("button").find(button => button.text() === "核验并定位原文")!.trigger("click");
    await flushPromises();
    expect(viewer.get).toHaveBeenCalledWith({ kind: "GLOBAL" }, evidence);
    expect(wrapper.text()).toContain("第 3 页");
    expect(wrapper.get(`a[href="/api/v1/global/evidence/${evidence}/content"]`).text())
      .toContain("下载固定证据原文");
    wrapper.unmount();
  });

  it("does not request detail for non-admin and shows read failure without source links", async () => {
    const router = createAppRouter(createMemoryHistory());
    await router.push(`/admin/reference-solutions/${reference}`); await router.isReady();
    const deniedReader = { current: vi.fn() };
    const denied = mount(GlobalReferenceDetailView, { props: { session: await session("NONE"),
      reader: deniedReader as unknown as GlobalReferenceReadClient }, global: { plugins: [router] } });
    await flushPromises();
    expect(denied.text()).toContain("无权查看");
    expect(deniedReader.current).not.toHaveBeenCalled();
    denied.unmount();

    const failingReader = { current: vi.fn().mockRejectedValue(new Error("读取被拒绝")) };
    const failed = mount(GlobalReferenceDetailView, { props: { session: await session("DEPLOYMENT_ADMIN"),
      reader: failingReader as unknown as GlobalReferenceReadClient }, global: { plugins: [router] } });
    await flushPromises();
    expect(failed.get('[role="alert"]').text()).toContain("读取被拒绝");
    expect(failed.find(`a[href="/api/v1/global/documents/${document}/versions/${documentVersion}/content"]`).exists())
      .toBe(false);
    failed.unmount();
  });
});
