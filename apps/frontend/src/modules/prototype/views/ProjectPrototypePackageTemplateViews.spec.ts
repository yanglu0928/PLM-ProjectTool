import { defineComponent } from "vue";
import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory, createRouter } from "vue-router";
import { describe, expect, it, vi } from "vitest";

import { SessionClient } from "@/modules/auth/api/sessionClient";
import { PrototypeWriteError } from "@/modules/prototype/api/prototypeWriteClient";
import ProjectPrototypePackageView from "./ProjectPrototypePackageView.vue";
import ProjectPrototypeTemplateView from "./ProjectPrototypeTemplateView.vue";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const packageId = "11234567-89ab-4cde-8123-456789abcdef";
const prototypeA = "21234567-89ab-4cde-8123-456789abcdef";
const prototypeB = "31234567-89ab-4cde-8123-456789abcdef";
const templateId = "41234567-89ab-4cde-8123-456789abcdef";
const templateVersion = "51234567-89ab-4cde-8123-456789abcdef";
const globalTemplate = "61234567-89ab-4cde-8123-456789abcdef";
const documentId = "71234567-89ab-4cde-8123-456789abcdef";
const documentVersion = "81234567-89ab-4cde-8123-456789abcdef";
const actor = "91234567-89ab-4cde-8123-456789abcdef";
const trace = "a1234567-89ab-4cde-8123-456789abcdef";
const now = "2026-10-08T12:00:00Z";
const packageSummary = { prototype_package_id: packageId, project_id: project, name: "验收原型包", state: "ACTIVE" as const,
  created_by: actor, created_at: now, updated_by: null, updated_at: now, etag: '"v0"' };
const prototypes = [{ prototype_id: prototypeA, project_id: project, name: "桌面端", state: "ACTIVE" as const,
  current_approved_version_ref: null, created_by: actor, created_at: now, updated_by: null, updated_at: now, etag: '"v0"' },
{ prototype_id: prototypeB, project_id: project, name: "管理端", state: "ACTIVE" as const,
  current_approved_version_ref: null, created_by: actor, created_at: now, updated_by: null, updated_at: now, etag: '"v0"' }];
const template = { prototype_template_id: templateId, prototype_template_version_id: templateVersion,
  scope: "PROJECT" as const, project_id: project, name: "项目表单", state: "ACTIVE" as const, version_no: 1,
  version_state: "PUBLISHED" as const, layout_contract: { layout: "SINGLE_COLUMN" },
  component_contract: { components: [{ kind: "FORM" }] }, applicable_terminals: ["DESKTOP"], artifact_refs: [],
  content_fingerprint: "b".repeat(64), etag: '"v0"', supersedes_version_id: null, is_current: true, updated_at: now, created_at: now };
const global = { ...template, prototype_template_id: globalTemplate, scope: "GLOBAL" as const, project_id: null,
  name: "全局参考", updated_at: "2026-10-08T11:00:00Z" };
const document = { document_id: documentId, scope: "PROJECT" as const, category: "TEMPLATE" as const, subtype: null,
  title: "原型设计规范", display_name: "原型设计规范.docx", state: "ACTIVE" as const,
  latest_version_ref: documentVersion, effective_version_ref: documentVersion, created_at: now, etag: '"v0"' };
function json(data: unknown) { return new Response(JSON.stringify({ data, trace_id: trace }),
  { status: 200, headers: { "Content-Type": "application/json" } }); }
async function session() { const fetcher = vi.fn().mockResolvedValueOnce(json({ user: { user_id: actor, username_display: "项目经理" },
  deployment_role: "NONE", password_change_required: false,
  authorized_projects: [{ project_id: project, name: "PLM项目", role: "PROJECT_MANAGER" }],
  absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "a".repeat(64) }));
  const value = new SessionClient(fetcher as typeof fetch); await value.login("manager", "synthetic"); return value; }
const Dummy = defineComponent({ template: "<div />" });
async function router(path: string) { const value = createRouter({ history: createMemoryHistory(), routes: [
  { path: "/projects/:projectId/prototypes", name: "project-prototypes", component: Dummy },
  { path: "/projects/:projectId/prototype-packages", name: "project-prototype-packages", component: Dummy },
  { path: "/projects/:projectId/prototype-templates", name: "project-prototype-templates", component: Dummy },
  { path: "/projects/:projectId/documents/:documentId", name: "project-document-detail", component: Dummy },
] }); await value.push(path); await value.isReady(); return value; }

