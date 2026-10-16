import { defineComponent } from "vue";
import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory, createRouter } from "vue-router";
import { describe, expect, it, vi } from "vitest";

import { SessionClient } from "@/modules/auth/api/sessionClient";
import { PrototypeWriteError } from "@/modules/prototype/api/prototypeWriteClient";
import type { RequirementVersionView } from "@/modules/requirement/api/requirementReadClient";
import ProjectPrototypeLinkView from "./ProjectPrototypeLinkView.vue";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const prototype = "11234567-89ab-4cde-8123-456789abcdef";
const prototypeVersion = "21234567-89ab-4cde-8123-456789abcdef";
const requirement = "31234567-89ab-4cde-8123-456789abcdef";
const requirementVersion = "41234567-89ab-4cde-8123-456789abcdef";
const acceptanceA = "51234567-89ab-4cde-8123-456789abcdef";
const acceptanceB = "61234567-89ab-4cde-8123-456789abcdef";
const actor = "71234567-89ab-4cde-8123-456789abcdef";
const linkId = "81234567-89ab-4cde-8123-456789abcdef";
const replacementId = "91234567-89ab-4cde-8123-456789abcdef";
const trace = "a1234567-89ab-4cde-8123-456789abcdef";
const now = "2026-10-08T12:00:00Z";
const requirementRoot = { requirement_id: requirement, project_id: project, requirement_code: "REQ-001", state: "ACTIVE" as const,
  current_approved_version_ref: requirementVersion, created_by: actor, created_at: now, updated_by: null, updated_at: now, etag: '"v1"' };
const prototypeRoot = { prototype_id: prototype, project_id: project, name: "审批交互原型", state: "ACTIVE" as const,
  current_approved_version_ref: prototypeVersion, created_by: actor, created_at: now, updated_by: actor, updated_at: now, etag: '"v1"' };
const requirementDetail = { requirement_version_id: requirementVersion, requirement_id: requirement, project_id: project,
  version_no: 2, state: "APPROVED" as const, title: "审批需求", domain_name: "审批", priority: "HIGH" as const,
  risk: "MEDIUM" as const, classification: "STANDARD_FUNCTION" as const, content_fingerprint: "a".repeat(64),
  declared_counts: { sources: 0, acceptance_criteria: 2, capability_assessments: 0, assumptions: 0,
    exclusions: 0, dependencies: 0, ai_tasks: 0 }, supersedes_version_ref: null, review_ref: null,
  review_round_ref: null, created_by: actor, created_at: now, statement: "审批可追踪", rationale: "客户确认",
  sources: [], acceptance_criteria: [
    { ordinal: 0, acceptance_criterion_ref: acceptanceA, observable_result: "提交后形成审批记录", verification_method: "查看记录",
      required_data: "审批数据", required_environment: "Windows 11", evidence_requirement: "审计记录" },
    { ordinal: 1, acceptance_criterion_ref: acceptanceB, observable_result: "驳回后返回申请人", verification_method: "状态核对",
      required_data: "驳回意见", required_environment: "Windows 11", evidence_requirement: "状态截图" },
  ], capability_assessments: [], assumptions: [], exclusions: [], dependencies: [], ai_tasks: [] };
const prototypeDetail = { prototype_version_id: prototypeVersion, prototype_id: prototype, project_id: project, version_no: 3,
  state: "APPROVED" as const, supersedes_version_id: null, template_id: "b1234567-89ab-4cde-8123-456789abcdef",
  template_version_id: "c1234567-89ab-4cde-8123-456789abcdef", artifact_refs: [],
  requirement_refs: [{ requirement_id: requirement, requirement_version_id: requirementVersion }],
  interaction_spec: { mode: "CLICK_THROUGH" }, coverage_summary: { maintained_by: "HUMAN" },
  content_fingerprint: "b".repeat(64), created_at: now };
