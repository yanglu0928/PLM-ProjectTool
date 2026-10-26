import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { PlanVersionReadClient } from "@/modules/plan/api/planVersionReadClient";
import { PlanVersionWriteClient } from "@/modules/plan/api/planVersionWriteClient";
import { loadPlanApprovedSolutions } from "@/modules/plan/api/planVersionApprovedSolutions";
import ProjectPlanVersionCreateView from "./ProjectPlanVersionCreateView.vue";
const project = "01234567-89ab-4cde-8123-456789abcdef"; const plan = "11234567-89ab-4cde-8123-456789abcdef";
const version = "21234567-89ab-4cde-8123-456789abcdef"; const user = "31234567-89ab-4cde-8123-456789abcdef";
const trace = "41234567-89ab-4cde-8123-456789abcdef";
const ref = { resource_kind: "OUTLINE", resource_id: user, version_id: version, spec_series_id: null, spec_type: null };
const candidate = { outline: { solution_outline_version_id: version }, refs: [ref], display: ["方案甲 · v2"] };
function response(data: unknown) { return new Response(JSON.stringify({ data, trace_id: trace }), { status: 200, headers: { "Content-Type": "application/json" } }); }
async function session() { const api = new SessionClient(vi.fn().mockResolvedValue(response({ user: { user_id: user, username_display: "合成负责人" },
  deployment_role: "NONE", password_change_required: false, authorized_projects: [{ project_id: project, name: "项目", role: "PROJECT_MANAGER" }],
  absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "a".repeat(64) })) as typeof fetch);
  await api.login("user", "synthetic-only"); return api; }
describe("ProjectPlanVersionCreateView", () => {
  it("previews required acceptance criteria, creates one immutable draft, then reads it back", async () => {
    window.sessionStorage.clear(); const router = createAppRouter(createMemoryHistory());
    await router.push(`/projects/${project}/plans/${plan}/versions/new`); await router.isReady();
    const candidateLoader = vi.fn().mockResolvedValue([candidate]);
    const creator = { create: vi.fn().mockImplementation(async (_p, _plan, draft) => ({ plan_version_id: "51234567-89ab-4cde-8123-456789abcdef",
      plan_id: plan, project_id: project, version_no: 1, version_state: "DRAFT", created_at: "2026-10-26T00:00:00Z" })) };
    const createdId = "51234567-89ab-4cde-8123-456789abcdef";
    const detail = { plan_version_id: createdId, plan_id: plan, project_id: project, version_no: 1, version_state: "DRAFT",
      created_by: user, supersedes_version_ref: null, review_ref: null, review_round_ref: null, created_at: "2026-10-26T00:00:00Z",
      calendar_ref: "CN_WORKDAY", approved_solution_refs: [ref], dependencies: [], milestones: [], exclusions: [] };
    const reader = { detail: vi.fn().mockImplementation(async () => {
      const sent = creator.create.mock.calls[0]![2] as Record<string, unknown>;
      return { ...detail, approved_solution_refs: sent.approved_solution_refs,
        wbs_items: sent.wbs_items as readonly Record<string, unknown>[] };
    }) };
    const wrapper = mount(ProjectPlanVersionCreateView, { props: { session: await session(), reader: reader as unknown as PlanVersionReadClient,
      creator: creator as unknown as PlanVersionWriteClient, candidateLoader: candidateLoader as typeof loadPlanApprovedSolutions }, global: { plugins: [router] } });
    await flushPromises(); expect(candidateLoader).toHaveBeenCalledTimes(1);
    await wrapper.get('input[type="radio"]').setValue(true);
    await wrapper.get("#plan-version-task-name").setValue("准备环境");
    await wrapper.get("#plan-version-acceptance").setValue("环境可复现");
    await wrapper.findAll("button").find(button => button.text() === "预览完整草稿")!.trigger("click");
    expect(wrapper.text()).toContain("创建不代表已批准"); expect(wrapper.text()).toContain("环境可复现");
    await wrapper.findAll("button").find(button => button.text() === "确认创建草稿版本")!.trigger("click");
    await flushPromises();
    expect(candidateLoader).toHaveBeenCalledTimes(2); expect(creator.create).toHaveBeenCalledTimes(1);
    const sent = creator.create.mock.calls[0]![2] as Record<string, unknown>;
    expect((sent.wbs_items as Array<Record<string, unknown>>)[0]?.acceptance_criteria).toEqual(["环境可复现"]);
    expect((sent.wbs_items as Array<Record<string, unknown>>)[0]?.solution_refs).toEqual([ref]);
    expect(reader.detail).toHaveBeenCalledWith(project, plan, createdId);
    expect(wrapper.text()).toContain("查看固定版本"); wrapper.unmount();
  });
  it("does not submit without acceptance criteria", async () => {
    const router = createAppRouter(createMemoryHistory()); await router.push(`/projects/${project}/plans/${plan}/versions/new`); await router.isReady();
    const creator = { create: vi.fn() };
    const wrapper = mount(ProjectPlanVersionCreateView, { props: { session: await session(), reader: { detail: vi.fn() } as unknown as PlanVersionReadClient,
      creator: creator as unknown as PlanVersionWriteClient, candidateLoader: vi.fn().mockResolvedValue([candidate]) as typeof loadPlanApprovedSolutions }, global: { plugins: [router] } });
    await flushPromises(); await wrapper.get('input[type="radio"]').setValue(true); await wrapper.get("#plan-version-task-name").setValue("准备环境");
    await wrapper.findAll("button").find(button => button.text() === "预览完整草稿")!.trigger("click");
    expect(wrapper.text()).toContain("验收标准至少填写一条"); expect(creator.create).not.toHaveBeenCalled(); wrapper.unmount();
  });
});
