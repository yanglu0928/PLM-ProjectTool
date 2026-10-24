import { defineComponent } from "vue";
import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory, createRouter } from "vue-router";
import { describe, expect, it, vi } from "vitest";

import { SessionClient } from "@/modules/auth/api/sessionClient";
import { PrototypeWriteError } from "@/modules/prototype/api/prototypeWriteClient";
import ProjectPrototypeVersionView from "./ProjectPrototypeVersionView.vue";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const prototype = "11234567-89ab-4cde-8123-456789abcdef";
const version = "21234567-89ab-4cde-8123-456789abcdef";
const template = "31234567-89ab-4cde-8123-456789abcdef";
const templateVersion = "41234567-89ab-4cde-8123-456789abcdef";
const document = "51234567-89ab-4cde-8123-456789abcdef";
const documentVersion = "61234567-89ab-4cde-8123-456789abcdef";
const requirement = "71234567-89ab-4cde-8123-456789abcdef";
const requirementVersion = "81234567-89ab-4cde-8123-456789abcdef";
const actor = "91234567-89ab-4cde-8123-456789abcdef";
const reviewer = "a1234567-89ab-4cde-8123-456789abcdef";
const member = "b1234567-89ab-4cde-8123-456789abcdef";
const department = "c1234567-89ab-4cde-8123-456789abcdef";
const audit = "d1234567-89ab-4cde-8123-456789abcdef";
const review = "e1234567-89ab-4cde-8123-456789abcdef";
const round = "f1234567-89ab-4cde-8123-456789abcdef";
const trace = "02234567-89ab-4cde-8123-456789abcdef";
const now = "2026-10-08T12:00:00Z";
const root = { prototype_id: prototype, project_id: project, name: "桌面交互原型", state: "ACTIVE" as const,
  current_approved_version_ref: null, created_by: actor, created_at: now, updated_by: null, updated_at: now, etag: '"v0"' };
const templateItem = { prototype_template_id: template, prototype_template_version_id: templateVersion,
  scope: "PROJECT" as const, project_id: project, name: "桌面表单模板", state: "ACTIVE" as const, version_no: 1,
  version_state: "PUBLISHED" as const, layout_contract: { layout: "SINGLE_COLUMN" },
  component_contract: { components: [{ kind: "FORM" }] }, applicable_terminals: ["DESKTOP"], artifact_refs: [],
  content_fingerprint: "a".repeat(64), etag: '"v0"', supersedes_version_id: null, is_current: true,
  updated_at: now, created_at: now };
const documentItem = { document_id: document, scope: "PROJECT" as const, category: "GENERATED_ARTIFACT" as const,
  subtype: null, title: "原型页面包", display_name: "prototype.pdf", state: "ACTIVE" as const,
  latest_version_ref: documentVersion, effective_version_ref: documentVersion, created_at: now, etag: '"v0"' };
const requirementItem = { requirement_id: requirement, project_id: project, requirement_code: "REQ-001", state: "ACTIVE" as const,
  current_approved_version_ref: requirementVersion, created_by: actor, created_at: now, updated_by: null, updated_at: now, etag: '"v0"' };
const versionItem = { prototype_version_id: version, prototype_id: prototype, project_id: project, version_no: 1,
  state: "DRAFT" as const, supersedes_version_id: null, template_id: template, template_version_id: templateVersion,
  artifact_refs: [{ artifact_kind: "DOCUMENT_VERSION" as const, target_id: documentVersion, document_id: document }],
  requirement_refs: [{ requirement_id: requirement, requirement_version_id: requirementVersion }],
  interaction_spec: { mode: "CLICK_THROUGH", navigation: "LINEAR", description: "按业务顺序演示" },
  coverage_summary: { basis: "APPROVED_REQUIREMENTS", requirement_count: 1, artifact_count: 1, maintained_by: "HUMAN" },
  content_fingerprint: "b".repeat(64), created_at: now };
const reviewerItem = { member_id: member, user: { user_id: reviewer, display_name: "客户经理" }, role: "CUSTOMER_MANAGER" as const,
  department: { department_id: department, name: "业务部" }, state: "ACTIVE" as const, effective_at: now, ended_at: null, etag: '"v0"' };
