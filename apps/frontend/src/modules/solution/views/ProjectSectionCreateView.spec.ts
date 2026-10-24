import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { OutlineReadClient } from "@/modules/solution/api/outlineReadClient";
import { SectionCreateClient, SectionCreateError } from "@/modules/solution/api/sectionCreateClient";
import ProjectSectionCreateView from "./ProjectSectionCreateView.vue";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const outline = "11234567-89ab-4cde-8123-456789abcdef";
const section = "21234567-89ab-4cde-8123-456789abcdef";
const parent = { solution_outline_id: outline, project_id: project, name: "方案目录",
  outline_state: "ACTIVE", current_approved_version_ref: null, created_by: project,
  created_at: "2026-10-09T00:00:00Z", etag: '"v0"' };
const created = { solution_section_id: section, solution_outline_id: outline, project_id: project,
  section_key: "业务范围", section_state: "ACTIVE", current_approved_version_ref: null,
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
async function page(role = "PROJECT_MANAGER", create = vi.fn().mockResolvedValue(created),
                    current = vi.fn().mockResolvedValue(parent)) {
  const router = createAppRouter(createMemoryHistory());
  await router.push(`/projects/${project}/solution-outlines/${outline}/sections/new`); await router.isReady();
  const wrapper = mount(ProjectSectionCreateView, { props: { session: await session(role),
    reader: { current } as unknown as OutlineReadClient,
    creator: { create } as unknown as SectionCreateClient }, global: { plugins: [router] } });
  await flushPromises();
  return { wrapper, router, create, current };
}
describe("ProjectSectionCreateView", () => {
  afterEach(() => { window.sessionStorage.clear(); vi.restoreAllMocks(); });

  it("reads parent, gates write roles and routes confirmed creation to Section detail", async () => {
    const denied = await page("CUSTOMER_MEMBER");
    expect(denied.wrapper.find("form").exists()).toBe(false);
    expect(denied.current).not.toHaveBeenCalled(); denied.wrapper.unmount();
    const allowed = await page();
    expect(allowed.router.currentRoute.value.name).toBe("project-section-create");
    expect(allowed.current).toHaveBeenCalledWith(project, outline);
    await allowed.wrapper.get("#section-key").setValue("  业务范围  ");
    await allowed.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(allowed.create).toHaveBeenCalledExactlyOnceWith(project, outline, "业务范围", expect.any(String));
    await vi.waitFor(() => expect(allowed.router.currentRoute.value.name).toBe("project-section-detail"));
    expect(allowed.router.currentRoute.value.params.sectionId).toBe(section);
    expect(window.sessionStorage.length).toBe(0);
    allowed.wrapper.unmount();
  });

  it("never submits if parent is archived or does not match route", async () => {
    const create = vi.fn();
    const archived = await page("PROJECT_MANAGER", create,
      vi.fn().mockResolvedValue({ ...parent, outline_state: "ARCHIVED" }));
    expect(archived.wrapper.find("form").exists()).toBe(false);
    expect(archived.wrapper.text()).toContain("父目录已归档"); archived.wrapper.unmount();
    const mismatch = await page("PROJECT_MANAGER", create,
      vi.fn().mockResolvedValue({ ...parent, project_id: section }));
    expect(mismatch.wrapper.find("form").exists()).toBe(false);
    expect(mismatch.wrapper.find("[role=alert]").exists()).toBe(true);
    expect(create).not.toHaveBeenCalled(); mismatch.wrapper.unmount();
  });

  it("persists uncertain result and retries only same key/parent on explicit confirmation", async () => {
    const create = vi.fn().mockRejectedValueOnce(new SectionCreateError("SECTION_CREATE_UNCERTAIN"))
      .mockResolvedValueOnce(created);
    const first = await page("PROJECT_MANAGER", create);
    await first.wrapper.get("#section-key").setValue("业务范围");
    await first.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(first.wrapper.text()).toContain("结果无法确认");
    const originalKey = create.mock.calls[0]?.[3];
    expect(window.sessionStorage.length).toBe(1); first.wrapper.unmount();
    const second = await page("PROJECT_MANAGER", create);
    expect(second.wrapper.get("#section-key").attributes("disabled")).toBeDefined();
    expect(second.wrapper.get("button[type=submit]").attributes("disabled")).toBeDefined();
    await second.wrapper.get("input[type=checkbox]").setValue(true);
    await second.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(create.mock.calls[1]).toEqual([project, outline, "业务范围", originalKey]);
    await vi.waitFor(() => expect(second.router.currentRoute.value.name).toBe("project-section-detail"));
    second.wrapper.unmount();
  });

  it("fails closed when original key cannot be stored or recovered", async () => {
    const create = vi.fn();
    const view = await page("PROJECT_MANAGER", create);
    const storage = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
    await view.wrapper.get("#section-key").setValue("业务范围");
    await view.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(create).not.toHaveBeenCalled();
    expect(view.wrapper.text()).toContain("本次未提交");
    storage.mockRestore(); view.wrapper.unmount();
    window.sessionStorage.setItem(`plm.sol.section.create.pending.${project}.${project}.${outline}`, "corrupt");
    const restored = await page("PROJECT_MANAGER", create);
    expect(restored.wrapper.get("button[type=submit]").attributes("disabled")).toBeDefined();
    expect(restored.wrapper.text()).toContain("已停止提交");
    restored.wrapper.unmount();
  });
});
