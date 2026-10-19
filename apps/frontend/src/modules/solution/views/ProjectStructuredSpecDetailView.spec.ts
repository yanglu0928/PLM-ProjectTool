import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { StructuredSpecReadClient } from "@/modules/solution/api/structuredSpecReadClient";
import { StructuredSpecValidateClient } from "@/modules/solution/api/structuredSpecValidateClient";
import ProjectStructuredSpecDetailView from "./ProjectStructuredSpecDetailView.vue";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const other = "02234567-89ab-4cde-8123-456789abcdef";
const spec = "11234567-89ab-4cde-8123-456789abcdef";
const requirement = "21234567-89ab-4cde-8123-456789abcdef";
const section = "31234567-89ab-4cde-8123-456789abcdef";
const detail = {
  structured_solution_spec_id: spec, spec_series_id: spec, project_id: project,
  spec_type: "MIGRATION_SPEC", version_no: 1, version_state: "DRAFT",
  content_fingerprint: "a".repeat(64), payload_fingerprint: "b".repeat(64),
  payload: { assumptions: ["客户尚未确认"], exclusions: [], source_system: "旧 PLM",
    target_system: "新 PLM", scope: "零件", cleansing_rules: ["去重"],
    field_mappings: [{ source: "old_id", target: "part_id" }],
    trial_plan: "先试点", reconciliation_plan: "逐条核对",
    rollback_plan: "恢复快照", acceptance_criteria: "差异清零" },
  requirement_refs: [{ requirement_id: requirement, requirement_version_id: requirement }],
  section_refs: [{ solution_section_id: section, solution_section_version_id: section }],
  evidence_ids: [], artifact_ids: [], declared_requirement_count: 1,
  declared_section_count: 1, declared_evidence_count: 0,
  supersedes_version_ref: null, review_ref: null, review_round_ref: null,
  created_by: project, created_at: "2026-10-16T00:00:00Z",
};
async function session(role = "CUSTOMER_MEMBER") {
  const api = new SessionClient(vi.fn().mockResolvedValue(new Response(JSON.stringify({ data: {
    user: { user_id: project, username_display: "合成用户" }, deployment_role: "NONE",
    password_change_required: false,
    authorized_projects: [{ project_id: project, name: "项目", role }],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64),
  }, trace_id: project }), { status: 200,
    headers: { "Content-Type": "application/json" } })) as typeof fetch);
  await api.login("user", "synthetic-only"); return api;
}

