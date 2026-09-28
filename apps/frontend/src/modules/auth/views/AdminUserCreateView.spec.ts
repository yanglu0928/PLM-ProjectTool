import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { AdminUserCreateClient, AdminUserCreateError } from "@/modules/auth/api/adminUserCreateClient";
import AdminUserCreateView from "./AdminUserCreateView.vue";

const adminId = "01234567-89ab-4cde-8123-456789abcdef";
const userId = "11234567-89ab-4cde-8123-456789abcdef";
const created = { user_id: userId, username_display: "测试负责人", account_state: "ENABLED" as const,
  deployment_role: "NONE" as const, credential_version: 1 as const,
  created_at: "2026-09-28T08:30:00Z", updated_at: "2026-09-28T08:30:00Z", etag: '"v1"' as const };
function response(data: unknown): Response {
  return new Response(JSON.stringify({ data, trace_id: adminId }), { status: 200,
    headers: { "Content-Type": "application/json" } });
}
async function session(admin = true, restricted = false, login = true, readOnly = false) {
  const auth = new SessionClient(vi.fn().mockResolvedValue(response({
    user: { user_id: adminId, username_display: "部署管理员" },
    deployment_role: admin ? "DEPLOYMENT_ADMIN" : "NONE", password_change_required: restricted,
    authorized_projects: [], absolute_expires_at: "2030-01-01T12:00:00Z",
    idle_expires_at: "2030-01-01T11:00:00Z", ...(!readOnly ? { csrf_token: "a".repeat(64) } : {}),
  })) as typeof fetch);
  if (login) {
    if (readOnly) await auth.current();
    else await auth.login("admin", "synthetic-only");
  }
  return auth;
}
async function view(auth: SessionClient) {
  const creator = new AdminUserCreateClient(auth);
  const create = vi.spyOn(creator, "create");
  const router = createAppRouter(createMemoryHistory());
  await router.push("/admin/users/new");
  await router.isReady();
  const wrapper = mount(AdminUserCreateView, { props: { session: auth, creator },
    global: { plugins: [router] } });
  await flushPromises();
  return { wrapper, create, router };
}
async function fill(wrapper: Awaited<ReturnType<typeof view>>["wrapper"], password = "synthetic-first-password") {
  await wrapper.get("#admin-new-username").setValue(" 测试负责人 ");
  await wrapper.get("#admin-new-password").setValue(password);
  await wrapper.get("#admin-confirm-password").setValue(password);
}

describe("AdminUserCreateView", () => {
  afterEach(() => vi.restoreAllMocks());

  it.each([[false, false, false, false], [false, false, true, false],
    [false, true, true, false], [true, false, true, true]] as const)(
    "has no create form/request without an active Admin write session %s %s %s %s",
    async (admin, restricted, login, readOnly) => {
      const { wrapper, create } = await view(await session(admin, restricted, login, readOnly));
      expect(wrapper.text()).toContain("需要已登录且可提交的部署管理员会话");
      expect(wrapper.find("form").exists()).toBe(false);
      expect(create).not.toHaveBeenCalled();
      wrapper.unmount();
    });

  it("rejects mismatched confirmation without creating and keeps fields editable", async () => {
    const { wrapper, create } = await view(await session());
    await fill(wrapper);
    await wrapper.get("#admin-confirm-password").setValue("different");
    await wrapper.get("form").trigger("submit");
    expect(wrapper.text()).toContain("两次输入的初始密码不一致");
    expect(create).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it("clears both password fields immediately and displays safe created metadata only", async () => {
    const { wrapper, create } = await view(await session());
    await fill(wrapper);
    let resolve!: (value: typeof created) => void;
    create.mockReturnValueOnce(new Promise((done) => { resolve = done; }));
    await wrapper.get("form").trigger("submit");
    expect(create).toHaveBeenCalledTimes(1);
    expect(create.mock.calls[0][0]).toEqual({ username: "测试负责人", password: "synthetic-first-password" });
    expect(create.mock.calls[0][1]).toMatch(/^[\x20-\x7e]{16,128}$/);
    expect((wrapper.get("#admin-new-password").element as HTMLInputElement).value).toBe("");
    expect((wrapper.get("#admin-confirm-password").element as HTMLInputElement).value).toBe("");
    resolve(created);
    await flushPromises();
    expect(wrapper.text()).toContain("账户创建已确认");
    expect(wrapper.text()).toContain(userId);
    expect(wrapper.text()).toContain("普通用户");
    expect(wrapper.html()).not.toContain("synthetic-first-password");
    expect(wrapper.find('a[href="/projects/new"]').exists()).toBe(true);
    wrapper.unmount();
  });

  it("requires original password re-entry and explicit confirmation for same-key uncertain recovery", async () => {
    const { wrapper, create } = await view(await session());
    await fill(wrapper);
    create.mockRejectedValueOnce(new AdminUserCreateError("USER_CREATE_UNCERTAIN"))
      .mockResolvedValueOnce(created);
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(wrapper.text()).toContain("创建结果无法确认");
    expect((wrapper.get("#admin-new-password").element as HTMLInputElement).value).toBe("");
    expect(wrapper.get("#admin-new-username").attributes("disabled")).toBeDefined();
    expect(wrapper.get("button[type=submit]").attributes("disabled")).toBeDefined();
    await wrapper.get("#admin-new-password").setValue("synthetic-first-password");
    await wrapper.get("#admin-confirm-password").setValue("synthetic-first-password");
    await wrapper.get('input[name="confirm_original_user_create"]').setValue(true);
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(create).toHaveBeenCalledTimes(2);
    expect(create.mock.calls[1]).toEqual(create.mock.calls[0]);
    expect(wrapper.text()).toContain("账户创建已确认");
    wrapper.unmount();
  });

  it("releases original attempt on definite username conflict without automatic retry", async () => {
    const { wrapper, create } = await view(await session());
    await fill(wrapper);
    create.mockRejectedValueOnce(new AdminUserCreateError("CONFLICT_DUPLICATE"));
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(wrapper.text()).toContain("该用户名已存在");
    expect(wrapper.text()).not.toContain("原操作标识仅保留");
    expect(create).toHaveBeenCalledTimes(1);
    wrapper.unmount();
  });

  it("blocks in-page retry on idempotency conflict", async () => {
    const { wrapper, create } = await view(await session());
    await fill(wrapper);
    create.mockRejectedValueOnce(new AdminUserCreateError("CONFLICT_IDEMPOTENCY"));
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(wrapper.text()).toContain("已停止页面内重试");
    expect(wrapper.get("button[type=submit]").attributes("disabled")).toBeDefined();
    expect(create).toHaveBeenCalledTimes(1);
    wrapper.unmount();
  });
});
