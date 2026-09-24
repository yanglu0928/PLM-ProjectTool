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
    expect(wrapper.findAll("nav a")).toHaveLength(1);
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
});
