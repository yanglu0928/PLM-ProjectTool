import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { PlanReadClient } from "@/modules/plan/api/planReadClient";
import ProjectPlanListView from "./ProjectPlanListView.vue";
import ProjectPlanDetailView from "./ProjectPlanDetailView.vue";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const other = "02234567-89ab-4cde-8123-456789abcdef";
const plan = "21234567-89ab-4cde-8123-456789abcdef";
const second = "11234567-89ab-4cde-8123-456789abcdef";
const token = `${"a".repeat(40)}.${"b".repeat(43)}`;
const item = { plan_id: plan, project_id: project, name: "实施计划甲",
  plan_state: "ACTIVE", current_approved_version_ref: null,
  created_at: "2026-10-19T00:00:00Z", etag: '"v0"' };
const secondItem = { ...item, plan_id: second, name: "实施计划乙" };
function success(data: unknown): Response {
  return new Response(JSON.stringify({ data, trace_id: project }), { status: 200,
    headers: { "Content-Type": "application/json" } });
}
async function session(role = "CUSTOMER_MEMBER"): Promise<SessionClient> {
  const api = new SessionClient(vi.fn().mockResolvedValue(success({
    user: { user_id: project, username_display: "合成用户" }, deployment_role: "NONE",
    password_change_required: false,
    authorized_projects: [{ project_id: project, name: "项目", role }],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64),
  })) as typeof fetch);
  await api.login("user", "synthetic-only"); return api;
}

describe("Project Plan current identity pages", () => {
  afterEach(() => vi.restoreAllMocks());

  it("routes from project to list and detail, keeps versions and WBS unclaimed", async () => {
    const router = createAppRouter(createMemoryHistory());
    expect(router.resolve(`/projects/${project}/plans`).name).toBe("project-plans");
    expect(router.resolve(`/projects/${project}/plans/new`).name).toBe("project-plan-create");
    expect(router.resolve(`/projects/${project}/plans/${plan}`).name).toBe("project-plan-detail");
    await router.push(`/projects/${project}/plans`); await router.isReady();
    const reader = { list: vi.fn().mockResolvedValueOnce({ items: [item], next_cursor: token, has_more: true })
      .mockResolvedValueOnce({ items: [secondItem], next_cursor: null, has_more: false }) };
    const wrapper = mount(ProjectPlanListView, { props: { session: await session(),
      reader: reader as unknown as PlanReadClient }, global: { plugins: [router] } });
    await flushPromises();
    expect(reader.list).toHaveBeenCalledWith(project, 50, null);
    expect(wrapper.text()).toContain("计划版本、实施 WBS");
    expect(wrapper.text()).toContain("尚无已审批计划版本");
    expect(wrapper.get(`a[href="/projects/${project}/plans/${plan}"]`).text()).toContain("查看计划详情");
    expect(wrapper.find(`a[href="/projects/${project}/plans/new"]`).exists()).toBe(false);
    await wrapper.findAll("button").find(button => button.text() === "加载更多计划")!.trigger("click");
    await flushPromises();
    expect(reader.list).toHaveBeenCalledWith(project, 50, token);
    expect(wrapper.text()).toContain("实施计划乙");
    wrapper.unmount();
  });

  it("shows create entry for project writers and rejects duplicate next page", async () => {
    const router = createAppRouter(createMemoryHistory());
    await router.push(`/projects/${project}/plans`); await router.isReady();
    const reader = { list: vi.fn().mockResolvedValueOnce({ items: [item], next_cursor: token, has_more: true })
      .mockResolvedValueOnce({ items: [item], next_cursor: null, has_more: false }) };
    const wrapper = mount(ProjectPlanListView, { props: { session: await session("PROJECT_MANAGER"),
      reader: reader as unknown as PlanReadClient }, global: { plugins: [router] } });
    await flushPromises();
    expect(wrapper.get(`a[href="/projects/${project}/plans/new"]`).text()).toContain("创建实施计划");
    await wrapper.findAll("button").find(button => button.text() === "加载更多计划")!.trigger("click");
    await flushPromises();
    expect(wrapper.findAll("li")).toHaveLength(0);
    expect(wrapper.text()).toContain("暂时无法读取实施计划");
    wrapper.unmount();
  });

  it("clears old project data and ignores late responses after route switch", async () => {
    const router = createAppRouter(createMemoryHistory());
    await router.push(`/projects/${project}/plans`); await router.isReady();
    let resolveFirst!: (value: unknown) => void;
    const reader = { list: vi.fn().mockImplementation(() => new Promise(resolve => { resolveFirst = resolve; })) };
    const wrapper = mount(ProjectPlanListView, { props: { session: await session(),
      reader: reader as unknown as PlanReadClient }, global: { plugins: [router] } });
    await flushPromises();
    await router.push(`/projects/${other}/plans`); await flushPromises();
    resolveFirst({ items: [item], next_cursor: null, has_more: false }); await flushPromises();
    expect(wrapper.text()).not.toContain("实施计划甲");
    expect(reader.list).toHaveBeenCalledTimes(1);
    expect(wrapper.text()).toContain("无权查看");
    wrapper.unmount();
  });

  it("reads one current identity without presenting approval as delivery", async () => {
    const router = createAppRouter(createMemoryHistory());
    await router.push(`/projects/${project}/plans/${plan}`); await router.isReady();
    const reader = { current: vi.fn().mockResolvedValue({ ...item, created_by: project }) };
    const wrapper = mount(ProjectPlanDetailView, { props: { session: await session(),
      reader: reader as unknown as PlanReadClient }, global: { plugins: [router] } });
    await flushPromises();
    expect(reader.current).toHaveBeenCalledWith(project, plan);
    expect(wrapper.text()).toContain("尚无已审批计划版本");
    expect(wrapper.text()).toContain("不得据此判断实施计划已交付");
    expect(wrapper.get(`a[href="/projects/${project}/plans"]`).text()).toContain("返回实施计划");
    wrapper.unmount();
  });
});
