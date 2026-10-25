import { defineComponent } from "vue";
import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory, createRouter } from "vue-router";
import { describe, expect, it, vi } from "vitest";

import { SessionClient } from "@/modules/auth/api/sessionClient";
import { PrototypeWriteError } from "@/modules/prototype/api/prototypeWriteClient";
import GlobalPrototypeTemplateView from "./GlobalPrototypeTemplateView.vue";

const templateId = "01234567-89ab-4cde-8123-456789abcdef";
const templateVersion = "11234567-89ab-4cde-8123-456789abcdef";
const documentId = "21234567-89ab-4cde-8123-456789abcdef";
const documentVersion = "31234567-89ab-4cde-8123-456789abcdef";
const actor = "41234567-89ab-4cde-8123-456789abcdef";
const trace = "51234567-89ab-4cde-8123-456789abcdef";
const now = "2026-10-08T12:00:00Z";
const template = { prototype_template_id: templateId, prototype_template_version_id: templateVersion,
  scope: "GLOBAL" as const, project_id: null, name: "全局桌面模板", state: "ACTIVE" as const, version_no: 1,
  version_state: "PUBLISHED" as const, layout_contract: { layout: "SINGLE_COLUMN" },
  component_contract: { components: [{ kind: "FORM" }] }, applicable_terminals: ["DESKTOP"],
  artifact_refs: [{ artifact_kind: "DOCUMENT_VERSION" as const, target_id: documentVersion, document_id: documentId }],
  content_fingerprint: "a".repeat(64), etag: '"v0"', supersedes_version_id: null, is_current: true,
  updated_at: now, created_at: now };
const document = { document_id: documentId, scope: "GLOBAL" as const, category: "TEMPLATE" as const, subtype: null,
  title: "企业原型规范", display_name: "企业原型规范.docx", state: "ACTIVE" as const,
  latest_version_ref: documentVersion, effective_version_ref: documentVersion, created_at: now, etag: '"v0"' };
function json(data: unknown) { return new Response(JSON.stringify({ data, trace_id: trace }),
  { status: 200, headers: { "Content-Type": "application/json" } }); }
async function session(admin = true) { const fetcher = vi.fn().mockResolvedValueOnce(json({
  user: { user_id: actor, username_display: admin ? "部署管理员" : "普通用户" },
  deployment_role: admin ? "DEPLOYMENT_ADMIN" : "NONE", password_change_required: false, authorized_projects: [],
  absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "a".repeat(64) }));
  const value = new SessionClient(fetcher as typeof fetch); await value.login("admin", "synthetic"); return value; }
async function router() { const Dummy = defineComponent({ template: "<div />" }); const value = createRouter({
  history: createMemoryHistory(), routes: [
    { path: "/admin/users", name: "admin-users", component: Dummy },
    { path: "/admin/prototype-templates", name: "global-prototype-templates", component: Dummy },
  ] }); await value.push("/admin/prototype-templates"); await value.isReady(); return value; }
function clients() { return {
  templates: { listGlobal: vi.fn().mockResolvedValue({ items: [template], next_cursor: null, has_more: false }) },
  documents: { list: vi.fn().mockResolvedValue({ items: [document], next_cursor: null, has_more: false }),
    contentUrl: vi.fn().mockReturnValue(`/api/v1/global/documents/${documentId}/versions/${documentVersion}/content`) },
}; }

describe("GLOBAL Prototype Template administrator page", () => {
  it("uses GLOBAL metadata, structured fields and the original operation to recover create", async () => {
    const auth = await session(), appRouter = await router(), api = clients();
    const writer = { createGlobalTemplate: vi.fn().mockRejectedValueOnce(new PrototypeWriteError("PROTOTYPE_WRITE_UNAVAILABLE"))
      .mockResolvedValueOnce(template), reviseGlobalTemplate: vi.fn() };
    const wrapper = mount(GlobalPrototypeTemplateView, { props: { session: auth, templates: api.templates as never,
      documents: api.documents as never, writer: writer as never }, global: { plugins: [appRouter] } });
    await flushPromises(); expect(api.documents.list).toHaveBeenCalledWith({ kind: "GLOBAL" });
    expect(wrapper.get(`a[href="/api/v1/global/documents/${documentId}/versions/${documentVersion}/content"]`).attributes("rel")).toBe("noopener");
    expect(wrapper.find("textarea").exists()).toBe(false); const form = wrapper.find("form");
    await form.get('input:not([type])').setValue("企业业务原型");
    await form.get(`input[value="${documentVersion}"]`).setValue(true);
    await form.findAll('input[type="checkbox"]').at(-1)!.setValue(true); await form.trigger("submit"); await flushPromises();
    expect(wrapper.text()).toContain("结果未知"); const first = writer.createGlobalTemplate.mock.calls[0]!;
    expect(first[1]).toEqual(expect.objectContaining({ layout_contract: { layout: "SINGLE_COLUMN" },
      component_contract: { components: [{ kind: "FORM" }] }, applicable_terminals: ["DESKTOP"],
      artifact_refs: [{ artifact_kind: "DOCUMENT_VERSION", target_id: documentVersion }] }));
    await wrapper.find("aside button").trigger("click"); await flushPromises(); const second = writer.createGlobalTemplate.mock.calls[1]!;
    expect(second[1]).toEqual(first[1]); expect(second[2]).toBe(first[2]);
    expect(wrapper.text()).toContain("项目仍须固定具体版本");
  });

  it("revises a GLOBAL template with its current ETag and preserves the old-version warning", async () => {
    const auth = await session(), appRouter = await router(), api = clients();
    const writer = { createGlobalTemplate: vi.fn(), reviseGlobalTemplate: vi.fn().mockResolvedValue({ ...template,
      prototype_template_version_id: actor, version_no: 2, etag: '"v1"', supersedes_version_id: templateVersion }) };
    const wrapper = mount(GlobalPrototypeTemplateView, { props: { session: auth, templates: api.templates as never,
      documents: api.documents as never, writer: writer as never }, global: { plugins: [appRouter] } });
    await flushPromises(); await wrapper.findAll("button").find(button => button.text().includes("当前固定版本修订"))!.trigger("click");
    await flushPromises(); const form = wrapper.find("form"); expect(form.text()).toContain("修订全局模板");
    await form.findAll('input[type="checkbox"]').at(-1)!.setValue(true); await form.trigger("submit"); await flushPromises();
    expect(writer.reviseGlobalTemplate).toHaveBeenCalledWith(templateId, '"v0"', expect.any(Object), expect.any(String));
    expect(wrapper.text()).toContain("旧版本及使用它的项目事实保持不变");
  });

  it("does not read or render management forms for a non-administrator", async () => {
    const auth = await session(false), appRouter = await router(), api = clients();
    const wrapper = mount(GlobalPrototypeTemplateView, { props: { session: auth, templates: api.templates as never,
      documents: api.documents as never, writer: {} as never }, global: { plugins: [appRouter] } });
    await flushPromises(); expect(wrapper.text()).toContain("仅部署管理员"); expect(wrapper.find("form").exists()).toBe(false);
    expect(api.templates.listGlobal).not.toHaveBeenCalled(); expect(api.documents.list).not.toHaveBeenCalled();
  });
});
