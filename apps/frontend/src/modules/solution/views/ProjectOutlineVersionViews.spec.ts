import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { OutlineVersionReadClient } from "@/modules/solution/api/outlineVersionReadClient";
import ProjectOutlineVersionListView from "./ProjectOutlineVersionListView.vue";
import ProjectOutlineVersionDetailView from "./ProjectOutlineVersionDetailView.vue";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const otherProject = "02234567-89ab-4cde-8123-456789abcdef";
const outline = "11234567-89ab-4cde-8123-456789abcdef";
const version = "21234567-89ab-4cde-8123-456789abcdef";
const older = "31234567-89ab-4cde-8123-456789abcdef";
const section = "41234567-89ab-4cde-8123-456789abcdef";
const item = { solution_outline_version_id: version, solution_outline_id: outline,
  project_id: project, version_no: 2, version_state: "DRAFT", content_fingerprint: "a".repeat(64),
  declared_section_count: 1, declared_requirement_count: 1, declared_reference_count: 2,
  missing_declaration_count: 1, conflict_declaration_count: 0,
  supersedes_version_ref: older, review_ref: null, review_round_ref: null,
  created_by: project, created_at: "2026-10-09T00:00:00Z" };
const detail = { ...item, section_ids: [section],
  requirement_refs: [{ requirement_id: older, requirement_version_id: version }],
  reference_refs: [
    { scope: "PROJECT", reference_solution_id: older, reference_version_id: version },
    { scope: "GLOBAL", reference_solution_id: version, reference_version_id: older },
  ], missing_declarations: [{ description: "资料待补" }], conflict_declarations: [] };
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

describe("OutlineVersion history views", () => {
  afterEach(() => vi.restoreAllMocks());

  it("lists ordered metadata and opens exact detail for a project member", async () => {
    const router = createAppRouter(createMemoryHistory());
    expect(router.resolve(`/projects/${project}/solution-outlines/${outline}/versions`).name)
      .toBe("project-outline-versions");
    expect(router.resolve(`/projects/${project}/solution-outlines/${outline}/versions/${version}`).name)
      .toBe("project-outline-version-detail");
    await router.push(`/projects/${project}/solution-outlines/${outline}/versions`); await router.isReady();
    const reader = { list: vi.fn().mockResolvedValueOnce({ items: [item], next_cursor: "cursor", has_more: true })
      .mockResolvedValueOnce({ items: [{ ...item, solution_outline_version_id: older,
        version_no: 1, supersedes_version_ref: null }], next_cursor: null, has_more: false }) };
    const wrapper = mount(ProjectOutlineVersionListView, { props: { session: await session(),
      reader: reader as unknown as OutlineVersionReadClient }, global: { plugins: [router] } });
    await flushPromises();
    expect(reader.list).toHaveBeenCalledWith(project, outline, 50, null);
    expect(wrapper.text()).toContain("历史引用不证明来源目前仍合格");
    expect(wrapper.text()).toContain("版本 2 · DRAFT");
    expect(wrapper.get(`a[href="/projects/${project}/solution-outlines/${outline}/versions/${version}"]`)
      .text()).toContain("查看固定版本详情");
    await wrapper.findAll("button").find(button => button.text() === "加载更早版本")!.trigger("click");
    await flushPromises();
    expect(reader.list).toHaveBeenCalledWith(project, outline, 50, "cursor");
    expect(wrapper.text()).toContain("版本 1 · DRAFT");
    wrapper.unmount();
  });

  it("renders fixed refs and declarations but not GLOBAL current candidate links", async () => {
    const router = createAppRouter(createMemoryHistory());
    await router.push(`/projects/${project}/solution-outlines/${outline}/versions/${version}`);
    await router.isReady();
    const reader = { detail: vi.fn().mockResolvedValue(detail) };
    const wrapper = mount(ProjectOutlineVersionDetailView, { props: { session: await session(),
      reader: reader as unknown as OutlineVersionReadClient }, global: { plugins: [router] } });
    await flushPromises();
    expect(reader.detail).toHaveBeenCalledWith(project, outline, version);
    expect(wrapper.text()).toContain("历史固定引用");
    expect(wrapper.text()).toContain("GLOBAL 固定参考");
    expect(wrapper.text()).toContain("当前可用性未验证");
    expect(wrapper.text()).toContain("资料待补");
    expect(wrapper.get(`a[href="/projects/${project}/solution-sections/${section}"]`).text())
      .toContain(section);
    expect(wrapper.find(`a[href="/global/reference-solutions/${version}"]`).exists()).toBe(false);
    wrapper.unmount();
  });

  it("shows empty state and blocks reads outside the current project", async () => {
    const router = createAppRouter(createMemoryHistory());
    await router.push(`/projects/${project}/solution-outlines/${outline}/versions`); await router.isReady();
    const reader = { list: vi.fn().mockResolvedValue({ items: [], next_cursor: null, has_more: false }) };
    const wrapper = mount(ProjectOutlineVersionListView, { props: { session: await session(),
      reader: reader as unknown as OutlineVersionReadClient }, global: { plugins: [router] } });
    await flushPromises();
    expect(wrapper.text()).toContain("尚无可见方案版本");
    await router.push(`/projects/${otherProject}/solution-outlines/${outline}/versions`);
    await flushPromises();
    expect(reader.list).toHaveBeenCalledTimes(1);
    expect(wrapper.text()).not.toContain("尚无可见方案版本");
    wrapper.unmount();
  });

  it("does not request a detail for an unauthorized project", async () => {
    const router = createAppRouter(createMemoryHistory());
    await router.push(`/projects/${otherProject}/solution-outlines/${outline}/versions/${version}`);
    await router.isReady();
    const reader = { detail: vi.fn() };
    const wrapper = mount(ProjectOutlineVersionDetailView, { props: { session: await session(),
      reader: reader as unknown as OutlineVersionReadClient }, global: { plugins: [router] } });
    await flushPromises(); expect(reader.detail).not.toHaveBeenCalled(); wrapper.unmount();
  });
});
