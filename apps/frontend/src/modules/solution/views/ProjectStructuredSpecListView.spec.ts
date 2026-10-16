import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { StructuredSpecListClient } from "@/modules/solution/api/structuredSpecListClient";
import ProjectStructuredSpecListView from "./ProjectStructuredSpecListView.vue";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const otherProject = "02234567-89ab-4cde-8123-456789abcdef";
const newest = "71234567-89ab-7cde-8123-456789abcdef";
const older = "61234567-89ab-7cde-8123-456789abcdef";
const series = "11234567-89ab-4cde-8123-456789abcdef";
const item = { structured_solution_spec_id: newest, spec_series_id: series,
  project_id: project, spec_type: "MIGRATION_SPEC", version_no: 2,
  version_state: "DRAFT", content_fingerprint: "a".repeat(64),
  payload_fingerprint: "b".repeat(64), supersedes_version_ref: older,
  review_ref: null, review_round_ref: null, created_by: project,
  created_at: "2026-10-16T00:00:00Z" };
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

describe("ProjectStructuredSpecListView", () => {
  afterEach(() => vi.restoreAllMocks());

  it("lists fixed summaries, paginates and links to exact detail", async () => {
    const router = createAppRouter(createMemoryHistory());
    expect(router.resolve(`/projects/${project}/structured-solution-specs`).name)
      .toBe("project-structured-specs");
    await router.push(`/projects/${project}/structured-solution-specs`); await router.isReady();
    const reader = { list: vi.fn().mockResolvedValueOnce({ items: [item],
      next_cursor: "cursor", has_more: true }).mockResolvedValueOnce({ items: [{ ...item,
      structured_solution_spec_id: older, version_no: 1, supersedes_version_ref: null }],
      next_cursor: null, has_more: false }) };
    const wrapper = mount(ProjectStructuredSpecListView, { props: { session: await session(),
      reader: reader as unknown as StructuredSpecListClient }, global: { plugins: [router] } });
    await flushPromises();
    expect(reader.list).toHaveBeenCalledWith(project, 50, null);
    expect(wrapper.text()).toContain("DRAFT、历史引用或出现在列表中都不代表已经批准");
    expect(wrapper.text()).toContain("数据迁移设计 · 版本 2 · 待评审草案");
    expect(wrapper.text()).not.toContain("payload");
    expect(wrapper.get(`a[href="/projects/${project}/structured-solution-specs/${newest}"]`)
      .text()).toContain("查看固定版本详情");
    await wrapper.findAll("button").find(button => button.text() === "加载更早版本")!.trigger("click");
    await flushPromises();
    expect(reader.list).toHaveBeenCalledWith(project, 50, "cursor");
    expect(wrapper.text()).toContain("版本 1 · 待评审草案"); wrapper.unmount();
  });

  it("shows create navigation only for project write roles", async () => {
    const router = createAppRouter(createMemoryHistory());
    await router.push(`/projects/${project}/structured-solution-specs`); await router.isReady();
    const reader = { list: vi.fn().mockResolvedValue({ items: [], next_cursor: null,
      has_more: false }) };
    const member = mount(ProjectStructuredSpecListView, { props: { session: await session(),
      reader: reader as unknown as StructuredSpecListClient }, global: { plugins: [router] } });
    await flushPromises(); expect(member.text()).not.toContain("创建结构化专项草案"); member.unmount();
    const managerRouter = createAppRouter(createMemoryHistory());
    await managerRouter.push(`/projects/${project}/structured-solution-specs`);
    await managerRouter.isReady();
    const manager = mount(ProjectStructuredSpecListView, { props: { session: await session("PROJECT_MANAGER"),
      reader: reader as unknown as StructuredSpecListClient }, global: { plugins: [managerRouter] } });
    await flushPromises();
    expect(manager.get(`a[href="/projects/${project}/structured-solution-specs/new"]`).text())
      .toContain("创建结构化专项草案"); manager.unmount();
  });

  it("clears prior items and avoids reads outside the current project", async () => {
    const router = createAppRouter(createMemoryHistory());
    await router.push(`/projects/${project}/structured-solution-specs`); await router.isReady();
    const reader = { list: vi.fn().mockResolvedValue({ items: [item], next_cursor: null,
      has_more: false }) };
    const wrapper = mount(ProjectStructuredSpecListView, { props: { session: await session(),
      reader: reader as unknown as StructuredSpecListClient }, global: { plugins: [router] } });
    await flushPromises(); expect(wrapper.text()).toContain("数据迁移设计");
    await router.push(`/projects/${otherProject}/structured-solution-specs`); await flushPromises();
    expect(reader.list).toHaveBeenCalledTimes(1);
    expect(wrapper.text()).toContain("没有此项目的读取权限");
    expect(wrapper.text()).not.toContain("数据迁移设计"); wrapper.unmount();
  });

  it("clears partial history when a later page cannot be trusted", async () => {
    const router = createAppRouter(createMemoryHistory());
    await router.push(`/projects/${project}/structured-solution-specs`); await router.isReady();
    const reader = { list: vi.fn().mockResolvedValueOnce({ items: [item], next_cursor: "cursor",
      has_more: true }).mockRejectedValueOnce(new Error("读取失败")) };
    const wrapper = mount(ProjectStructuredSpecListView, { props: { session: await session(),
      reader: reader as unknown as StructuredSpecListClient }, global: { plugins: [router] } });
    await flushPromises();
    await wrapper.findAll("button").find(button => button.text() === "加载更早版本")!.trigger("click");
    await flushPromises();
    expect(wrapper.get("[role=alert]").text()).toBe("读取失败");
    expect(wrapper.text()).not.toContain("数据迁移设计"); wrapper.unmount();
  });
});
