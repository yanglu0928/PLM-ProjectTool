import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { ProjectReadClient } from "@/modules/project/api/projectReadClient";
import ProjectListView from "./ProjectListView.vue";

const id = "01234567-89ab-4cde-8123-456789abcdef";
const project = { project_id: id, code: "TEST", name: "<script>unsafe</script>", state: "ACTIVE",
  created_at: "2026-09-28T08:30:00Z", etag: '"v0"' };
function response(data: unknown, status = 200, code?: string) {
  return new Response(JSON.stringify(code ? { error: { code, message: "private details" }, trace_id: id }
    : { data, trace_id: id }), { status, headers: { "Content-Type": "application/json" } });
}
async function session(restricted = false, admin = false): Promise<SessionClient> {
  const client = new SessionClient(vi.fn().mockResolvedValue(response({
    user: { user_id: id, username_display: "合成用户" }, deployment_role: admin ? "DEPLOYMENT_ADMIN" : "NONE",
    password_change_required: restricted, authorized_projects: [],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64),
  })) as typeof fetch);
  await client.login("user", "synthetic-only");
  return client;
}
async function view(auth: SessionClient, ...results: Response[]) {
  const fetcher = vi.fn();
  for (const result of results) fetcher.mockResolvedValueOnce(result);
  const router = createAppRouter(createMemoryHistory());
  await router.push("/projects");
  await router.isReady();
  const wrapper = mount(ProjectListView, { props: { session: auth,
    projects: new ProjectReadClient(fetcher as typeof fetch) }, global: { plugins: [router] } });
  await flushPromises();
  return { wrapper, fetcher };
}

describe("ProjectListView", () => {
  afterEach(() => vi.restoreAllMocks());

  it("does not request project data without in-memory identity", async () => {
    const { wrapper, fetcher } = await view(new SessionClient(vi.fn() as typeof fetch));
    expect(wrapper.text()).toContain("尚未读取当前身份");
    expect(wrapper.find('a[href="/login"]').exists()).toBe(true);
    expect(fetcher).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it("does not request projects for a password-change-restricted session", async () => {
    const { wrapper, fetcher } = await view(await session(true));
    expect(wrapper.text()).toContain("须先修改密码");
    expect(fetcher).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it("loads an empty authoritative list even for deployment admin with zero memberships", async () => {
    const { wrapper, fetcher } = await view(await session(false, true),
      response({ items: [], next_cursor: null, has_more: false }));
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(wrapper.text()).toContain("当前没有可查看的项目");
    expect(wrapper.findAll('ul[aria-label="当前授权项目"] li')).toHaveLength(0);
    wrapper.unmount();
  });

  it("shows only the live server list, escaped as text, and refreshes explicitly", async () => {
    const { wrapper, fetcher } = await view(await session(),
      response({ items: [project], next_cursor: null, has_more: false }),
      response({ items: [], next_cursor: null, has_more: false }));
    expect(wrapper.text()).toContain(project.name);
    expect(wrapper.find("script").exists()).toBe(false);
    expect(wrapper.get('ul[aria-label="当前授权项目"]')).toBeTruthy();
    await wrapper.get("button").trigger("click");
    await flushPromises();
    expect(wrapper.text()).not.toContain(project.name);
    expect(wrapper.text()).toContain("当前没有可查看的项目");
    expect(fetcher).toHaveBeenCalledTimes(2);
    wrapper.unmount();
  });

  it.each([[401, "AUTH_SESSION_EXPIRED", "会话已失效"],
    [403, "LICENSE_OPERATION_DENIED", "当前许可不允许查看项目"],
    [503, "SYSTEM_UNAVAILABLE", "暂时无法读取项目"]] as const)(
    "shows a safe error and hides old project content after %s %s", async (status, code, message) => {
      const { wrapper, fetcher } = await view(await session(),
        response({ items: [project], next_cursor: null, has_more: false }), failure(status, code));
      expect(wrapper.text()).toContain(project.name);
      await wrapper.get("button").trigger("click");
      await flushPromises();
      expect(wrapper.get('[role="alert"]').text()).toContain(message);
      expect(wrapper.text()).not.toContain(project.name);
      expect(wrapper.html()).not.toContain("private details");
      expect(fetcher).toHaveBeenCalledTimes(2);
      wrapper.unmount();
    });
});

function failure(status: number, code: string): Response {
  return response(null, status, code);
}
