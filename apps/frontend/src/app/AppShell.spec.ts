import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import AppShell from "@/app/AppShell.vue";
import { createAppRouter } from "@/app/router";

function readyResponse(): Response {
  return {
    ok: true,
    json: vi.fn().mockResolvedValue({ status: "UP" }),
  } as unknown as Response;
}

describe("AppShell", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the foundation home with implemented navigation", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(readyResponse()));
    const router = createAppRouter(createMemoryHistory());
    await router.push("/");
    await router.isReady();

    const wrapper = mount(AppShell, { global: { plugins: [router] } });
    await flushPromises();

    expect(wrapper.get("h1").text()).toContain("项目实施信息");
    expect(wrapper.findAll("nav a")).toHaveLength(7);
    expect(wrapper.get('nav[aria-label="主导航"]').classes()).toContain("primary-nav");
    expect(wrapper.get('nav a[href="/login"]').text()).toBe("账户与登录");
    expect(wrapper.get('nav a[href="/projects"]').text()).toBe("我的项目");
    expect(wrapper.get('nav a[href="/admin/evidence"]').text()).toBe("全局证据");
    expect(wrapper.text()).not.toContain("客户项目列表");
  });

  it("renders a safe 404 for an unknown route", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(readyResponse()));
    const router = createAppRouter(createMemoryHistory());
    await router.push("/not-implemented");
    await router.isReady();

    const wrapper = mount(AppShell, { global: { plugins: [router] } });
    await flushPromises();

    expect(wrapper.get("h1").text()).toBe("没有找到这个页面");
    expect(wrapper.text()).not.toContain("/not-implemented");
  });

  it("mounts the login page through the real route without automatic login", async () => {
    const fetcher = vi.fn().mockResolvedValue(readyResponse());
    vi.stubGlobal("fetch", fetcher);
    const router = createAppRouter(createMemoryHistory());
    await router.push("/login");
    await router.isReady();
    const wrapper = mount(AppShell, { global: { plugins: [router] } });
    await flushPromises();
    expect(wrapper.get("h1").text()).toBe("登录项目实施辅助工具");
    expect(fetcher.mock.calls.every(([url]) => url === "/health/ready")).toBe(true);
    expect(wrapper.get('input[name="password"]').attributes("type")).toBe("password");
  });

  it("keeps the same in-memory session across routes but not a new app instance", async () => {
    const id = "01234567-89ab-4cde-8123-456789abcdef";
    const auth = new Response(JSON.stringify({ data: {
      user: { user_id: id, username_display: "Synthetic Member" }, deployment_role: "NONE",
      password_change_required: true, authorized_projects: [],
      absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
      csrf_token: "a".repeat(64),
    }, trace_id: id }), { headers: { "Content-Type": "application/json" } });
    const fetcher = vi.fn((url: string) => Promise.resolve(url === "/health/ready" ? readyResponse() : auth));
    vi.stubGlobal("fetch", fetcher);
    const router = createAppRouter(createMemoryHistory());
    await router.push("/login");
    await router.isReady();
    const wrapper = mount(AppShell, { global: { plugins: [router] } });
    await flushPromises();
    await wrapper.get('input[name="username"]').setValue("Synthetic Member");
    await wrapper.get('input[name="password"]').setValue("synthetic-only");
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(wrapper.text()).toContain("Synthetic Member");
    expect(wrapper.find('form[aria-label="修改本人密码"]').exists()).toBe(true);
    await router.push("/");
    await flushPromises();
    await router.push("/login");
    await flushPromises();
    expect(wrapper.text()).toContain("Synthetic Member");
    expect(wrapper.find('form[aria-label="修改本人密码"]').exists()).toBe(true);
    expect(fetcher.mock.calls.filter(([url]) => url === "/api/v1/auth/login")).toHaveLength(1);
    expect(fetcher.mock.calls.filter(([url]) => url === "/api/v1/auth/session")).toHaveLength(0);
    wrapper.unmount();

    const freshRouter = createAppRouter(createMemoryHistory());
    await freshRouter.push("/login");
    await freshRouter.isReady();
    const fresh = mount(AppShell, { global: { plugins: [freshRouter] } });
    await flushPromises();
    expect(fresh.find(".auth-identity").exists()).toBe(false);
    expect(fresh.find('form[aria-label="修改本人密码"]').exists()).toBe(false);
    fresh.unmount();
  });

  it("reaches the authorized project list after login without treating the Auth summary as project data", async () => {
    const id = "01234567-89ab-4cde-8123-456789abcdef";
    const auth = new Response(JSON.stringify({ data: {
      user: { user_id: id, username_display: "合成用户" }, deployment_role: "NONE",
      password_change_required: false,
      authorized_projects: [{ project_id: id, name: "摘要项目", role: "PROJECT_MANAGER" }],
      absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
      csrf_token: "a".repeat(64),
    }, trace_id: id }), { headers: { "Content-Type": "application/json" } });
    const list = new Response(JSON.stringify({ data: { items: [], next_cursor: null, has_more: false }, trace_id: id }),
      { headers: { "Content-Type": "application/json" } });
    const fetcher = vi.fn((url: string) => Promise.resolve(url === "/health/ready" ? readyResponse()
      : url === "/api/v1/auth/login" ? auth : list));
    vi.stubGlobal("fetch", fetcher);
    const router = createAppRouter(createMemoryHistory());
    await router.push("/login");
    await router.isReady();
    const wrapper = mount(AppShell, { global: { plugins: [router] } });
    await flushPromises();
    await wrapper.get('input[name="username"]').setValue("user");
    await wrapper.get('input[name="password"]').setValue("synthetic-only");
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    await router.push("/projects");
    await flushPromises();
    expect(wrapper.get("h1").text()).toBe("我的项目");
    expect(wrapper.text()).toContain("当前没有可查看的项目");
    expect(wrapper.text()).not.toContain("摘要项目");
    expect(fetcher.mock.calls.filter(([url]) => url === "/api/v1/projects")).toHaveLength(1);
    wrapper.unmount();
  });
});
