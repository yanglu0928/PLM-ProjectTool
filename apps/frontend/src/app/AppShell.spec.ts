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

  it("renders the foundation home without unimplemented business navigation", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(readyResponse()));
    const router = createAppRouter(createMemoryHistory());
    await router.push("/");
    await router.isReady();

    const wrapper = mount(AppShell, { global: { plugins: [router] } });
    await flushPromises();

    expect(wrapper.get("h1").text()).toContain("项目实施信息");
    expect(wrapper.findAll("nav a")).toHaveLength(2);
    expect(wrapper.get('nav[aria-label="主导航"]').classes()).toContain("primary-nav");
    expect(wrapper.get('nav a[href="/login"]').text()).toBe("账户与登录");
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
});
