import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { ProjectMemberChoicesClient } from "@/modules/project/api/projectMemberChoicesClient";
import { ProjectMemberCreateClient, ProjectMemberCreateError } from "@/modules/project/api/projectMemberCreateClient";
import ProjectMemberCreateView from "./ProjectMemberCreateView.vue";

const actor = "01234567-89ab-4cde-8123-456789abcdef";
const project = "11234567-89ab-4cde-8123-456789abcdef";
const target = "21234567-89ab-4cde-8123-456789abcdef";
const department = "31234567-89ab-4cde-8123-456789abcdef";
const member = { member_id: "41234567-89ab-4cde-8123-456789abcdef",
  user: { user_id: target, display_name: "张三" }, role: "IMPLEMENTATION_MEMBER" as const,
  department: { department_id: department, name: "研发部" }, state: "ACTIVE" as const,
  effective_at: "2026-09-28T08:30:00Z", ended_at: null, etag: '"v0"' };
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
  const choices = new ProjectMemberChoicesClient(auth);
  const departments = vi.spyOn(choices, "activeDepartments").mockResolvedValue([
    { department_id: department, code: "DEV", name: "研发部" },
  ]);
  const candidate = vi.spyOn(choices, "candidate").mockResolvedValue({ user_id: target, display_name: "张三" });
  const creator = new ProjectMemberCreateClient(auth);
  const create = vi.spyOn(creator, "create");
  const router = createAppRouter(createMemoryHistory());
  await router.push(`/projects/${project}/members/new`);
  await router.isReady();
  const wrapper = mount(ProjectMemberCreateView, { props: { session: auth, choices, creator },
    global: { plugins: [router] } });
  await flushPromises();
  return { wrapper, departments, candidate, create, router };
}
async function fill(wrapper: Awaited<ReturnType<typeof view>>["wrapper"]) {
  await wrapper.get("#member-username").setValue("张三");
  await wrapper.get("form button[type=button]").trigger("click");
  await flushPromises();
  await wrapper.get("#member-role").setValue("IMPLEMENTATION_MEMBER");
  await wrapper.get("#member-department").setValue(department);
  await wrapper.get('input[type="checkbox"]').setValue(true);
}

describe("ProjectMemberCreateView", () => {
  afterEach(() => vi.restoreAllMocks());

  it.each([null, "CUSTOMER_MEMBER"])("does not load or submit without current manager role: %s", async (role) => {
    const { wrapper, departments, candidate, create } = await view(await session(role));
    expect(wrapper.text()).toContain("需要当前项目负责人");
    expect(departments).not.toHaveBeenCalled();
    expect(candidate).not.toHaveBeenCalled();
    expect(create).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it("searches exact username and explicitly confirms role/active department before one create", async () => {
    const { wrapper, departments, candidate, create } = await view(await session());
    expect(departments).toHaveBeenCalledWith(project);
    expect(wrapper.text()).toContain("服务器会在提交时重新核验");
    await fill(wrapper);
    expect(candidate).toHaveBeenCalledWith(project, "张三");
    create.mockResolvedValueOnce(member);
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(create).toHaveBeenCalledTimes(1);
    expect(create.mock.calls[0][0]).toBe(project);
    expect(create.mock.calls[0][1]).toEqual({ user_id: target, role: "IMPLEMENTATION_MEMBER", department_id: department });
    expect(create.mock.calls[0][2]).toMatch(/^[\x20-\x7e]{16,128}$/);
    expect(wrapper.text()).toContain("成员创建已确认");
    wrapper.unmount();
  });

  it("invalidates candidate when username changes, preventing stale target submission", async () => {
    const { wrapper, create } = await view(await session());
    await fill(wrapper);
    await wrapper.get("#member-username").setValue("李四");
    await wrapper.get("form").trigger("submit");
    expect(create).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("请先确认准确用户名");
    wrapper.unmount();
  });

  it("retains original input and key on uncertain result, requiring explicit original retry", async () => {
    const { wrapper, create } = await view(await session());
    await fill(wrapper);
    create.mockRejectedValueOnce(new ProjectMemberCreateError("PROJECT_MEMBER_CREATE_UNCERTAIN"))
      .mockResolvedValueOnce(member);
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(wrapper.text()).toContain("结果无法确认");
    expect(wrapper.get("button[type=submit]").attributes("disabled")).toBeDefined();
    await wrapper.get('input[name="confirm_original_member"]').setValue(true);
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(create).toHaveBeenCalledTimes(2);
    expect(create.mock.calls[1]).toEqual(create.mock.calls[0]);
    expect(wrapper.text()).toContain("成员创建已确认");
    wrapper.unmount();
  });

  it("clears candidate after definite rejection and blocks retry on key conflict", async () => {
    const first = await view(await session());
    await fill(first.wrapper);
    first.create.mockRejectedValueOnce(new ProjectMemberCreateError("PROJECT_USER_ALREADY_ASSIGNED"));
    await first.wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(first.wrapper.text()).toContain("目标用户已属于其他项目");
    expect(first.wrapper.text()).not.toContain("原操作仅保留");
    expect(first.wrapper.text()).not.toContain("已找到候选");
    first.wrapper.unmount();
    const second = await view(await session());
    await fill(second.wrapper);
    second.create.mockRejectedValueOnce(new ProjectMemberCreateError("CONFLICT_IDEMPOTENCY"));
    await second.wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(second.wrapper.text()).toContain("已停止页面内重试");
    expect(second.wrapper.get("button[type=submit]").attributes("disabled")).toBeDefined();
    second.wrapper.unmount();
  });
});
