import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { StructuredSpecCreateClient, StructuredSpecCreateError } from
  "@/modules/solution/api/structuredSpecCreateClient";
import ProjectStructuredSpecCreateView from "./ProjectStructuredSpecCreateView.vue";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const requirement = "11234567-89ab-4cde-8123-456789abcdef";
const requirementVersion = "21234567-89ab-4cde-8123-456789abcdef";
const section = "31234567-89ab-4cde-8123-456789abcdef";
const sectionVersion = "41234567-89ab-4cde-8123-456789abcdef";
const evidence = "51234567-89ab-4cde-8123-456789abcdef";
const created = "61234567-89ab-4cde-8123-456789abcdef";
const series = "71234567-89ab-4cde-8123-456789abcdef";
const candidates = {
  requirements: [{ requirement_id: requirement, project_id: project,
    requirement_code: "REQ-1", current_approved_version_ref: requirementVersion,
    state: "ACTIVE" }],
  sections: [{ section: { solution_section_id: section, project_id: project,
    section_key: "设计", section_state: "ACTIVE" }, version: {
      solution_section_version_id: sectionVersion, solution_section_id: section,
      project_id: project, version_no: 1, version_state: "DRAFT", title: "方案草案" } }],
  evidence: [{ evidence_id: evidence, display_label: "调研证据", eligibility_state: "ELIGIBLE" }],
};
async function session(role = "PROJECT_MANAGER") {
  const api = new SessionClient(vi.fn().mockResolvedValue(new Response(JSON.stringify({ data: {
    user: { user_id: project, username_display: "合成用户" }, deployment_role: "NONE",
    password_change_required: false,
    authorized_projects: [{ project_id: project, name: "项目", role }],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64),
  }, trace_id: project }), { status: 200, headers: { "Content-Type": "application/json" } })) as typeof fetch);
  await api.login("user", "synthetic-only"); return api;
}
async function page(role = "PROJECT_MANAGER", create = vi.fn().mockResolvedValue({
  structured_solution_spec_id: created, spec_series_id: series }),
  candidateLoader = vi.fn().mockResolvedValue(candidates)) {
  const router = createAppRouter(createMemoryHistory());
  await router.push(`/projects/${project}/structured-solution-specs/new`); await router.isReady();
  const wrapper = mount(ProjectStructuredSpecCreateView, { props: {
    session: await session(role), creator: { create } as unknown as StructuredSpecCreateClient,
    candidateLoader }, global: { plugins: [router] } });
  await flushPromises(); return { wrapper, router, create, candidateLoader };
}
async function fill(wrapper: Awaited<ReturnType<typeof page>>["wrapper"]) {
  await wrapper.get(`input[value="${requirement}"]`).setValue(true);
  await wrapper.get(`input[value="${section}"]`).setValue(true);
  await wrapper.get(`input[value="${evidence}"]`).setValue(true);
  await wrapper.get("#spec-source").setValue("旧 PLM");
  await wrapper.get("#spec-target").setValue("新 PLM");
  await wrapper.get("#spec-mappings").setValue("old_id → part_id");
  await wrapper.get("#spec-scope").setValue("零件");
  await wrapper.get("#spec-cleansing").setValue("去重");
  await wrapper.get("#spec-trial").setValue("试点");
  await wrapper.get("#spec-reconcile").setValue("对账");
  await wrapper.get("#spec-rollback").setValue("恢复快照");
  await wrapper.get("#spec-acceptance").setValue("差异为零");
  const checks = wrapper.findAll('input[type="checkbox"]');
  await checks[checks.length - 1]!.setValue(true);
}

