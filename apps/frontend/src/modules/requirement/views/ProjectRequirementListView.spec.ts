import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { RequirementReadClient, RequirementReadError, type RequirementView } from "@/modules/requirement/api/requirementReadClient";
import ProjectRequirementListView from "./ProjectRequirementListView.vue";

const project = "01234567-89ab-4cde-8123-456789abcdef"; const other = "11234567-89ab-4cde-8123-456789abcdef";
const requirementId = "21234567-89ab-4cde-8123-456789abcdef"; const actor = "31234567-89ab-4cde-8123-456789abcdef";
const trace = "41234567-89ab-4cde-8123-456789abcdef"; const token = `${"A".repeat(24)}.${"B".repeat(43)}` as never;
const item: RequirementView = { requirement_id: requirementId, project_id: project, requirement_code: "REQ-001", state: "ACTIVE",
  current_approved_version_ref: null, created_by: actor, created_at: "2026-10-08T12:00:00Z", updated_by: null,
  updated_at: "2026-10-08T12:00:00Z", etag: '"v0"' };
function response(data: unknown) { return new Response(JSON.stringify({ data, trace_id: trace }), { headers: { "Content-Type": "application/json" } }); }
async function session(restricted = false) { const api = new SessionClient(vi.fn().mockResolvedValue(response({
  user: { user_id: actor, username_display: "合成用户" }, deployment_role: "NONE", password_change_required: restricted,
  authorized_projects: restricted ? [] : [{ project_id: project, name: "合成项目", role: "PROJECT_MANAGER" }],
  absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "a".repeat(64),
})) as typeof fetch); await api.login("user", "synthetic-only"); return api; }
function reader() { return new RequirementReadClient(vi.fn() as typeof fetch); }
async function view(auth: SessionClient, requirements = reader()) { const router = createAppRouter(createMemoryHistory());
  await router.push(`/projects/${project}/requirements`); await router.isReady();
  const wrapper = mount(ProjectRequirementListView, { props: { session: auth, requirements }, global: { plugins: [router] } });
  await flushPromises(); return { wrapper, router, requirements }; }

describe("ProjectRequirementListView", () => {
  afterEach(() => vi.restoreAllMocks());
  it("does not read without identity or before password change", async () => { const requirements = reader(); const list = vi.spyOn(requirements, "listRequirements");
    const absent = await view(new SessionClient(vi.fn() as typeof fetch), requirements); expect(absent.wrapper.text()).toContain("尚未读取当前身份"); absent.wrapper.unmount();
    const restricted = await view(await session(true), requirements); expect(restricted.wrapper.text()).toContain("须先修改密码"); expect(list).not.toHaveBeenCalled(); restricted.wrapper.unmount(); });
  it("shows safe summaries and detail navigation without an edit form", async () => { const requirements = reader();
    vi.spyOn(requirements, "listRequirements").mockResolvedValue({ items: [item], next_cursor: null, has_more: false });
    const { wrapper } = await view(await session(), requirements); expect(wrapper.text()).toContain("AI 建议和来源摘要不是已确认业务事实");
    expect(wrapper.text()).toContain("REQ-001"); expect(wrapper.text()).toContain("尚未形成"); expect(wrapper.find("form").exists()).toBe(false);
    expect(wrapper.get(`a[href="/projects/${project}/requirements/${requirementId}"]`).text()).toContain("原文入口"); wrapper.unmount(); });
  it("appends a distinct page and clears all items after a denied refresh", async () => { const requirements = reader();
    vi.spyOn(requirements, "listRequirements").mockResolvedValueOnce({ items: [item], next_cursor: token, has_more: true })
      .mockResolvedValueOnce({ items: [{ ...item, requirement_id: actor, requirement_code: "REQ-000" }], next_cursor: null, has_more: false })
      .mockRejectedValueOnce(new RequirementReadError("RESOURCE_NOT_FOUND"));
    const { wrapper } = await view(await session(), requirements); await wrapper.findAll("button").at(-1)!.trigger("click"); await flushPromises();
    expect(wrapper.text()).toContain("REQ-000"); await wrapper.findAll("button")[0]!.trigger("click"); await flushPromises();
    expect(wrapper.text()).not.toContain("REQ-001"); expect(wrapper.get("[role=alert]").text()).toContain("无权查看"); wrapper.unmount(); });
  it("discards a late prior-project page", async () => { const requirements = reader(); let finish!: (value: never) => void;
    vi.spyOn(requirements, "listRequirements").mockReturnValueOnce(new Promise(resolve => { finish = resolve as typeof finish; }))
      .mockResolvedValueOnce({ items: [], next_cursor: null, has_more: false });
    const { wrapper, router } = await view(await session(), requirements); await router.push(`/projects/${other}/requirements`); await flushPromises();
    finish({ items: [item], next_cursor: null, has_more: false } as never); await flushPromises(); expect(wrapper.text()).not.toContain("REQ-001");
    expect(requirements.listRequirements).toHaveBeenLastCalledWith(other, 50, null); wrapper.unmount(); });
});
