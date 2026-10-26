import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { PlanVersionReadClient } from "@/modules/plan/api/planVersionReadClient";
import { PlanVersionWriteClient, PlanVersionWriteError } from "@/modules/plan/api/planVersionWriteClient";
import ProjectPlanVersionValidateView from "./ProjectPlanVersionValidateView.vue";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const plan = "11234567-89ab-4cde-8123-456789abcdef";
const version = "21234567-89ab-4cde-8123-456789abcdef";
const user = "31234567-89ab-4cde-8123-456789abcdef";
const trace = "41234567-89ab-4cde-8123-456789abcdef";
const coverage = { requirement_total: 2, requirement_mapped: 1, requirement_excluded: 0, requirement_uncovered: 1,
  solution_total: 1, solution_mapped: 1, solution_excluded: 0, solution_uncovered: 0 };
const row = { plan_version_id: version, plan_id: plan, project_id: project, version_no: 1, version_state: "DRAFT",
  created_by: user, supersedes_version_ref: null, review_ref: null, review_round_ref: null,
  created_at: "2026-10-26T00:00:00Z", calendar_ref: "CN_WORKDAY", approved_solution_refs: [], wbs_items: [],
  dependencies: [], milestones: [], exclusions: [] };
function response(data: unknown) { return new Response(JSON.stringify({ data, trace_id: trace }), { status: 200, headers: { "Content-Type": "application/json" } }); }
async function makeSession() {
  const api = new SessionClient(vi.fn().mockResolvedValue(response({ user: { user_id: user, username_display: "合成负责人" },
    deployment_role: "NONE", password_change_required: false,
    authorized_projects: [{ project_id: project, name: "合成项目", role: "PROJECT_MANAGER" }],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "a".repeat(64) })) as typeof fetch);
  await api.login("user", "synthetic-only"); return api;
}
function route() { return createAppRouter(createMemoryHistory()); }

describe("PlanVersion validation page", () => {
  beforeEach(() => { window.sessionStorage.clear(); });

  it("only validates after user action and renders the full current-snapshot report", async () => {
    const router = route(); await router.push(`/projects/${project}/plans/${plan}/versions/${version}/validate`); await router.isReady();
    const reader = { detail: vi.fn().mockResolvedValue(row) };
    const validator = { validate: vi.fn().mockResolvedValue({ valid: false, blocking_issues: ["REQUIREMENT_UNCOVERED"],
      warnings: ["SOURCE_WARNING"], coverage_summary: coverage, checked_at: "2026-10-26T01:02:03Z" }) };
    const view = mount(ProjectPlanVersionValidateView, { props: { session: await makeSession(),
      reader: reader as unknown as PlanVersionReadClient, validator: validator as unknown as PlanVersionWriteClient }, global: { plugins: [router] } });
    await flushPromises(); expect(reader.detail).toHaveBeenCalledWith(project, plan, version);
    expect(validator.validate).not.toHaveBeenCalled();
    await view.get("button").trigger("click"); await flushPromises();
    expect(validator.validate).toHaveBeenCalledWith(project, plan, version, expect.any(String));
    expect(view.text()).toContain("发现阻断问题"); expect(view.text()).toContain("REQUIREMENT_UNCOVERED");
    expect(view.text()).toContain("SOURCE_WARNING"); expect(view.text()).toContain("未覆盖需求");
    expect(view.text()).toContain("不代表批准"); expect(window.sessionStorage.length).toBe(0); view.unmount();
  });

  it("keeps the original operation key after an uncertain response for exact retry", async () => {
    const router = route(); await router.push(`/projects/${project}/plans/${plan}/versions/${version}/validate`); await router.isReady();
    const validator = { validate: vi.fn().mockRejectedValueOnce(new PlanVersionWriteError("SYSTEM_UNAVAILABLE"))
      .mockResolvedValueOnce({ valid: true, blocking_issues: [], warnings: [], coverage_summary: coverage,
        checked_at: "2026-10-26T01:02:03Z" }) };
    const view = mount(ProjectPlanVersionValidateView, { props: { session: await makeSession(),
      reader: { detail: vi.fn().mockResolvedValue(row) } as unknown as PlanVersionReadClient,
      validator: validator as unknown as PlanVersionWriteClient }, global: { plugins: [router] } });
    await flushPromises(); await view.get("button").trigger("click"); await flushPromises();
    const saved = JSON.parse(window.sessionStorage.getItem(`plm:plan-version-validate:${project}:${plan}:${version}`)!);
    await view.get("button").trigger("click"); await flushPromises();
    expect(validator.validate.mock.calls[0]?.[3]).toBe(saved.key);
    expect(validator.validate.mock.calls[1]?.[3]).toBe(saved.key);
    expect(view.text()).toContain("验证通过"); expect(window.sessionStorage.length).toBe(0); view.unmount();
  });

  it("does not expose validation to a customer member", async () => {
    const router = route(); await router.push(`/projects/${project}/plans/${plan}/versions/${version}/validate`); await router.isReady();
    const api = new SessionClient(vi.fn().mockResolvedValue(response({ user: { user_id: user, username_display: "客户" },
      deployment_role: "NONE", password_change_required: false,
      authorized_projects: [{ project_id: project, name: "合成项目", role: "CUSTOMER_MEMBER" }],
      absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "a".repeat(64) })) as typeof fetch);
    await api.login("customer", "synthetic-only"); const validator = { validate: vi.fn() };
    const view = mount(ProjectPlanVersionValidateView, { props: { session: api,
      reader: { detail: vi.fn() } as unknown as PlanVersionReadClient,
      validator: validator as unknown as PlanVersionWriteClient }, global: { plugins: [router] } });
    await flushPromises(); expect(view.text()).toContain("无权核查"); expect(validator.validate).not.toHaveBeenCalled(); view.unmount();
  });
});