const activeLink = { requirement_prototype_link_id: linkId, project_id: project, requirement_id: requirement,
  requirement_version_id: requirementVersion, prototype_id: prototype, prototype_version_id: prototypeVersion,
  purpose: "VALIDATES" as const, coverage: { covered_acceptance_criterion_refs: [acceptanceA],
    uncovered_acceptance_criteria: [{ acceptance_criterion_ref: acceptanceB, reason: "待补充驳回页面" }] },
  state: "ACTIVE" as const, created_by: actor, created_at: now, superseded_by_ref: null, etag: '"v0"' };

function json(data: unknown) { return new Response(JSON.stringify({ data, trace_id: trace }),
  { status: 200, headers: { "Content-Type": "application/json" } }); }
async function session() {
  const fetcher = vi.fn().mockResolvedValueOnce(json({ user: { user_id: actor, username_display: "实施人员" },
    deployment_role: "NONE", password_change_required: false,
    authorized_projects: [{ project_id: project, name: "PLM项目", role: "PROJECT_MANAGER" }],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "a".repeat(64) }));
  const value = new SessionClient(fetcher as typeof fetch); await value.login("member", "synthetic"); return value;
}
async function router() { const Dummy = defineComponent({ template: "<div />" }); const value = createRouter({
  history: createMemoryHistory(), routes: [
    { path: "/projects/:projectId/prototypes", name: "project-prototypes", component: Dummy },
    { path: "/projects/:projectId/prototype-links", name: "project-prototype-links", component: Dummy },
  ] }); await value.push(`/projects/${project}/prototype-links`); await value.isReady(); return value; }
function readers(items: readonly typeof activeLink[] = [], requirementValue: RequirementVersionView = requirementDetail) { return {
  identities: { list: vi.fn().mockResolvedValue({ items: [prototypeRoot], next_cursor: null, has_more: false }) },
  versions: { get: vi.fn().mockResolvedValue(prototypeDetail) },
  links: { list: vi.fn().mockResolvedValue({ items, next_cursor: null, has_more: false }) },
  requirements: { listRequirements: vi.fn().mockResolvedValue({ items: [requirementRoot], next_cursor: null, has_more: false }),
    getVersion: vi.fn().mockResolvedValue(requirementValue) },
}; }

