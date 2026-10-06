import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { SurveyReadClient, SurveyReadError, type SurveyView } from "@/modules/survey/api/surveyReadClient";
import ProjectSurveyListView from "./ProjectSurveyListView.vue";

const project = "01234567-89ab-4cde-8123-456789abcdef"; const other = "11234567-89ab-4cde-8123-456789abcdef";
const surveyId = "21234567-89ab-4cde-8123-456789abcdef"; const actor = "31234567-89ab-4cde-8123-456789abcdef";
const trace = "41234567-89ab-4cde-8123-456789abcdef"; const token = `${"A".repeat(24)}.${"B".repeat(43)}` as never;
const item: SurveyView = { survey_id: surveyId, project_id: project, name: "客户现状调研", state: "ACTIVE",
  current_approved_version_ref: null, created_by: actor, created_at: "2026-10-06T12:00:00Z", updated_by: null,
  updated_at: "2026-10-06T12:00:00Z", etag: '"v0"' };
function response(data: unknown) { return new Response(JSON.stringify({ data, trace_id: trace }),
  { headers: { "Content-Type": "application/json" } }); }
async function session(restricted = false) { const api = new SessionClient(vi.fn().mockResolvedValue(response({
  user: { user_id: actor, username_display: "合成用户" }, deployment_role: "NONE", password_change_required: restricted,
  authorized_projects: restricted ? [] : [{ project_id: project, name: "合成项目", role: "PROJECT_MANAGER" }],
  absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "a".repeat(64),
})) as typeof fetch); await api.login("user", "synthetic-only"); return api; }
function reader() { return new SurveyReadClient(vi.fn() as typeof fetch); }
async function view(auth: SessionClient, surveys = reader()) { const router = createAppRouter(createMemoryHistory());
  await router.push(`/projects/${project}/surveys`); await router.isReady();
  const wrapper = mount(ProjectSurveyListView, { props: { session: auth, surveys }, global: { plugins: [router] } });
  await flushPromises(); return { wrapper, router, surveys }; }

describe("ProjectSurveyListView", () => {
  afterEach(() => vi.restoreAllMocks());
  it("does not read without identity or before password change", async () => { const surveys = reader();
    const list = vi.spyOn(surveys, "listSurveys");
    const absent = await view(new SessionClient(vi.fn() as typeof fetch), surveys);
    expect(absent.wrapper.text()).toContain("尚未读取当前身份"); absent.wrapper.unmount();
    const restricted = await view(await session(true), surveys);
    expect(restricted.wrapper.text()).toContain("须先修改密码"); expect(list).not.toHaveBeenCalled(); restricted.wrapper.unmount(); });

  it("shows safe summaries, actual-record warning and detail navigation", async () => { const surveys = reader();
    vi.spyOn(surveys, "listSurveys").mockResolvedValue({ items: [item], next_cursor: null, has_more: false });
    const { wrapper } = await view(await session(), surveys);
    expect(wrapper.text()).toContain("实际面对面调研记录"); expect(wrapper.text()).toContain("模板和来源说明不等于客户事实");
    expect(wrapper.text()).toContain("客户现状调研"); expect(wrapper.text()).toContain("尚未形成");
    expect(wrapper.find("form").exists()).toBe(false);
    expect(wrapper.get(`a[href="/projects/${project}/surveys/${surveyId}"]`).text()).toContain("问题与来源说明"); wrapper.unmount(); });

  it("appends a distinct page and clears all items after a denied later page", async () => { const surveys = reader();
    const older = { ...item, survey_id: actor, name: "旧调研", updated_at: "2026-10-06T11:00:00Z" };
    vi.spyOn(surveys, "listSurveys").mockResolvedValueOnce({ items: [item], next_cursor: token, has_more: true })
      .mockResolvedValueOnce({ items: [older], next_cursor: null, has_more: false })
      .mockRejectedValueOnce(new SurveyReadError("RESOURCE_NOT_FOUND"));
    const { wrapper } = await view(await session(), surveys);
    await wrapper.findAll("button").at(-1)!.trigger("click"); await flushPromises(); expect(wrapper.text()).toContain("旧调研");
    await wrapper.findAll("button")[0]!.trigger("click"); await flushPromises(); expect(wrapper.text()).not.toContain("客户现状调研");
    expect(wrapper.get("[role=alert]").text()).toContain("无权查看"); wrapper.unmount(); });

  it("discards a late prior-project page", async () => { const surveys = reader(); let finish!: (value: never) => void;
    vi.spyOn(surveys, "listSurveys").mockReturnValueOnce(new Promise(resolve => { finish = resolve as typeof finish; }))
      .mockResolvedValueOnce({ items: [], next_cursor: null, has_more: false });
    const { wrapper, router } = await view(await session(), surveys);
    await router.push(`/projects/${other}/surveys`); await flushPromises();
    finish({ items: [item], next_cursor: null, has_more: false } as never); await flushPromises();
    expect(wrapper.text()).not.toContain("客户现状调研"); expect(surveys.listSurveys).toHaveBeenLastCalledWith(other, 50, null);
    wrapper.unmount(); });
});
