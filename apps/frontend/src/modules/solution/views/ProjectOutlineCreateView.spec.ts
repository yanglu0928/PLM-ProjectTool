import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { OutlineCreateClient, OutlineCreateError } from "@/modules/solution/api/outlineCreateClient";
import ProjectOutlineCreateView from "./ProjectOutlineCreateView.vue";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const outline = "11234567-89ab-4cde-8123-456789abcdef";
const item = { solution_outline_id: outline, project_id: project, name: "方案目录",
  outline_state: "ACTIVE", current_approved_version_ref: null,
  created_at: "2026-10-09T00:00:00Z", etag: '"v0"' };
async function session(role = "PROJECT_MANAGER") {
  const api = new SessionClient(vi.fn().mockResolvedValue(new Response(JSON.stringify({ data: {
    user: { user_id: project, username_display: "合成用户" }, deployment_role: "NONE",
    password_change_required: false,
    authorized_projects: [{ project_id: project, name: "项目", role }],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64),
  }, trace_id: project }), { status: 200, headers: { "Content-Type": "application/json" } })) as typeof fetch);
  await api.login("user", "synthetic-only"); return api;
}
async function page(role = "PROJECT_MANAGER", create = vi.fn().mockResolvedValue(item)) {
  const router = createAppRouter(createMemoryHistory());
  await router.push(`/projects/${project}/solution-outlines/new`); await router.isReady();
  const wrapper = mount(ProjectOutlineCreateView, { props: { session: await session(role),
    creator: { create } as unknown as OutlineCreateClient }, global: { plugins: [router] } });
  return { wrapper, router, create };
}
describe("ProjectOutlineCreateView", () => {
  afterEach(() => { window.sessionStorage.clear(); vi.restoreAllMocks(); });
  it("shows only the allowed write role and routes a confirmed creation to detail", async () => {
    const denied = await page("CUSTOMER_MEMBER");
    expect(denied.wrapper.find("form").exists()).toBe(false); denied.wrapper.unmount();
    const allowed = await page();
    await allowed.wrapper.get("#outline-name").setValue("  方案目录  ");
    await allowed.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(allowed.create).toHaveBeenCalledExactlyOnceWith(project, "方案目录", expect.any(String));
    await vi.waitFor(() => expect(allowed.router.currentRoute.value.name).toBe("project-outline-detail"));
    expect(allowed.router.currentRoute.value.params.outlineId).toBe(outline);
    expect(window.sessionStorage.length).toBe(0);
    allowed.wrapper.unmount();
  });
  it("persists uncertainty across reload and retries only the original name/key on explicit confirmation", async () => {
    const create = vi.fn().mockRejectedValueOnce(new OutlineCreateError("OUTLINE_CREATE_UNCERTAIN"))
      .mockResolvedValueOnce(item);
    const first = await page("PROJECT_MANAGER", create);
    await first.wrapper.get("#outline-name").setValue("方案目录");
    await first.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(first.wrapper.text()).toContain("结果无法确认");
    const firstKey = create.mock.calls[0]?.[2];
    expect(window.sessionStorage.length).toBe(1);
    first.wrapper.unmount();
    const second = await page("PROJECT_MANAGER", create);
    expect(second.wrapper.get("#outline-name").attributes("disabled")).toBeDefined();
    expect(second.wrapper.get("button[type=submit]").attributes("disabled")).toBeDefined();
    await second.wrapper.get("input[type=checkbox]").setValue(true);
    await second.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(create).toHaveBeenCalledTimes(2);
    expect(create.mock.calls[1]).toEqual([project, "方案目录", firstKey]);
    await vi.waitFor(() => expect(second.router.currentRoute.value.name).toBe("project-outline-detail"));
    second.wrapper.unmount();
  });
  it("fails closed if original key cannot be stored or recovered", async () => {
    const create = vi.fn();
    const view = await page("PROJECT_MANAGER", create);
    const storage = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
    await view.wrapper.get("#outline-name").setValue("方案目录");
    await view.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(create).not.toHaveBeenCalled();
    expect(view.wrapper.text()).toContain("本次未提交");
    storage.mockRestore(); view.wrapper.unmount();
    window.sessionStorage.setItem(`plm.sol.outline.create.pending.${project}.${project}`, "corrupt");
    const restored = await page("PROJECT_MANAGER", create);
    expect(restored.wrapper.get("button[type=submit]").attributes("disabled")).toBeDefined();
    expect(restored.wrapper.text()).toContain("已停止提交");
    restored.wrapper.unmount();
  });
});
