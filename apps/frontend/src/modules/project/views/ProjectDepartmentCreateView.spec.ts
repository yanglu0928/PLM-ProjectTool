import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { ProjectDepartmentCreateClient, ProjectDepartmentCreateError } from
  "@/modules/project/api/projectDepartmentCreateClient";
import ProjectDepartmentCreateView from "./ProjectDepartmentCreateView.vue";

const actor = "01234567-89ab-4cde-8123-456789abcdef";
const project = "11234567-89ab-4cde-8123-456789abcdef";
const other = "21234567-89ab-4cde-8123-456789abcdef";
const department = { department_id: "31234567-89ab-4cde-8123-456789abcdef", code: "RD",
  name: "研发部", state: "ACTIVE" as const, created_at: "2026-09-29T03:00:00Z", etag: '"v0"' };
const receipt = { first_result: department, is_current_state_proof: false as const };
function response(data: unknown): Response {
  return new Response(JSON.stringify({ data, trace_id: actor }), { status: 200,
    headers: { "Content-Type": "application/json" } });
}
async function session(role: string | null = "PROJECT_MANAGER", login = true) {
  const auth = new SessionClient(vi.fn().mockResolvedValue(response({
    user: { user_id: actor, username_display: "负责人" }, deployment_role: "NONE",
    password_change_required: false, authorized_projects: role ? [{ project_id: project, name: "项目", role }] : [],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64),
  })) as typeof fetch);
  if (login) await auth.login("负责人", "synthetic-only");
  return auth;
}
async function view(auth: SessionClient) {
  const creator = new ProjectDepartmentCreateClient(auth);
  const create = vi.spyOn(creator, "create");
  const router = createAppRouter(createMemoryHistory());
  await router.push(`/projects/${project}/departments/new`);
  await router.isReady();
  const wrapper = mount(ProjectDepartmentCreateView, { props: { session: auth, creator },
    global: { plugins: [router] } });
  await flushPromises();
  return { wrapper, create, router };
}
async function fill(wrapper: Awaited<ReturnType<typeof view>>["wrapper"]) {
  await wrapper.get("#department-code").setValue("RD");
  await wrapper.get("#department-name").setValue("研发部");
  await wrapper.get('input[type="checkbox"]').setValue(true);
}

describe("ProjectDepartmentCreateView", () => {
  afterEach(() => vi.restoreAllMocks());

  it.each([null, "CUSTOMER_MEMBER"])("blocks create without current manager role: %s", async (role) => {
    const { wrapper, create } = await view(await session(role));
    expect(wrapper.text()).toContain("需要当前项目负责人");
    expect(wrapper.find("form").exists()).toBe(false);
    expect(create).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it("blocks create without an in-memory write session", async () => {
    const { wrapper, create } = await view(await session("PROJECT_MANAGER", false));
    expect(wrapper.text()).toContain("需要当前项目负责人");
    expect(create).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it("requires renewed confirmation after editing and sends one scoped attempt", async () => {
    const { wrapper, create } = await view(await session());
    await fill(wrapper);
    await wrapper.get("#department-name").setValue("新研发部");
    expect(wrapper.get("button[type=submit]").attributes("disabled")).toBeDefined();
    await wrapper.get('input[type="checkbox"]').setValue(true);
    create.mockResolvedValueOnce({ first_result: { ...department, name: "新研发部" }, is_current_state_proof: false });
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(create).toHaveBeenCalledTimes(1);
    expect(create.mock.calls[0][0]).toBe(project);
    expect(create.mock.calls[0][1]).toEqual({ code: "RD", name: "新研发部" });
    expect(create.mock.calls[0][2]).toMatch(/^[\x20-\x7e]{16,128}$/);
    expect(wrapper.text()).toContain("首次回执");
    expect(wrapper.text()).toContain("不是当前状态证明");
    expect(wrapper.find("form").exists()).toBe(false);
    wrapper.unmount();
  });

  it("retains original input and key on uncertainty, requiring explicit original retry", async () => {
    const { wrapper, create } = await view(await session());
    await fill(wrapper);
    create.mockRejectedValueOnce(new ProjectDepartmentCreateError("PROJECT_DEPARTMENT_CREATE_UNCERTAIN"))
      .mockResolvedValueOnce(receipt);
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(wrapper.text()).toContain("结果无法确认");
    expect(wrapper.get("#department-code").attributes("disabled")).toBeDefined();
    expect(wrapper.get("button[type=submit]").attributes("disabled")).toBeDefined();
    await wrapper.get('input[name="confirm_original_department"]').setValue(true);
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(create).toHaveBeenCalledTimes(2);
    expect(create.mock.calls[1]).toEqual(create.mock.calls[0]);
    expect(wrapper.text()).toContain("首次回执");
    wrapper.unmount();
  });

  it("locks the page on idempotency conflict", async () => {
    const { wrapper, create } = await view(await session());
    await fill(wrapper);
    create.mockRejectedValueOnce(new ProjectDepartmentCreateError("CONFLICT_IDEMPOTENCY"));
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(wrapper.text()).toContain("已停止本页创建");
    expect(wrapper.get("button[type=submit]").attributes("disabled")).toBeDefined();
    await wrapper.get("form").trigger("submit");
    expect(create).toHaveBeenCalledTimes(1);
    wrapper.unmount();
  });

  it("clears a definite refusal and requires a new confirmation", async () => {
    const { wrapper, create } = await view(await session());
    await fill(wrapper);
    create.mockRejectedValueOnce(new ProjectDepartmentCreateError("CONFLICT_DUPLICATE"));
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(wrapper.text()).toContain("部门编号已存在");
    expect(wrapper.get("button[type=submit]").attributes("disabled")).toBeDefined();
    wrapper.unmount();
  });

  it("drops a late receipt after project navigation", async () => {
    const { wrapper, create, router } = await view(await session());
    await fill(wrapper);
    let finish!: (value: typeof receipt) => void;
    create.mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
    await wrapper.get("form").trigger("submit");
    await router.push(`/projects/${other}/departments/new`);
    finish(receipt);
    await flushPromises();
    expect(wrapper.text()).not.toContain("首次回执");
    expect(wrapper.text()).toContain("需要当前项目负责人");
    wrapper.unmount();
  });
});