const report = { audit_event_id: audit, prototype_version_id: version, state: "DRAFT" as const, valid: true,
  blocking_issues: [], warnings: [], coverage_summary: { template_available: true, requirements_available: true,
    artifacts_available: true }, checked_at: now };
const submission = { review_id: review, review_round_id: round, subject_type: "PRT-03" as const, project_id: project,
  prototype_id: prototype, prototype_version_id: version, policy_ref: "PROTOTYPE_ALL_V1" as const, reviewer_ids: [reviewer],
  state: "IN_REVIEW" as const, round_no: 1, review_etag: '"v1"', submitted_by: actor, submitted_at: now };
function json(data: unknown) { return new Response(JSON.stringify({ data, trace_id: trace }),
  { status: 200, headers: { "Content-Type": "application/json" } }); }
async function session(role: "PROJECT_MANAGER" | "IMPLEMENTATION_MEMBER" = "PROJECT_MANAGER") {
  const fetcher = vi.fn().mockResolvedValueOnce(json({ user: { user_id: actor, username_display: "实施人员" },
    deployment_role: "NONE", password_change_required: false, authorized_projects: [{ project_id: project, name: "PLM项目", role }],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "a".repeat(64) }));
  const value = new SessionClient(fetcher as typeof fetch); await value.login("member", "synthetic"); return value;
}
async function router(direct = false) { const Dummy = defineComponent({ template: "<div />" }); const value = createRouter({
  history: createMemoryHistory(), routes: [
    { path: "/projects/:projectId/prototypes/:prototypeId", name: "project-prototype-detail", component: Dummy },
    { path: "/projects/:projectId/prototypes/:prototypeId/versions", name: "project-prototype-versions", component: Dummy },
    { path: "/projects/:projectId/prototypes/:prototypeId/versions/:versionId", name: "project-prototype-version-detail", component: Dummy },
    { path: "/projects/:projectId/documents/:documentId", name: "project-document-detail", component: Dummy },
  ] }); await value.push(`/projects/${project}/prototypes/${prototype}/versions${direct ? `/${version}` : ""}`);
  await value.isReady(); return value; }
function readers(withVersion = false) { return {
  identities: { get: vi.fn().mockResolvedValue(root) },
  versions: { list: vi.fn().mockResolvedValue({ items: withVersion ? [versionItem] : [], next_cursor: null, has_more: false }),
    get: vi.fn().mockResolvedValue(versionItem) },
  templates: { listProject: vi.fn().mockResolvedValue({ items: [templateItem], next_cursor: null, has_more: false }) },
  documents: { list: vi.fn().mockResolvedValue({ items: [documentItem], next_cursor: null, has_more: false }) },
  requirements: { listRequirements: vi.fn().mockResolvedValue({ items: [requirementItem], next_cursor: null, has_more: false }) },
  members: { list: vi.fn().mockResolvedValue({ items: [reviewerItem], next_cursor: null, has_more: false }) },
}; }