describe("RequirementPrototypeLink structured page", () => {
  it("builds a complete stable-ref partition and retries an uncertain create with the exact input and key", async () => {
    const auth = await session(), appRouter = await router(), api = readers();
    const writer = { createLink: vi.fn().mockRejectedValueOnce(new PrototypeWriteError("PROTOTYPE_WRITE_UNAVAILABLE"))
      .mockResolvedValueOnce(activeLink), revokeLink: vi.fn(), supersedeLink: vi.fn() };
    const wrapper = mount(ProjectPrototypeLinkView, { props: { session: auth, identities: api.identities as never,
      versions: api.versions as never, links: api.links as never, requirements: api.requirements as never,
      writer: writer as never }, global: { plugins: [appRouter] } }); await flushPromises();
    expect(wrapper.text()).toContain("缺少关联、空白或部分映射均不能推断为完整覆盖");
    await wrapper.findAll("button").find(item => item.text().includes("加载验收标准"))!.trigger("click"); await flushPromises();
    expect(api.requirements.getVersion).toHaveBeenCalledWith(project, requirement, requirementVersion);
    expect(api.versions.get).toHaveBeenCalledWith(project, prototype, prototypeVersion);
    const articles = wrapper.findAll("article");
    await articles[0]!.get('input[value="COVERED"]').setValue(true);
    await articles[1]!.get('input[value="UNCOVERED"]').setValue(true);
    await articles[1]!.get("textarea").setValue("本轮不包含异常驳回页面");
    await wrapper.get('form input[type="checkbox"]').setValue(true); await wrapper.get("form").trigger("submit"); await flushPromises();
    expect(wrapper.text()).toContain("上次创建结果未知"); const first = writer.createLink.mock.calls[0]!;
    expect(first[1]).toEqual({ requirement_id: requirement, requirement_version_id: requirementVersion,
      prototype_id: prototype, prototype_version_id: prototypeVersion, purpose: "VALIDATES",
      coverage: { covered_acceptance_criterion_refs: [acceptanceA], uncovered_acceptance_criteria: [
        { acceptance_criterion_ref: acceptanceB, reason: "本轮不包含异常驳回页面" }] } });
    await wrapper.find("aside button").trigger("click"); await flushPromises();
    expect(writer.createLink.mock.calls[1]).toEqual(first);
    expect(wrapper.text()).toContain("覆盖分区是人工声明，不等于评审批准");
  });

  it("fails closed when the approved requirement projection lacks stable criterion references", async () => {
    const auth = await session(), appRouter = await router();
    const api = readers([], { ...requirementDetail, acceptance_criteria: [
      { ...requirementDetail.acceptance_criteria[0]!, acceptance_criterion_ref: null },
      requirementDetail.acceptance_criteria[1]!,
    ] });
    const writer = { createLink: vi.fn(), revokeLink: vi.fn(), supersedeLink: vi.fn() };
    const wrapper = mount(ProjectPrototypeLinkView, { props: { session: auth, identities: api.identities as never,
      versions: api.versions as never, links: api.links as never, requirements: api.requirements as never,
      writer: writer as never }, global: { plugins: [appRouter] } }); await flushPromises();
    await wrapper.findAll("button").find(item => item.text().includes("加载验收标准"))!.trigger("click"); await flushPromises();
    expect(wrapper.text()).toContain("不能手工填写UUID代替");
    expect(wrapper.findAll("article")).toHaveLength(0); expect(wrapper.findAll("form button").at(-1)!.attributes("disabled")).toBeDefined();
    expect(writer.createLink).not.toHaveBeenCalled();
  });

  it("locks logical identity during supersede and retries the exact replacement operation", async () => {
    const auth = await session(), appRouter = await router(), api = readers([activeLink]);
    const replacement = { ...activeLink, requirement_prototype_link_id: replacementId, created_at: "2026-10-08T12:01:00Z" };
    const writer = { createLink: vi.fn(), revokeLink: vi.fn(),
      supersedeLink: vi.fn().mockRejectedValueOnce(new PrototypeWriteError("PROTOTYPE_WRITE_UNAVAILABLE"))
        .mockResolvedValueOnce(replacement) };
    const wrapper = mount(ProjectPrototypeLinkView, { props: { session: auth, identities: api.identities as never,
      versions: api.versions as never, links: api.links as never, requirements: api.requirements as never,
      writer: writer as never }, global: { plugins: [appRouter] } }); await flushPromises();
    await wrapper.findAll("button").find(item => item.text() === "替换关联")!.trigger("click");
    expect(wrapper.findAll("form select").every(item => item.attributes("disabled") !== undefined)).toBe(true);
    await wrapper.findAll("button").find(item => item.text().includes("加载验收标准"))!.trigger("click"); await flushPromises();
    expect(wrapper.findAll("article")[0]!.get('input[value="COVERED"]').element).toMatchObject({ checked: true });
    expect(wrapper.findAll("article")[1]!.get("textarea").element).toMatchObject({ value: "待补充驳回页面" });
    await wrapper.get('form input[type="checkbox"]').setValue(true); await wrapper.get("form").trigger("submit"); await flushPromises();
    expect(wrapper.text()).toContain("上次替换结果未知"); const first = writer.supersedeLink.mock.calls[0]!;
    expect(first.slice(0, 3)).toEqual([project, linkId, expect.objectContaining({ requirement_id: requirement,
      prototype_id: prototype, purpose: "VALIDATES" })]);
    await wrapper.find("aside button").trigger("click"); await flushPromises();
    expect(writer.supersedeLink.mock.calls[1]).toEqual(first);
    expect(wrapper.text()).toContain("原关联已被新关联替换");
  });
});