describe("ProjectStructuredSpecCreateView", () => {
  afterEach(() => { window.sessionStorage.clear(); vi.restoreAllMocks(); });
  it("gates writers and candidate failures", async () => {
    const denied = await page("CUSTOMER_MEMBER");
    expect(denied.wrapper.find("form").exists()).toBe(false);
    expect(denied.candidateLoader).not.toHaveBeenCalled(); denied.wrapper.unmount();
    const unavailable = await page("PROJECT_MANAGER", vi.fn(),
      vi.fn().mockRejectedValue(new Error("incomplete")));
    expect(unavailable.wrapper.find("form").exists()).toBe(false);
    expect(unavailable.wrapper.text()).toContain("incomplete"); unavailable.wrapper.unmount();
  });
  it("submits human fields as fixed source DRAFT without auto-approval", async () => {
    const view = await page();
    expect(view.router.currentRoute.value.name).toBe("project-structured-spec-create");
    expect(view.wrapper.get(`a[href="/projects/${project}/structured-solution-specs"]`).text())
      .toContain("查看专项版本历史");
    await fill(view.wrapper);
    await view.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(view.create).toHaveBeenCalledExactlyOnceWith(project, {
      spec_type: "MIGRATION_SPEC", payload: {
        source_system: "旧 PLM", target_system: "新 PLM", scope: "零件",
        field_mappings: [{ source: "old_id", target: "part_id" }],
        cleansing_rules: ["去重"], trial_plan: "试点", reconciliation_plan: "对账",
        rollback_plan: "恢复快照", acceptance_criteria: "差异为零",
        assumptions: [], exclusions: [],
      },
      requirement_refs: [{ requirement_id: requirement, requirement_version_id: requirementVersion }],
      section_refs: [{ solution_section_id: section, solution_section_version_id: sectionVersion }],
      evidence_ids: [evidence], artifact_ids: [],
    }, expect.any(String));
    expect(view.wrapper.text()).toContain("仅为 DRAFT");
    expect(view.wrapper.get(`a[href="/projects/${project}/structured-solution-specs/${created}"]`)
      .text()).toContain("查看专项详情");
    expect(window.sessionStorage.length).toBe(0); view.wrapper.unmount();
  });
  it("keeps exact original body and key across uncertain reload", async () => {
    const create = vi.fn().mockRejectedValueOnce(new StructuredSpecCreateError("STRUCTURED_SPEC_CREATE_UNCERTAIN"))
      .mockResolvedValueOnce({ structured_solution_spec_id: created, spec_series_id: series });
    const first = await page("PROJECT_MANAGER", create); await fill(first.wrapper);
    await first.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(window.sessionStorage.length).toBe(1);
    const original = create.mock.calls[0]; first.wrapper.unmount();
    const second = await page("PROJECT_MANAGER", create);
    expect(second.wrapper.find("#spec-source").exists()).toBe(false);
    expect(second.wrapper.get("button[type=submit]").attributes("disabled")).toBeDefined();
    await second.wrapper.get('input[type="checkbox"]').setValue(true);
    await second.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(create.mock.calls[1]).toEqual(original);
    expect(window.sessionStorage.length).toBe(0); second.wrapper.unmount();
  });
  it("restores pending operation when returning to the same project route", async () => {
    const create = vi.fn().mockRejectedValueOnce(new StructuredSpecCreateError("STRUCTURED_SPEC_CREATE_UNCERTAIN"));
    const view = await page("PROJECT_MANAGER", create); await fill(view.wrapper);
    await view.wrapper.get("form").trigger("submit"); await flushPromises();
    await view.router.push(`/projects/${project}/solution-sections`); await flushPromises();
    await view.router.push(`/projects/${project}/structured-solution-specs/new`); await flushPromises();
    expect(view.wrapper.text()).toContain("存在原创建操作");
    expect(view.wrapper.find("#spec-source").exists()).toBe(false);
    view.wrapper.unmount();
  });
  it("stops when original operation cannot be stored or parsed", async () => {
    const create = vi.fn(); const view = await page("PROJECT_MANAGER", create); await fill(view.wrapper);
    const storage = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
    await view.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(create).not.toHaveBeenCalled(); storage.mockRestore(); view.wrapper.unmount();
    window.sessionStorage.setItem(`plm.sol.spec.create.pending.${project}.${project}`, "corrupt");
    const restored = await page("PROJECT_MANAGER", create);
    expect(restored.wrapper.text()).toContain("已停止提交");
    restored.wrapper.unmount();
    window.sessionStorage.setItem(`plm.sol.spec.create.pending.${project}.${project}`,
      JSON.stringify({ project, actor: project, key: "k".repeat(16), draft: {} }));
    const malformed = await page("PROJECT_MANAGER", create);
    expect(malformed.wrapper.text()).toContain("已停止提交");
    malformed.wrapper.unmount();
  });
});