describe("Prototype Version structured page", () => {
  it("creates, validates and submits only fixed business choices while recovering original idempotent operations", async () => {
    const auth = await session(), appRouter = await router(), api = readers();
    const created = { ...versionItem, prototype_etag: '"v1"' };
    const writer = { createVersion: vi.fn().mockRejectedValueOnce(new PrototypeWriteError("PROTOTYPE_WRITE_UNAVAILABLE"))
      .mockResolvedValueOnce(created), validateVersion: vi.fn().mockRejectedValueOnce(new PrototypeWriteError("PROTOTYPE_WRITE_UNAVAILABLE"))
      .mockResolvedValueOnce(report), submitVersionReview: vi.fn().mockRejectedValueOnce(new PrototypeWriteError("PROTOTYPE_WRITE_UNAVAILABLE"))
      .mockResolvedValueOnce(submission) };
    const wrapper = mount(ProjectPrototypeVersionView, { props: { session: auth, identities: api.identities as never,
      versions: api.versions as never, templates: api.templates as never, documents: api.documents as never,
      requirements: api.requirements as never, members: api.members as never, writer: writer as never },
      global: { plugins: [appRouter] } }); await flushPromises();
    expect(wrapper.text()).toContain("版本创建和服务端校验都不是批准"); const form = wrapper.find("form");
    await form.get(`input[value="${documentVersion}"]`).setValue(true);
    await form.get(`input[value="${requirementVersion}"]`).setValue(true);
    await form.get("textarea").setValue("按业务顺序演示关键页面");
    await form.findAll('input[type="checkbox"]').at(-1)!.setValue(true); await form.trigger("submit"); await flushPromises();
    expect(wrapper.text()).toContain("版本创建结果未知"); const firstCreate = writer.createVersion.mock.calls[0]!;
    expect(firstCreate[3]).toEqual(expect.objectContaining({ template_id: template, template_version_id: templateVersion,
      artifact_refs: [{ artifact_kind: "DOCUMENT_VERSION", target_id: documentVersion }],
      requirement_refs: [{ requirement_id: requirement, requirement_version_id: requirementVersion }],
      interaction_spec: { mode: "CLICK_THROUGH", navigation: "LINEAR", description: "按业务顺序演示关键页面" },
      coverage_summary: { basis: "APPROVED_REQUIREMENTS", requirement_count: 1, artifact_count: 1, maintained_by: "HUMAN" } }));
    await wrapper.find("aside button").trigger("click"); await flushPromises(); const secondCreate = writer.createVersion.mock.calls[1]!;
    expect(secondCreate.slice(2)).toEqual(firstCreate.slice(2)); expect(wrapper.text()).toContain("创建和后续校验都不代表批准");
    await wrapper.findAll("button").find(button => button.text().includes("当前事实校验"))!.trigger("click"); await flushPromises();
    const firstValidate = writer.validateVersion.mock.calls[0]!; expect(wrapper.text()).toContain("校验结果未知");
    await wrapper.find("aside button").trigger("click"); await flushPromises(); const secondValidate = writer.validateVersion.mock.calls[1]!;
    expect(secondValidate).toEqual(firstValidate); expect(wrapper.text()).toContain("这不是批准结论");
    const reviewField = wrapper.findAll("fieldset").find(item => item.text().includes("正式送审"))!;
    await reviewField.get(`input[value="${reviewer}"]`).setValue(true);
    await reviewField.find("button").trigger("click"); await flushPromises();
    expect(wrapper.text()).toContain("送审结果未知"); const firstReview = writer.submitVersionReview.mock.calls[0]!;
    await wrapper.find("aside button").trigger("click"); await flushPromises(); const secondReview = writer.submitVersionReview.mock.calls[1]!;
    expect(secondReview).toEqual(firstReview);
    expect(writer.submitVersionReview).toHaveBeenCalledWith(project, prototype, version, [reviewer], expect.any(String));
    expect(wrapper.text()).toContain("评审回执不是批准结论");
  });

  it("loads an exact fixed version and prevents an implementation member from submitting review", async () => {
    const auth = await session("IMPLEMENTATION_MEMBER"), appRouter = await router(true), api = readers(true);
    const writer = { createVersion: vi.fn(), validateVersion: vi.fn().mockResolvedValue(report), submitVersionReview: vi.fn() };
    const wrapper = mount(ProjectPrototypeVersionView, { props: { session: auth, identities: api.identities as never,
      versions: api.versions as never, templates: api.templates as never, documents: api.documents as never,
      requirements: api.requirements as never, members: api.members as never, writer: writer as never },
      global: { plugins: [appRouter] } }); await flushPromises();
    expect(api.versions.get).toHaveBeenCalledWith(project, prototype, version);
    expect(wrapper.get(`a[href="/projects/${project}/documents/${document}?version=${documentVersion}"]`).text()).toContain("原型页面包");
    await wrapper.findAll("button").find(button => button.text().includes("当前事实校验"))!.trigger("click"); await flushPromises();
    expect(wrapper.text()).toContain("只有项目负责人可以提交正式评审");
    expect(wrapper.findAll("button").some(button => button.text() === "提交正式评审")).toBe(false);
    expect(writer.submitVersionReview).not.toHaveBeenCalled();
  });
});