describe("Prototype Package and Template structured pages", () => {
  it("replaces the complete Package member set and recovers with the original operation", async () => {
    const auth = await session(), appRouter = await router(`/projects/${project}/prototype-packages`);
    const packages = { list: vi.fn().mockResolvedValue({ items: [packageSummary], next_cursor: null, has_more: false }),
      get: vi.fn().mockResolvedValue({ ...packageSummary, prototype_ids: [prototypeA] }) };
    const identities = { list: vi.fn().mockResolvedValue({ items: prototypes, next_cursor: null, has_more: false }) };
    const writer = { setPackageMembers: vi.fn().mockRejectedValueOnce(new PrototypeWriteError("PROTOTYPE_WRITE_UNAVAILABLE"))
      .mockResolvedValueOnce({ ...packageSummary, prototype_ids: [prototypeA, prototypeB], etag: '"v1"' }),
      createPackage: vi.fn(), patchPackage: vi.fn() };
    const wrapper = mount(ProjectPrototypePackageView, { props: { session: auth, packages: packages as never,
      prototypes: identities as never, writer: writer as never }, global: { plugins: [appRouter] } });
    await flushPromises(); await wrapper.findAll("button").find(button => button.text().includes("查看并维护"))!.trigger("click");
    await flushPromises(); expect(wrapper.text()).toContain("完整替换当前集合");
    const form = wrapper.findAll("form").find(item => item.text().includes("完整成员集合"))!;
    const memberInputs = form.findAll('input[type="checkbox"][value]'); await memberInputs[1]!.setValue(true);
    await form.findAll('input[type="checkbox"]').at(-1)!.setValue(true); await form.trigger("submit"); await flushPromises();
    expect(wrapper.text()).toContain("结果未知"); const first = writer.setPackageMembers.mock.calls[0]!;
    await wrapper.find("aside button").trigger("click"); await flushPromises(); const second = writer.setPackageMembers.mock.calls[1]!;
    expect(second.slice(1)).toEqual(first.slice(1)); expect(second[2]).toBe('"v0"');
    expect(wrapper.text()).toContain("完整替换"); expect(wrapper.text()).toContain("历史未删除");
  });

  it("shows GLOBAL templates read-only and creates a structured PROJECT template from fixed document choices", async () => {
    const auth = await session(), appRouter = await router(`/projects/${project}/prototype-templates`);
    const templatePage = { items: [template, global], next_cursor: null, has_more: false };
    const templates = { listProject: vi.fn().mockResolvedValue(templatePage) };
    const documents = { list: vi.fn().mockResolvedValue({ items: [document], next_cursor: null, has_more: false }) };
    const writer = { createProjectTemplate: vi.fn().mockRejectedValueOnce(new PrototypeWriteError("PROTOTYPE_WRITE_UNAVAILABLE"))
      .mockResolvedValueOnce(template), reviseProjectTemplate: vi.fn() };
    const wrapper = mount(ProjectPrototypeTemplateView, { props: { session: auth, templates: templates as never,
      documents: documents as never, writer: writer as never }, global: { plugins: [appRouter] } });
    await flushPromises(); expect(wrapper.text()).toContain("获准的全局模板（只读）"); expect(wrapper.text()).toContain("全局参考");
    expect(wrapper.find("textarea").exists()).toBe(false); const form = wrapper.find("form");
    await form.get('input:not([type])').setValue("桌面业务模板");
    await form.get(`input[value="${documentVersion}"]`).setValue(true);
    await form.findAll('input[type="checkbox"]').at(-1)!.setValue(true); await form.trigger("submit"); await flushPromises();
    expect(wrapper.text()).toContain("结果未知"); const first = writer.createProjectTemplate.mock.calls[0]!;
    expect(first[2]).toEqual(expect.objectContaining({ layout_contract: { layout: "SINGLE_COLUMN" },
      component_contract: { components: [{ kind: "FORM" }] }, applicable_terminals: ["DESKTOP"],
      artifact_refs: [{ artifact_kind: "DOCUMENT_VERSION", target_id: documentVersion }] }));
    await wrapper.find("aside button").trigger("click"); await flushPromises(); const second = writer.createProjectTemplate.mock.calls[1]!;
    expect(second[2]).toEqual(first[2]); expect(second[3]).toBe(first[3]); expect(wrapper.text()).toContain("不是客户确认事实");
  });
});
