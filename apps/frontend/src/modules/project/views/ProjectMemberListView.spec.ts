import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { ProjectMemberReadClient } from "@/modules/project/api/projectMemberReadClient";
import ProjectMemberListView from "./ProjectMemberListView.vue";

const id = "01234567-89ab-4cde-8123-456789abcdef";
const otherId = "11234567-89ab-4cde-8123-456789abcdef";
const memberId = "21234567-89ab-4cde-8123-456789abcdef";
const cursor = `${"a".repeat(40)}.${"b".repeat(43)}`;
const entry = { member_id: memberId, user: { user_id: "31234567-89ab-4cde-8123-456789abcdef", display_name: "成员甲" },
  role: "PROJECT_MANAGER", department: { department_id: "41234567-89ab-4cde-8123-456789abcdef", name: "研发部" },
  state: "ACTIVE", effective_at: "2026-09-28T08:30:00Z", ended_at: null, etag: '"v0"' };
function response(data: unknown): Response {
  return new Response(JSON.stringify({ data, trace_id: id }), { status: 200,
    headers: { "Content-Type": "application/json" } });
}
function failure(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: "private details" }, trace_id: id }),
    { status, headers: { "Content-Type": "application/json" } });
}
async function session(restricted = false): Promise<SessionClient> {
  const api = new SessionClient(vi.fn().mockResolvedValue(response({
    user: { user_id: id, username_display: "合成用户" }, deployment_role: "NONE",
    password_change_required: restricted, authorized_projects: [],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64),
  })) as typeof fetch);
  await api.login("user", "synthetic-only");
  return api;
}
async function view(auth: SessionClient, path: string, fetcher: typeof fetch) {
  const router = createAppRouter(createMemoryHistory());
  await router.push(path);
  await router.isReady();
  const wrapper = mount(ProjectMemberListView, {
    props: { session: auth, members: new ProjectMemberReadClient(fetcher) }, global: { plugins: [router] },
  });
  await flushPromises();
  return { wrapper, router };
}

describe("ProjectMemberListView", () => {
  afterEach(() => vi.restoreAllMocks());

  it("does not request members without current identity or with required password change", async () => {
    const fetcher = vi.fn();
    const absent = await view(new SessionClient(fetcher as typeof fetch), `/projects/${id}/members`, fetcher as typeof fetch);
    expect(absent.wrapper.text()).toContain("尚未读取当前身份");
    absent.wrapper.unmount();
    const restricted = await view(await session(true), `/projects/${id}/members`, fetcher as typeof fetch);
    expect(restricted.wrapper.text()).toContain("须先修改密码");
    expect(fetcher).not.toHaveBeenCalled();
    restricted.wrapper.unmount();
  });

  it("reads member history only through server even when Session summary has no projects", async () => {
    const fetcher = vi.fn().mockResolvedValue(response({ items: [{ ...entry,
      user: { ...entry.user, display_name: "<img src=x>" } }], next_cursor: null, has_more: false }));
    const { wrapper } = await view(await session(), `/projects/${id}/members`, fetcher as typeof fetch);
    expect(wrapper.text()).toContain("<img src=x>");
    expect(wrapper.find("img").exists()).toBe(false);
    expect(wrapper.text()).toContain("项目负责人");
    expect(fetcher.mock.calls[0]?.[0]).toBe(`/api/v1/projects/${id}/members?page_size=50`);
    wrapper.unmount();
  });

  it("shows empty authorized history without inventing members", async () => {
    const fetcher = vi.fn().mockResolvedValue(response({ items: [], next_cursor: null, has_more: false }));
    const { wrapper } = await view(await session(), `/projects/${id}/members`, fetcher as typeof fetch);
    expect(wrapper.text()).toContain("没有成员记录");
    expect(wrapper.find('ul[aria-label="项目成员历史"]').exists()).toBe(false);
    wrapper.unmount();
  });

  it("loads next page with opaque cursor and appends only server-projected items", async () => {
    const second = { ...entry, member_id: "51234567-89ab-4cde-8123-456789abcdef", user: { ...entry.user, display_name: "成员乙" } };
    const fetcher = vi.fn().mockResolvedValueOnce(response({ items: [entry], next_cursor: cursor, has_more: true }))
      .mockResolvedValueOnce(response({ items: [second], next_cursor: null, has_more: false }));
    const { wrapper } = await view(await session(), `/projects/${id}/members`, fetcher as typeof fetch);
    await wrapper.get("button:last-of-type").trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("成员甲");
    expect(wrapper.text()).toContain("成员乙");
    expect(fetcher.mock.calls[1]?.[0]).toBe(`/api/v1/projects/${id}/members?page_size=50&cursor=${cursor}`);
    expect(wrapper.findAll('ul[aria-label="项目成员历史"] li')).toHaveLength(2);
    wrapper.unmount();
  });

  it("clears prior members and cursor when a later page is rejected", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response({ items: [entry], next_cursor: cursor, has_more: true }))
      .mockResolvedValueOnce(failure(404, "RESOURCE_NOT_FOUND"));
    const { wrapper } = await view(await session(), `/projects/${id}/members`, fetcher as typeof fetch);
    await wrapper.get("button:last-of-type").trigger("click");
    await flushPromises();
    expect(wrapper.get('[role="alert"]').text()).toContain("不存在或无权");
    expect(wrapper.text()).not.toContain("成员甲");
    expect(wrapper.html()).not.toContain("private details");
    expect(wrapper.find('ul[aria-label="项目成员历史"]').exists()).toBe(false);
    wrapper.unmount();
  });

  it("rejects an unsafe direct project path before network", async () => {
    const fetcher = vi.fn();
    const { wrapper } = await view(await session(), "/projects/bad/members", fetcher as typeof fetch);
    expect(wrapper.get('[role="alert"]').text()).toContain("项目标识无效");
    expect(fetcher).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it("drops old project members after navigation and ignores a late old response", async () => {
    let resolveOld!: (value: Response) => void;
    const fetcher = vi.fn().mockImplementationOnce(() => new Promise<Response>((resolve) => { resolveOld = resolve; }))
      .mockResolvedValueOnce(response({ items: [], next_cursor: null, has_more: false }));
    const { wrapper, router } = await view(await session(), `/projects/${id}/members`, fetcher as typeof fetch);
    await router.push(`/projects/${otherId}/members`);
    await flushPromises();
    resolveOld(response({ items: [entry], next_cursor: null, has_more: false }));
    await flushPromises();
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(fetcher.mock.calls[1]?.[0]).toBe(`/api/v1/projects/${otherId}/members?page_size=50`);
    expect(wrapper.text()).not.toContain("成员甲");
    expect(wrapper.text()).toContain("没有成员记录");
    wrapper.unmount();
  });

  it("clears all members when another page repeats an existing member", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response({ items: [entry], next_cursor: cursor, has_more: true }))
      .mockResolvedValueOnce(response({ items: [entry], next_cursor: null, has_more: false }));
    const { wrapper } = await view(await session(), `/projects/${id}/members`, fetcher as typeof fetch);
    await wrapper.get("button:last-of-type").trigger("click");
    await flushPromises();
    expect(wrapper.get('[role="alert"]').text()).toContain("暂时无法读取");
    expect(wrapper.text()).not.toContain("成员甲");
    wrapper.unmount();
  });
});
