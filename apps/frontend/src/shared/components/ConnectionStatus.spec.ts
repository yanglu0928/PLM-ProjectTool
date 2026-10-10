import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";

import ConnectionStatus from "@/shared/components/ConnectionStatus.vue";

function healthResponse(status: "UP" | "NOT_READY"): Response {
  return {
    ok: status === "UP",
    json: vi.fn().mockResolvedValue({ status }),
  } as unknown as Response;
}

describe("ConnectionStatus", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows ready after the health request succeeds", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(healthResponse("UP")));
    const wrapper = mount(ConnectionStatus);

    await flushPromises();

    expect(wrapper.text()).toContain("服务已就绪");
    expect(wrapper.attributes("data-state")).toBe("READY");
  });

  it("shows a safe unavailable state without error details", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("secret path")));
    const wrapper = mount(ConnectionStatus);

    await flushPromises();

    expect(wrapper.text()).toContain("服务暂不可用");
    expect(wrapper.text()).not.toContain("secret path");
  });
});
