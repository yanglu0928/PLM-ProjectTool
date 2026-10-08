import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { OutlineReadClient } from "@/modules/solution/api/outlineReadClient";
import ProjectOutlineListView from "./ProjectOutlineListView.vue";
import ProjectOutlineDetailView from "./ProjectOutlineDetailView.vue";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const other = "02234567-89ab-4cde-8123-456789abcdef";
const outline = "11234567-89ab-4cde-8123-456789abcdef";
const second = "21234567-89ab-4cde-8123-456789abcdef";
const token = `${"a".repeat(40)}.${"b".repeat(43)}`;
const item = { solution_outline_id: outline, project_id: project, name: "实施方案目录",
  outline_state: "ACTIVE", current_approved_version_ref: null,
  created_at: "2026-10-09T00:00:00Z", etag: '"v0"' };
const secondItem = { ...item, solution_outline_id: second, name: "另一目录" };
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

describe("PROJECT Outline read pages", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows project-only list, empty approved state and detail navigation", async () => {
    const router = createAppRouter(createMemoryHistory());
    expect(router.resolve(`/projects/${project}/solution-outlines`).name).toBe("project-outlines");
    expect(router.resolve(`/projects/${project}/solution-outlines/${outline}`).name).toBe("project-outline-detail");
    await router.push(`/projects/${project}/solution-outlines`); await router.isReady();
    const reader = { list: vi.fn().mockResolvedValueOnce({ items: [item], next_cursor: token, has_more: true })
      .mockResolvedValueOnce({ items: [secondItem], next_cursor: null, has_more: false }) };
    const wrapper = mount(ProjectOutlineListView, { props: { session: await session(),
      reader: reader as unknown as OutlineReadClient }, global: { plugins: [router] } });
    await flushPromises();
    expect(reader.list).toHaveBeenCalledWith(project, 50, null);
    expect(wrapper.text()).toContain("目录只是方案的逻辑身份");
    expect(wrapper.text()).toContain("尚无已审批版本");
    expect(wrapper.get(`a[href="/projects/${project}/solution-outlines/${outline}"]`).text())
      .toContain("目录详情");
    await wrapper.findAll("button").find(button => button.text() === "加载更多目录")!.trigger("click");
    await flushPromises();
    expect(reader.list).toHaveBeenCalledWith(project, 50, token);
    expect(wrapper.text()).toContain("另一目录");
    wrapper.unmount();
  });

  it("reads one exact identity without presenting approval as formal delivery", async () => {
    const router = createAppRouter(createMemoryHistory());
    await router.push(`/projects/${project}/solution-outlines/${outline}`); await router.isReady();
    const reader = { current: vi.fn().mockResolvedValue({ ...item, created_by: project }) };
    const wrapper = mount(ProjectOutlineDetailView, { props: { session: await session(),
      reader: reader as unknown as OutlineReadClient }, global: { plugins: [router] } });
    await flushPromises();
    expect(reader.current).toHaveBeenCalledWith(project, outline);
    expect(wrapper.text()).toContain("尚无已审批版本");
    expect(wrapper.text()).toContain("不得据此判断方案已交付");
    expect(wrapper.get(`a[href="/projects/${project}/solution-outlines"]`).text()).toContain("返回方案目录");
    expect(wrapper.get(`a[href="/projects/${project}/solution-sections"]`).text())
      .toContain("整个项目的方案章节");
    expect(wrapper.find(`a[href="/projects/${project}/solution-outlines/${outline}/sections/new"]`).exists())
      .toBe(false);
    wrapper.unmount();
  });

  it("shows Section create entry only for a current writer and active parent", async () => {
    const router = createAppRouter(createMemoryHistory());
    await router.push(`/projects/${project}/solution-outlines/${outline}`); await router.isReady();
    const reader = { current: vi.fn().mockResolvedValue({ ...item, created_by: project }) };
    const wrapper = mount(ProjectOutlineDetailView, { props: { session: await session("PROJECT_MANAGER"),
      reader: reader as unknown as OutlineReadClient }, global: { plugins: [router] } });
    await flushPromises();
    expect(wrapper.get(`a[href="/projects/${project}/solution-outlines/${outline}/sections/new"]`).text())
      .toContain("创建章节");
    wrapper.unmount();
  });

  it("does not issue requests for an unauthorized project route", async () => {
    const router = createAppRouter(createMemoryHistory());
    await router.push(`/projects/${other}/solution-outlines`); await router.isReady();
    const reader = { list: vi.fn() };
    const wrapper = mount(ProjectOutlineListView, { props: { session: await session(),
      reader: reader as unknown as OutlineReadClient }, global: { plugins: [router] } });
    await flushPromises();
    expect(reader.list).not.toHaveBeenCalled();
    wrapper.unmount();
  });
});
