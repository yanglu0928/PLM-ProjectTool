import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { StructuredSpecReadClient, type StructuredSpecDetail } from
  "@/modules/solution/api/structuredSpecReadClient";
import { StructuredSpecReviseClient, StructuredSpecReviseError } from
  "@/modules/solution/api/structuredSpecReviseClient";
import ProjectStructuredSpecReviseView from "./ProjectStructuredSpecReviseView.vue";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const predecessor = "11234567-89ab-4cde-8123-456789abcdef";
const revised = "21234567-89ab-4cde-8123-456789abcdef";
const requirement = "31234567-89ab-4cde-8123-456789abcdef";
const requirementVersion = "41234567-89ab-4cde-8123-456789abcdef";
const section = "51234567-89ab-4cde-8123-456789abcdef";
const sectionVersion = "61234567-89ab-4cde-8123-456789abcdef";
const evidence = "71234567-89ab-4cde-8123-456789abcdef";
const detail: StructuredSpecDetail = { structured_solution_spec_id: predecessor, spec_series_id: predecessor,
  project_id: project, spec_type: "MIGRATION_SPEC", version_no: 1, version_state: "DRAFT",
  content_fingerprint: "a".repeat(64), payload_fingerprint: "b".repeat(64),
  payload: { assumptions: ["客户尚未确认"], exclusions: [], source_system: "旧 PLM",
    target_system: "新 PLM", scope: "零件", cleansing_rules: ["去重"],
    field_mappings: [{ source: "old_id", target: "part_id" }], trial_plan: "先试点",
    reconciliation_plan: "逐条核对", rollback_plan: "恢复快照",
    acceptance_criteria: "差异清零" },
  requirement_refs: [{ requirement_id: requirement, requirement_version_id: requirementVersion }],
  section_refs: [{ solution_section_id: section, solution_section_version_id: sectionVersion }],
  evidence_ids: [evidence], artifact_ids: [], declared_requirement_count: 1,
  declared_section_count: 1, declared_evidence_count: 1, supersedes_version_ref: null,
  review_ref: null, review_round_ref: null, created_by: project,
  created_at: "2026-10-16T00:00:00Z" };
const candidates = { requirements: [{ requirement_id: requirement, project_id: project,
  requirement_code: "REQ-1", current_approved_version_ref: requirementVersion, state: "ACTIVE" }],
  sections: [{ section: { solution_section_id: section, project_id: project,
    section_key: "设计", section_state: "ACTIVE" }, version: {
      solution_section_version_id: sectionVersion, solution_section_id: section,
      project_id: project, version_no: 1, version_state: "DRAFT", title: "方案草案" } }],
  evidence: [{ evidence_id: evidence, display_label: "调研证据", eligibility_state: "ELIGIBLE" }] };