describe("ProjectStructuredSpecDetailView", () => {
  afterEach(() => { vi.restoreAllMocks(); window.sessionStorage.clear(); });
  it("shows readable DRAFT and fixed-source links for a project member", async () => {
    const router = createAppRouter(createMemoryHistory());
    expect(router.resolve(`/projects/${project}/structured-solution-specs/${spec}`).name)
      .toBe("project-structured-spec-detail");
    await router.push(`/projects/${project}/structured-solution-specs/${spec}`);
    await router.isReady();
    const reader = { detail: vi.fn().mockResolvedValue(detail) };
    const wrapper = mount(ProjectStructuredSpecDetailView, { props: {
      session: await session(), reader: reader as unknown as StructuredSpecReadClient },
    global: { plugins: [router] } });
    await flushPromises();
    expect(reader.detail).toHaveBeenCalledWith(project, spec);
    expect(wrapper.text()).toContain("待评审草案");
    expect(wrapper.text()).toContain("零件");
    expect(wrapper.text()).toContain("old_id");
    expect(wrapper.text()).toContain("客户尚未确认");
    expect(wrapper.text()).toContain("不证明需求、章节或证据目前仍合格");
    expect(wrapper.get(`a[href="/projects/${project}/structured-solution-specs"]`).text())
      .toContain("返回专项版本历史");
    expect(wrapper.find(`a[href="/projects/${project}/solution-sections/${section}/versions/${section}"]`).exists()).toBe(true);
    expect(wrapper.find("pre").exists()).toBe(false);
    expect(wrapper.find(`a[href="/projects/${project}/structured-solution-specs/${spec}/revise"]`).exists()).toBe(false);
    wrapper.unmount();
  });

  it("offers revision only to a writer on a state that the server can revise", async () => {
    const router = createAppRouter(createMemoryHistory());
    await router.push(`/projects/${project}/structured-solution-specs/${spec}`); await router.isReady();
    const wrapper = mount(ProjectStructuredSpecDetailView, { props: {
      session: await session("PROJECT_MANAGER"), reader: {
        detail: vi.fn().mockResolvedValue(detail),
      } as unknown as StructuredSpecReadClient }, global: { plugins: [router] } });
    await flushPromises();
    expect(wrapper.get(`a[href="/projects/${project}/structured-solution-specs/${spec}/revise"]`)
      .text()).toContain("创建修订草案");
    wrapper.unmount();
  });

  it("validates as a writer and explains every unavailable fact and type check", async () => {
    const router = createAppRouter(createMemoryHistory());
    await router.push(`/projects/${project}/structured-solution-specs/${spec}`); await router.isReady();
    const validator = { validate: vi.fn().mockResolvedValue({
      audit_event_id: requirement, observation_trace_id: section, project_id: project,
      structured_solution_spec_id: spec, spec_series_id: spec, spec_type: "MIGRATION_SPEC",
      version_no: 1, version_state: "DRAFT", content_fingerprint: "a".repeat(64),
      payload_fingerprint: "b".repeat(64), requirement_count: 1, section_count: 1,
      evidence_count: 0, artifact_count: 0,
      facts: { integrity: "PASS", payload: "PASS", requirements: "PASS", sections: "PASS",
        evidence: "PASS", artifacts: "PASS", trace: "UNAVAILABLE", current_version: "PASS" },
      type_checks: [{ code: "SCOPE_MAPPING", status: "PASS" },
        { code: "TRIAL_PLAN", status: "PASS" },
        { code: "RECONCILIATION_PLAN", status: "PASS" },
        { code: "ROLLBACK_PLAN", status: "PASS" },
        { code: "ACCEPTANCE_CRITERIA", status: "PASS" }],
      valid: true, ready_for_review: false,
      issue_codes: ["TRACE_COVERAGE_UNAVAILABLE"], observed_at: "2026-10-19T00:00:00Z",
    }) };
    const wrapper = mount(ProjectStructuredSpecDetailView, { props: {
      session: await session("IMPLEMENTATION_MEMBER"),
      reader: { detail: vi.fn().mockResolvedValue(detail) } as unknown as StructuredSpecReadClient,
      validator: validator as unknown as StructuredSpecValidateClient,
    }, global: { plugins: [router] } });
    await flushPromises();
    await wrapper.findAll("button").find(button => button.text() === "验证当前事实")!.trigger("click");
    await flushPromises();
    expect(validator.validate).toHaveBeenCalledWith(project, spec, expect.stringMatching(/^structured-spec-validate-/));
    expect(wrapper.text()).toContain("固定内容与主要来源核验通过");
    expect(wrapper.text()).toContain("尚不具备送审条件");
    expect(wrapper.text()).toContain("当前缺少专项到需求/章节的可信追溯覆盖");
    expect(wrapper.text()).toContain("TRIAL_PLAN");
    expect(wrapper.text()).toContain("不代表已实施、已试运行或已获客户验收");
    expect(window.sessionStorage.length).toBe(0);
    wrapper.unmount();
  });

  it("does not read another project and clears old content on route change", async () => {
    const router = createAppRouter(createMemoryHistory());
    await router.push(`/projects/${project}/structured-solution-specs/${spec}`);
    await router.isReady();
    const reader = { detail: vi.fn().mockResolvedValue(detail) };
    const wrapper = mount(ProjectStructuredSpecDetailView, { props: {
      session: await session(), reader: reader as unknown as StructuredSpecReadClient },
    global: { plugins: [router] } });
    await flushPromises();
    expect(wrapper.text()).toContain("数据迁移设计");
    await router.push(`/projects/${other}/structured-solution-specs/${spec}`);
    await flushPromises();
    expect(reader.detail).toHaveBeenCalledTimes(1);
    expect(wrapper.text()).toContain("没有此项目的读取权限");
    expect(wrapper.text()).not.toContain("数据迁移设计");
    wrapper.unmount();
  });

  it("shows read failure without presenting old data", async () => {
    const router = createAppRouter(createMemoryHistory());
    await router.push(`/projects/${project}/structured-solution-specs/${spec}`);
    await router.isReady();
    const reader = { detail: vi.fn().mockRejectedValue(new Error("读取失败")) };
    const wrapper = mount(ProjectStructuredSpecDetailView, { props: {
      session: await session(), reader: reader as unknown as StructuredSpecReadClient },
    global: { plugins: [router] } });
    await flushPromises();
    expect(wrapper.get("[role=alert]").text()).toBe("读取失败");
    expect(wrapper.text()).not.toContain("设计内容");
    wrapper.unmount();
  });
});
