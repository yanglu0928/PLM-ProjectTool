import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { PlanVersionReadClient } from "@/modules/plan/api/planVersionReadClient";
import ProjectPlanVersionListView from "./ProjectPlanVersionListView.vue";
import ProjectPlanVersionDetailView from "./ProjectPlanVersionDetailView.vue";
const project = "01234567-89ab-4cde-8123-456789abcdef";
const plan = "11234567-89ab-4cde-8123-456789abcdef";
const version = "21234567-89ab-4cde-8123-456789abcdef";
const user = "31234567-89ab-4cde-8123-456789abcdef";
const trace = "41234567-89ab-4cde-8123-456789abcdef";
const row = { plan_version_id: version, plan_id: plan, project_id: project, version_no: 1, version_state: "DRAFT",
  created_by: user, supersedes_version_ref: null, review_ref: null, review_round_ref: null, created_at: "2026-10-26T00:00:00Z" };
function response(data: unknown) { return new Response(JSON.stringify({ data, trace_id: trace }), { status: 200, headers: { "Content-Type": "application/json" } }); }
async function session() { const api = new SessionClient(vi.fn().mockResolvedValue(response({ user: { user_id: user, username_display: "合成用户" },
  deployment_role: "NONE", password_change_required: false, authorized_projects: [{ project_id: project, name: "项目", role: "CUSTOMER_MEMBER" }],
  absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "a".repeat(64) })) as typeof fetch);
  await api.login("user", "synthetic-only"); return api; }
describe("PlanVersion read-only pages", () => {
  it("routes to a history and fixed snapshot without implying approval or delivery", async () => {
    const router = createAppRouter(createMemoryHistory());
    expect(router.resolve(`/projects/${project}/plans/${plan}/versions`).name).toBe("project-plan-versions");
    expect(router.resolve(`/projects/${project}/plans/${plan}/versions/${version}`).name).toBe("project-plan-version-detail");
    await router.push(`/projects/${project}/plans/${plan}/versions`); await router.isReady();
    const reader = { list: vi.fn().mockResolvedValue({ items: [row], next_cursor: null, has_more: false }) };
    const list = mount(ProjectPlanVersionListView, { props: { session: await session(), reader: reader as unknown as PlanVersionReadClient }, global: { plugins: [router] } });
    await flushPromises(); expect(list.text()).toContain("版本 1 · DRAFT"); expect(list.text()).toContain("不等于当前批准");
    expect(list.get(`a[href="/projects/${project}/plans/${plan}/versions/${version}"]`).text()).toContain("查看固定快照");
    list.unmount();
    await router.push(`/projects/${project}/plans/${plan}/versions/${version}`); await flushPromises();
    const detailData = { ...row, calendar_ref: null, approved_solution_refs: [{ solution_id: user }], wbs_items: [{ name: "交付根任务" }],
      dependencies: [], milestones: [], exclusions: [] };
    const detailReader = { detail: vi.fn().mockResolvedValue(detailData) };
    const detail = mount(ProjectPlanVersionDetailView, { props: { session: await session(), reader: detailReader as unknown as PlanVersionReadClient }, global: { plugins: [router] } });
    await flushPromises(); expect(detail.text()).toContain("交付根任务"); expect(detail.text()).toContain("只读历史内容");
    expect(detail.text()).toContain("不执行Validate或Review"); detail.unmount();
  });
});
