import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { AdminUserListClient } from "@/modules/auth/api/adminUserListClient";
import { ProjectCreateClient, ProjectCreateError } from "@/modules/project/api/projectCreateClient";
import ProjectCreateView from "./ProjectCreateView.vue";

const adminId = "01234567-89ab-4cde-8123-456789abcdef";
const managerId = "11234567-89ab-4cde-8123-456789abcdef";
const disabledId = "21234567-89ab-4cde-8123-456789abcdef";
const project = { project_id: "31234567-89ab-4cde-8123-456789abcdef", code: "DEMO", name: "演示项目",
  state: "ACTIVE" as const, created_at: "2026-09-28T08:30:00Z", etag: '"v0"' };
const usersPage = { data: { items: [
  { user_id: managerId, username_display: "负责人", account_state: "ENABLED", deployment_role: "NONE" },
  { user_id: disabledId, username_display: "停用用户", account_state: "DISABLED", deployment_role: "NONE" },
], next_cursor: null, has_more: false }, trace_id: adminId };
function response(data: unknown): Response {
  return new Response(JSON.stringify({ data, trace_id: adminId }), { status: 200,
    headers: { "Content-Type": "application/json" } });
}
async function session(admin = true, restricted = false, login = true) {
  const auth = new SessionClient(vi.fn().mockResolvedValue(response({
    user: { user_id: adminId, username_display: "部署管理员" },
    deployment_role: admin ? "DEPLOYMENT_ADMIN" : "NONE", password_change_required: restricted,
    authorized_projects: [], absolute_expires_at: "2030-01-01T12:00:00Z",
    idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "a".repeat(64),
  })) as typeof fetch);
  if (login) await auth.login("admin", "synthetic-only");
  return auth;
}
async function view(auth: SessionClient) {
  const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify(usersPage), {
    headers: { "Content-Type": "application/json" },
  }));
  const users = new AdminUserListClient(fetcher as typeof fetch);
  const creator = new ProjectCreateClient(auth);
  const create = vi.spyOn(creator, "create");
  const router = createAppRouter(createMemoryHistory());
  await router.push("/projects/new");
  await router.isReady();
  const wrapper = mount(ProjectCreateView, { props: { session: auth, users, creator },
    global: { plugins: [router] } });
  await flushPromises();
  return { wrapper, fetcher, create, router };
}
async function fill(wrapper: Awaited<ReturnType<typeof view>>["wrapper"]) {
  await wrapper.get("#new-project-code").setValue(" DEMO ");
  await wrapper.get("#new-project-name").setValue(" 演示项目 ");
  await wrapper.get("#new-project-manager").setValue(managerId);
}

describe("ProjectCreateView", () => {
  afterEach(() => vi.restoreAllMocks());

  it.each([[false, false, false], [true, false, false], [false, true, true]] as const)(
    "issues no candidate or create request without active admin write session %s %s %s",
    async (admin, restricted, login) => {
      const { wrapper, fetcher, create } = await view(await session(admin, restricted, login));
      expect(wrapper.text()).toContain("需要已登录且可提交的部署管理员会话");
      expect(fetcher).not.toHaveBeenCalled();
      expect(create).not.toHaveBeenCalled();
      wrapper.unmount();
    });

  it("loads candidates but disables a stopped account and does not claim membership eligibility", async () => {
    const { wrapper, fetcher, create } = await view(await session());
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(wrapper.text()).toContain("服务器会在提交时最终核验");
    expect(wrapper.get(`option[value="${disabledId}"]`).attributes("disabled")).toBeDefined();
    await fill(wrapper);
    create.mockResolvedValueOnce(project);
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(create).toHaveBeenCalledTimes(1);
    expect(create.mock.calls[0][0]).toEqual({ code: " DEMO ", name: " 演示项目 ",
      initial_manager_user_id: managerId });
    expect(create.mock.calls[0][1]).toMatch(/^[\x20-\x7e]{16,128}$/);
    expect(wrapper.text()).toContain("项目创建已确认");
    expect(wrapper.text()).toContain("部署管理员不会自动成为项目成员");
    expect(wrapper.find('a[href="/projects/31234567-89ab-4cde-8123-456789abcdef"]').exists()).toBe(false);
    wrapper.unmount();
  });

  it("keeps original input, manager and key after uncertain result; retry needs explicit confirmation", async () => {
    const { wrapper, create } = await view(await session());
    await fill(wrapper);
    create.mockRejectedValueOnce(new ProjectCreateError("PROJECT_CREATE_UNCERTAIN"))
      .mockResolvedValueOnce(project);
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(create).toHaveBeenCalledTimes(1);
    expect(wrapper.text()).toContain("结果无法确认");
    expect(wrapper.get("button[type=submit]").attributes("disabled")).toBeDefined();
    await wrapper.get('input[name="confirm_original_create"]').setValue(true);
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(create).toHaveBeenCalledTimes(2);
    expect(create.mock.calls[1]).toEqual(create.mock.calls[0]);
    expect(wrapper.text()).toContain("项目创建已确认");
    wrapper.unmount();
  });

  it("clears original key on definite rejection; no automatic retry", async () => {
    const { wrapper, create } = await view(await session());
    await fill(wrapper);
    create.mockRejectedValueOnce(new ProjectCreateError("PROJECT_USER_ALREADY_ASSIGNED"));
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(wrapper.text()).toContain("首位负责人已属于其他项目");
    expect(wrapper.text()).not.toContain("原操作仅保留");
    expect(create).toHaveBeenCalledTimes(1);
    wrapper.unmount();
  });

  it("stops in-page retry on idempotency conflict", async () => {
    const { wrapper, create } = await view(await session());
    await fill(wrapper);
    create.mockRejectedValueOnce(new ProjectCreateError("CONFLICT_IDEMPOTENCY"));
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(wrapper.text()).toContain("已停止页面内重试");
    expect(wrapper.get("button[type=submit]").attributes("disabled")).toBeDefined();
    expect(create).toHaveBeenCalledTimes(1);
    wrapper.unmount();
  });
});
