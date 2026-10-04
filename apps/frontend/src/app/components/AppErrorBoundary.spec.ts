import { mount } from "@vue/test-utils";
import { defineComponent, h, nextTick } from "vue";
import { afterEach, describe, expect, it, vi } from "vitest";

import AppErrorBoundary from "@/app/components/AppErrorBoundary.vue";

describe("AppErrorBoundary", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows a safe fallback without rendering exception details", async () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    const BrokenChild = defineComponent({
      setup() {
        throw new Error("secret stack and customer path");
      },
      render: () => h("div"),
    });

    const wrapper = mount(AppErrorBoundary, {
      slots: {
        default: BrokenChild,
      },
    });
    await nextTick();

    expect(wrapper.get('[role="alert"]').text()).toContain("页面暂时无法显示");
    expect(wrapper.text()).not.toContain("secret stack");
    expect(wrapper.text()).not.toContain("customer path");
  });
});
