import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { SectionReadClient } from "@/modules/solution/api/sectionReadClient";
import ProjectSectionListView from "./ProjectSectionListView.vue";
import ProjectSectionDetailView from "./ProjectSectionDetailView.vue";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const other = "02234567-89ab-4cde-8123-456789abcdef";
const outline = "11234567-89ab-4cde-8123-456789abcdef";
const section = "21234567-89ab-4cde-8123-456789abcdef";
const second = "31234567-89ab-4cde-8123-456789abcdef";
const token = `${"a".repeat(40)}.${"b".repeat(43)}`;
const item = { solution_section_id: section, solution_outline_id: outline, project_id: project,
  section_key: "业务范围", section_state: "ACTIVE", current_approved_version_ref: null,
  created_at: "2026-10-09T00:00:00Z", etag: '"v0"' };
const secondItem = { ...item, solution_section_id: second, section_key: "目标架构" };
function success(data: unknown): Response {
  return new Response(JSON.stringify({ data, trace_id: project }), { status: 200,
    headers: { "Content-Type": "application/json" } });
}
async function session(): Promise<SessionClient> {
  const api = new SessionClient(vi.fn().mockResolvedValue(success({
    user: { user_id: project, username_display: "合成用户" }, deployment_role: "NONE",
    password_change_required: false,
    authorized_projects: [{ project_id: project, name: "项目", role: "CUSTOMER_MEMBER" }],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64),
  })) as typeof fetch);
  await api.login("user", "synthetic-only"); return api;
}

describe("PROJECT Section read pages", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows whole-project list, safe status and parent/detail navigation", async () => {
    const router = createAppRouter(createMemoryHistory());
    expect(router.resolve(`/projects/${project}/solution-sections`).name).toBe("project-sections");
    expect(router.resolve(`/projects/${project}/solution-sections/${section}`).name)
      .toBe("project-section-detail");
    await router.push(`/projects/${project}/solution-sections`); await router.isReady();
    const reader = { list: vi.fn().mockResolvedValueOnce({ items: [item], next_cursor: token, has_more: true })
      .mockResolvedValueOnce({ items: [secondItem], next_cursor: null, has_more: false }) };
    const wrapper = mount(ProjectSectionListView, { props: { session: await session(),
      reader: reader as unknown as SectionReadClient }, global: { plugins: [router] } });
    await flushPromises();
    expect(reader.list).toHaveBeenCalledWith(project, 50, null);
    expect(wrapper.text()).toContain("整个项目的章节身份");
    expect(wrapper.text()).toContain("尚无已审批版本");
    expect(wrapper.get(`a[href="/projects/${project}/solution-outlines/${outline}"]`).text())
      .toContain("所属目录");
    expect(wrapper.get(`a[href="/projects/${project}/solution-sections/${section}"]`).text())
      .toContain("章节详情");
    await wrapper.findAll("button").find(button => button.text() === "加载更多章节")!.trigger("click");
    await flushPromises();
    expect(reader.list).toHaveBeenCalledWith(project, 50, token);
    expect(wrapper.text()).toContain("目标架构");
    wrapper.unmount();
  });

  it("shows one identity without claiming approval or formal delivery", async () => {
    const router = createAppRouter(createMemoryHistory());
    await router.push(`/projects/${project}/solution-sections/${section}`); await router.isReady();
    const reader = { current: vi.fn().mockResolvedValue({ ...item, created_by: project }) };
    const wrapper = mount(ProjectSectionDetailView, { props: { session: await session(),
      reader: reader as unknown as SectionReadClient }, global: { plugins: [router] } });
    await flushPromises();
    expect(reader.current).toHaveBeenCalledWith(project, section);
    expect(wrapper.text()).toContain("尚无已审批版本");
    expect(wrapper.text()).toContain("不得据此判断方案已交付");
    expect(wrapper.get(`a[href="/projects/${project}/solution-sections"]`).text()).toContain("返回方案章节");
    wrapper.unmount();
  });

  it("does not request unauthorized project list or detail", async () => {
    const router = createAppRouter(createMemoryHistory());
    await router.push(`/projects/${other}/solution-sections`); await router.isReady();
    const identity = await session();
    const listReader = { list: vi.fn() };
    const list = mount(ProjectSectionListView, { props: { session: identity,
      reader: listReader as unknown as SectionReadClient }, global: { plugins: [router] } });
    await flushPromises();
    expect(listReader.list).not.toHaveBeenCalled();
    list.unmount();
    await router.push(`/projects/${other}/solution-sections/${section}`);
    const detailReader = { current: vi.fn() };
    const detail = mount(ProjectSectionDetailView, { props: { session: identity,
      reader: detailReader as unknown as SectionReadClient }, global: { plugins: [router] } });
    await flushPromises();
    expect(detailReader.current).not.toHaveBeenCalled();
    detail.unmount();
  });

  it("rejects a duplicate next page without displaying it", async () => {
    const router = createAppRouter(createMemoryHistory());
    await router.push(`/projects/${project}/solution-sections`); await router.isReady();
    const reader = { list: vi.fn().mockResolvedValueOnce({ items: [item], next_cursor: token, has_more: true })
      .mockResolvedValueOnce({ items: [item], next_cursor: null, has_more: false }) };
    const wrapper = mount(ProjectSectionListView, { props: { session: await session(),
      reader: reader as unknown as SectionReadClient }, global: { plugins: [router] } });
    await flushPromises();
    await wrapper.findAll("button").find(button => button.text() === "加载更多章节")!.trigger("click");
    await flushPromises();
    expect(wrapper.find("[role=alert]").exists()).toBe(true);
    expect(wrapper.findAll("ol li")).toHaveLength(0);
    wrapper.unmount();
  });
});
