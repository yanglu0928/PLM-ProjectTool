import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { ReferenceReadClient } from "@/modules/solution/api/referenceReadClient";
import { EvidenceViewerClient } from "@/modules/evidence/api/evidenceViewerClient";
import ProjectReferenceListView from "./ProjectReferenceListView.vue";
import ProjectReferenceDetailView from "./ProjectReferenceDetailView.vue";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const reference = "11234567-89ab-4cde-8123-456789abcdef";
const version = "21234567-89ab-4cde-8123-456789abcdef";
const document = "31234567-89ab-4cde-8123-456789abcdef";
const documentVersion = "41234567-89ab-4cde-8123-456789abcdef";
const evidence = "51234567-89ab-4cde-8123-456789abcdef";
const date = "2026-10-09T00:00:00Z";
const item = { reference_solution_id: reference, reference_version_id: version, scope: "PROJECT",
  project_id: project, name: "历史方案", eligibility_state: "REFERENCE_ONLY", version_no: 1,
  version_state: "DRAFT", created_at: date, etag: '"v0"' };
const detail = { ...item, eligibility_reason: null, source_project_class: "PLM",
  deidentification_class: "PROJECT_INTERNAL", applicability: {}, document_version_ids: [documentVersion],
  document_refs: [{ document_id: document, document_version_id: documentVersion }],
  evidence_ids: [evidence], source_fingerprint: "a".repeat(64), content_fingerprint: "b".repeat(64),
  created_by: project, version_created_by: project, version_created_at: date };
function success(data: unknown): Response {
  return new Response(JSON.stringify({ data, trace_id: project }), { status: 200,
    headers: { "Content-Type": "application/json" } });
}
async function session(): Promise<SessionClient> {
  const api = new SessionClient(vi.fn().mockResolvedValue(success({
    user: { user_id: project, username_display: "合成用户" }, deployment_role: "NONE",
    password_change_required: false, authorized_projects: [{ project_id: project, name: "项目", role: "CUSTOMER_MEMBER" }],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64),
  })) as typeof fetch);
  await api.login("user", "synthetic-only"); return api;
}
describe("PROJECT Reference pages", () => {
  afterEach(() => vi.restoreAllMocks());
  it("offers a project-only list and fixed-source detail link", async () => {
    const router = createAppRouter(createMemoryHistory());
    await router.push(`/projects/${project}/reference-solutions`); await router.isReady();
    const reader = { list: vi.fn().mockResolvedValue({ items: [item], next_cursor: null, has_more: false }) };
    const wrapper = mount(ProjectReferenceListView, { props: { session: await session(), reader: reader as unknown as ReferenceReadClient },
      global: { plugins: [router] } });
    await flushPromises();
    expect(reader.list).toHaveBeenCalledWith(project, 50, null);
    expect(wrapper.text()).toContain("历史固定来源");
    expect(wrapper.get(`a[href="/projects/${project}/reference-solutions/${reference}"]`).text())
      .toContain("固定来源");
    wrapper.unmount();
  });

  it("links the exact document version and resolves Evidence only through its authorized viewer", async () => {
    const router = createAppRouter(createMemoryHistory());
    await router.push(`/projects/${project}/reference-solutions/${reference}`); await router.isReady();
    const reader = { current: vi.fn().mockResolvedValue(detail) };
    const viewer = { get: vi.fn().mockResolvedValue({ evidence_id: evidence, document_id: document,
      document_version_id: documentVersion, document_version_no: 1, detected_mime: "application/pdf",
      size_bytes: 128, locator: { locator_type: "PAGE", page_no: 3 }, precision: "PARSED_NODE",
      display_label: "第三页", short_preview: "合成提示", content_url: `/api/v1/projects/${project}/evidence/${evidence}/content` }) };
    const wrapper = mount(ProjectReferenceDetailView, { props: { session: await session(),
      reader: reader as unknown as ReferenceReadClient, viewer: viewer as unknown as EvidenceViewerClient },
      global: { plugins: [router] } });
    await flushPromises();
    expect(reader.current).toHaveBeenCalledWith(project, reference);
    expect(wrapper.findAll("a").some(link => link.attributes("href")?.includes(
      `documents/${document}?versionId=${documentVersion}`))).toBe(true);
    expect(wrapper.text()).toContain("历史固定引用");
    await wrapper.get("button").trigger("click"); // refresh does not grant Evidence access
    await flushPromises();
    expect(viewer.get).not.toHaveBeenCalled();
    await wrapper.findAll("button").find(button => button.text() === "核验并定位原文")!.trigger("click");
    await flushPromises();
    expect(viewer.get).toHaveBeenCalledWith({ kind: "PROJECT", projectId: project }, evidence);
    expect(wrapper.text()).toContain("第三页");
    expect(wrapper.text()).toContain("第 3 页");
    expect(wrapper.get(`a[href="/api/v1/projects/${project}/evidence/${evidence}/content"]`).text())
      .toContain("下载固定证据原文");
    wrapper.unmount();
  });
});
