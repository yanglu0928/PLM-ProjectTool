import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { HandoverReadClient } from "@/modules/handover/api/handoverReadClient";
import ProjectHandoverListView from "./ProjectHandoverListView.vue";

const project = "01234567-89ab-4cde-8123-456789abcdef"; const other = "11234567-89ab-4cde-8123-456789abcdef";
const analysis = "21234567-89ab-4cde-8123-456789abcdef"; const actor = "31234567-89ab-4cde-8123-456789abcdef";
const trace = "41234567-89ab-4cde-8123-456789abcdef"; const token = `${"A".repeat(24)}.${"B".repeat(43)}`;
const item = { handover_analysis_id: analysis, project_id: project, analysis_purpose: "系统交接差异分析",
  source_set_ref: `sha256:${"a".repeat(64)}`, state: "ACTIVE", current_approved_version_ref: null, created_by: actor,
  created_at: "2026-10-05T12:00:00Z", updated_at: "2026-10-05T12:00:00Z", etag: '"v0"' };
function response(data: unknown) { return new Response(JSON.stringify({ data, trace_id: trace }),
  { headers: { "Content-Type": "application/json" } }); }
function failure(status: number, code: string) { return new Response(JSON.stringify({ error: { code, message: "private" }, trace_id: trace }),
  { status, headers: { "Content-Type": "application/json" } }); }
async function session(restricted = false) { const api = new SessionClient(vi.fn().mockResolvedValue(response({
  user: { user_id: actor, username_display: "合成用户" }, deployment_role: "NONE", password_change_required: restricted,
  authorized_projects: restricted ? [] : [{ project_id: project, name: "合成项目", role: "PROJECT_MANAGER" }],
  absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "a".repeat(64),
})) as typeof fetch); await api.login("user", "synthetic-only"); return api; }
async function view(auth: SessionClient, fetcher: typeof fetch) { const router = createAppRouter(createMemoryHistory());
  await router.push(`/projects/${project}/handover`); await router.isReady();
  const wrapper = mount(ProjectHandoverListView, { props: { session: auth, handover: new HandoverReadClient(fetcher) },
    global: { plugins: [router] } }); await flushPromises(); return { wrapper, router }; }

describe("ProjectHandoverListView", () => {
  afterEach(() => vi.restoreAllMocks());
  it("does not read without identity or before password change", async () => { const fetcher = vi.fn();
    const absent = await view(new SessionClient(fetcher as typeof fetch), fetcher as typeof fetch);
    expect(absent.wrapper.text()).toContain("尚未读取当前身份"); absent.wrapper.unmount();
    const restricted = await view(await session(true), fetcher as typeof fetch);
    expect(restricted.wrapper.text()).toContain("须先修改密码"); expect(fetcher).not.toHaveBeenCalled(); restricted.wrapper.unmount(); });
  it("shows safe summaries, non-formal warning and detail navigation", async () => { const fetcher = vi.fn().mockResolvedValue(response({
    items: [item], next_cursor: null, has_more: false }));
    const { wrapper } = await view(await session(), fetcher as typeof fetch);
    expect(wrapper.text()).toContain("候选问题不等于已确认事实"); expect(wrapper.text()).toContain("系统交接差异分析");
    expect(wrapper.text()).toContain("尚未形成"); expect(wrapper.find("form").exists()).toBe(false);
    expect(wrapper.get(`a[href="/projects/${project}/handover/${analysis}"]`).text()).toContain("原文位置"); wrapper.unmount(); });
  it("appends a distinct page and refreshes from the first page", async () => { const older = { ...item,
    handover_analysis_id: actor, analysis_purpose: "旧分析", created_at: "2026-10-05T11:00:00Z",
    updated_at: "2026-10-05T11:00:00Z" };
    const fetcher = vi.fn().mockResolvedValueOnce(response({ items: [item], next_cursor: token, has_more: true }))
      .mockResolvedValueOnce(response({ items: [older], next_cursor: null, has_more: false }))
      .mockResolvedValueOnce(response({ items: [older], next_cursor: null, has_more: false }));
    const { wrapper } = await view(await session(), fetcher as typeof fetch);
    await wrapper.findAll("button").at(-1)!.trigger("click"); await flushPromises(); expect(wrapper.text()).toContain("旧分析");
    await wrapper.findAll("button")[0]!.trigger("click"); await flushPromises(); expect(wrapper.text()).not.toContain("系统交接差异分析");
    expect(fetcher.mock.calls[1][0]).toContain(`cursor=${token}`); wrapper.unmount(); });
  it("clears prior summaries when a later page is denied", async () => { const fetcher = vi.fn()
    .mockResolvedValueOnce(response({ items: [item], next_cursor: token, has_more: true }))
    .mockResolvedValueOnce(failure(404, "RESOURCE_NOT_FOUND")); const { wrapper } = await view(await session(), fetcher as typeof fetch);
    await wrapper.findAll("button").at(-1)!.trigger("click"); await flushPromises();
    expect(wrapper.get("[role=alert]").text()).toContain("无权查看"); expect(wrapper.text()).not.toContain("系统交接差异分析"); wrapper.unmount(); });
  it("discards a late prior-project response", async () => { let resolve!: (value: Response) => void;
    const fetcher = vi.fn().mockImplementationOnce(() => new Promise<Response>(done => { resolve = done; }))
      .mockResolvedValueOnce(response({ items: [], next_cursor: null, has_more: false }));
    const { wrapper, router } = await view(await session(), fetcher as typeof fetch);
    await router.push(`/projects/${other}/handover`); await flushPromises();
    resolve(response({ items: [item], next_cursor: null, has_more: false })); await flushPromises();
    expect(wrapper.text()).not.toContain("系统交接差异分析"); expect(fetcher.mock.calls[1][0]).toContain(other); wrapper.unmount(); });
});