async function session(role = "PROJECT_MANAGER") {
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
async function page(options: { role?: string; fixed?: typeof detail; revise?: ReturnType<typeof vi.fn>;
  available?: typeof candidates } = {}) {
  const router = createAppRouter(createMemoryHistory());
  await router.push(`/projects/${project}/structured-solution-specs/${predecessor}/revise`);
  await router.isReady();
  const read = vi.fn().mockResolvedValue(options.fixed ?? detail);
  const revise = options.revise ?? vi.fn().mockResolvedValue({
    structured_solution_spec_id: revised, version_no: 2 });
  const candidateLoader = vi.fn().mockResolvedValue(options.available ?? candidates);
  const wrapper = mount(ProjectStructuredSpecReviseView, { props: {
    session: await session(options.role), reader: { detail: read } as unknown as StructuredSpecReadClient,
    reviser: { revise } as unknown as StructuredSpecReviseClient, candidateLoader },
  global: { plugins: [router] } });
  await flushPromises(); return { wrapper, router, read, revise, candidateLoader };
}
function confirmation(wrapper: Awaited<ReturnType<typeof page>>["wrapper"]) {
  const checks = wrapper.findAll('input[type="checkbox"]');
  return checks[checks.length - 1]!;
}

describe("ProjectStructuredSpecReviseView", () => {
  afterEach(() => { window.sessionStorage.clear(); vi.restoreAllMocks(); });
  it("prefills a lossless fixed version and submits an explicit new DRAFT", async () => {
    const view = await page();
    expect(view.router.currentRoute.value.name).toBe("project-structured-spec-revise");
    expect((view.wrapper.get(`input[value="${requirement}"]`).element as HTMLInputElement).checked).toBe(true);
    expect((view.wrapper.get(`input[value="${section}"]`).element as HTMLInputElement).checked).toBe(true);
    expect((view.wrapper.get(`input[value="${evidence}"]`).element as HTMLInputElement).checked).toBe(true);
    expect((view.wrapper.get("#revise-source").element as HTMLInputElement).value).toBe("旧 PLM");
    await view.wrapper.get("#revise-scope").setValue("零件与 BOM");
    await confirmation(view.wrapper).setValue(true);
    await view.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(view.revise).toHaveBeenCalledExactlyOnceWith(project, predecessor,
      expect.objectContaining({ spec_type: "MIGRATION_SPEC",
        payload: expect.objectContaining({ scope: "零件与 BOM", source_system: "旧 PLM" }),
        requirement_refs: [{ requirement_id: requirement,
          requirement_version_id: requirementVersion }],
        section_refs: [{ solution_section_id: section,
          solution_section_version_id: sectionVersion }], evidence_ids: [evidence], artifact_ids: [] }),
      expect.any(String));
    expect(view.wrapper.text()).toContain("当前仅为 DRAFT");
    expect(view.wrapper.find(`a[href="/projects/${project}/structured-solution-specs/${revised}"]`).exists()).toBe(true);
    expect(window.sessionStorage.length).toBe(0); view.wrapper.unmount();
  });
  it("never loads a revision form for a non-writer or an in-review version", async () => {
    const denied = await page({ role: "CUSTOMER_MEMBER" });
    expect(denied.read).not.toHaveBeenCalled(); expect(denied.candidateLoader).not.toHaveBeenCalled();
    expect(denied.wrapper.find("form").exists()).toBe(false); denied.wrapper.unmount();
    const inReview = await page({ fixed: { ...detail, version_state: "IN_REVIEW" } });
    expect(inReview.wrapper.find("form").exists()).toBe(false);
    expect(inReview.wrapper.text()).toContain("不允许修订"); inReview.wrapper.unmount();
  });
  it("keeps the exact body and operation key after an uncertain result", async () => {
    const revise = vi.fn().mockRejectedValueOnce(
      new StructuredSpecReviseError("STRUCTURED_SPEC_REVISE_UNCERTAIN"))
      .mockResolvedValueOnce({ structured_solution_spec_id: revised, version_no: 2 });
    const first = await page({ revise });
    await first.wrapper.get("#revise-scope").setValue("改后范围");
    await confirmation(first.wrapper).setValue(true);
    await first.wrapper.get("form").trigger("submit"); await flushPromises();
    const original = revise.mock.calls[0]; expect(window.sessionStorage.length).toBe(1);
    first.wrapper.unmount();
    const second = await page({ revise });
    expect(second.wrapper.find("#revise-source").exists()).toBe(false);
    expect(second.wrapper.text()).toContain("存在原修订操作");
    await second.wrapper.get('input[type="checkbox"]').setValue(true);
    await second.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(revise.mock.calls[1]).toEqual(original);
    expect(window.sessionStorage.length).toBe(0); second.wrapper.unmount();
  });
  it("does not silently replace a historical source with its newer current version", async () => {
    const newer = "81234567-89ab-4cde-8123-456789abcdef";
    const available = { ...candidates, requirements: [{ ...candidates.requirements[0]!,
      current_approved_version_ref: newer }] };
    const view = await page({ available });
    expect((view.wrapper.get(`input[value="${requirement}"]`).element as HTMLInputElement).checked).toBe(false);
    expect(view.wrapper.text()).toContain("系统没有自动替换");
    await confirmation(view.wrapper).setValue(true);
    await view.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(view.revise).not.toHaveBeenCalled();
    expect(view.wrapper.get("[role=alert]").text()).toContain("至少一条当前已批准需求");
    view.wrapper.unmount();
  });
});
