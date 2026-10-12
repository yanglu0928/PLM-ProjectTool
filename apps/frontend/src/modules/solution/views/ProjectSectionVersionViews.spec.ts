import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { SectionVersionReadClient } from "@/modules/solution/api/sectionVersionReadClient";
import ProjectSectionVersionListView from "./ProjectSectionVersionListView.vue";
import ProjectSectionVersionDetailView from "./ProjectSectionVersionDetailView.vue";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const otherProject = "02234567-89ab-4cde-8123-456789abcdef";
const section = "11234567-89ab-4cde-8123-456789abcdef";
const version = "21234567-89ab-4cde-8123-456789abcdef";
const older = "31234567-89ab-4cde-8123-456789abcdef";
const requirement = "41234567-89ab-4cde-8123-456789abcdef";
const evidence = "51234567-89ab-4cde-8123-456789abcdef";
const item = { solution_section_version_id: version, solution_section_id: section,
  project_id: project, version_no: 2, version_state: "DRAFT", title: "方案章节草案",
  content_fingerprint: "a".repeat(64), declared_requirement_count: 1,
  declared_evidence_count: 1, assumption_count: 1, exclusion_count: 0,
  supersedes_version_ref: older, review_ref: null, review_round_ref: null,
  created_by: project, created_at: "2026-10-12T00:00:00Z" };
const detail = { ...item, content_document_version_ref: older, content_artifact_ref: null,
  requirement_refs: [{ requirement_id: requirement, requirement_version_id: older }],
  evidence_ids: [evidence], assumptions: [{ note: "资料待补" }], exclusions: [] };
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

describe("SectionVersion history views", () => {
  afterEach(() => vi.restoreAllMocks());

  it("lists paginated metadata and links to exact detail for a project member", async () => {
    const router = createAppRouter(createMemoryHistory());
    expect(router.resolve(`/projects/${project}/solution-sections/${section}/versions`).name)
      .toBe("project-section-versions");
    expect(router.resolve(`/projects/${project}/solution-sections/${section}/versions/${version}`).name)
      .toBe("project-section-version-detail");
    await router.push(`/projects/${project}/solution-sections/${section}/versions`); await router.isReady();
    const reader = { list: vi.fn().mockResolvedValueOnce({ items: [item], next_cursor: "cursor", has_more: true })
      .mockResolvedValueOnce({ items: [{ ...item, solution_section_version_id: older,
        version_no: 1, supersedes_version_ref: null }], next_cursor: null, has_more: false }) };
    const wrapper = mount(ProjectSectionVersionListView, { props: { session: await session(),
      reader: reader as unknown as SectionVersionReadClient }, global: { plugins: [router] } });
    await flushPromises();
    expect(reader.list).toHaveBeenCalledWith(project, section, 50, null);
    expect(wrapper.text()).toContain("历史来源不证明目前仍合格");
    expect(wrapper.text()).toContain("版本 2 · DRAFT · 方案章节草案");
    expect(wrapper.get(`a[href="/projects/${project}/solution-sections/${section}/versions/${version}"]`)
      .text()).toContain("查看固定版本详情");
    await wrapper.findAll("button").find(button => button.text() === "加载更早版本")!.trigger("click");
    await flushPromises();
    expect(reader.list).toHaveBeenCalledWith(project, section, 50, "cursor");
    expect(wrapper.text()).toContain("版本 1 · DRAFT"); wrapper.unmount();
  });

  it("renders fixed refs and declarations without invented document locator", async () => {
    const router = createAppRouter(createMemoryHistory());
    await router.push(`/projects/${project}/solution-sections/${section}/versions/${version}`);
    await router.isReady();
    const reader = { detail: vi.fn().mockResolvedValue(detail) };
    const wrapper = mount(ProjectSectionVersionDetailView, { props: { session: await session(),
      reader: reader as unknown as SectionVersionReadClient }, global: { plugins: [router] } });
    await flushPromises();
    expect(reader.detail).toHaveBeenCalledWith(project, section, version);
    expect(wrapper.text()).toContain("历史固定引用");
    expect(wrapper.text()).toContain("资料待补");
    expect(wrapper.text()).toContain("不能从固定 UUID 推断下载地址");
    expect(wrapper.get(`a[href="/projects/${project}/requirements/${requirement}"]`).text())
      .toContain(requirement);
    expect(wrapper.find(`a[href="/projects/${project}/documents/${older}"]`).exists()).toBe(false);
    wrapper.unmount();
  });

  it("blocks reads for another project and clears old pages on route change", async () => {
    const router = createAppRouter(createMemoryHistory());
    await router.push(`/projects/${project}/solution-sections/${section}/versions`); await router.isReady();
    const reader = { list: vi.fn().mockResolvedValue({ items: [item], next_cursor: null, has_more: false }) };
    const wrapper = mount(ProjectSectionVersionListView, { props: { session: await session(),
      reader: reader as unknown as SectionVersionReadClient }, global: { plugins: [router] } });
    await flushPromises(); expect(wrapper.text()).toContain("方案章节草案");
    await router.push(`/projects/${otherProject}/solution-sections/${section}/versions`);
    await flushPromises();
    expect(reader.list).toHaveBeenCalledTimes(1);
    expect(wrapper.text()).not.toContain("方案章节草案"); wrapper.unmount();
  });

  it("does not request a detail outside the current project", async () => {
    const router = createAppRouter(createMemoryHistory());
    await router.push(`/projects/${otherProject}/solution-sections/${section}/versions/${version}`);
    await router.isReady();
    const reader = { detail: vi.fn() };
    const wrapper = mount(ProjectSectionVersionDetailView, { props: { session: await session(),
      reader: reader as unknown as SectionVersionReadClient }, global: { plugins: [router] } });
    await flushPromises(); expect(reader.detail).not.toHaveBeenCalled(); wrapper.unmount();
  });
});
