import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { AdminUserDetailClient } from "@/modules/auth/api/adminUserDetailClient";
import { AdminUserNameClient } from "@/modules/auth/api/adminUserNameClient";
import AdminUserNameView from "./AdminUserNameView.vue";

const adminId = "01234567-89ab-4cde-8123-456789abcdef";
const userId = "11234567-89ab-4cde-8123-456789abcdef";
const otherId = "21234567-89ab-4cde-8123-456789abcdef";
const before = { user_id: userId, username_display: "原用户名", account_state: "ENABLED",
  deployment_role: "NONE", credential_version: 1, created_at: "2026-09-28T08:30:00Z",
  updated_at: "2026-09-28T09:30:00Z", etag: '"v0"' };
const after = { ...before, username_display: "新用户名", updated_at: "2026-09-28T10:00:00Z", etag: '"v1"' };
function response(data: unknown, status = 200, etag?: string) {
  return new Response(JSON.stringify({ data, trace_id: adminId }), { status,
    headers: { "Content-Type": "application/json", ...(etag ? { ETag: etag } : {}) } });
}
function failure(status: number, code: string) {
  return new Response(JSON.stringify({ error: { code, message: "private server message" }, trace_id: adminId }),
    { status, headers: { "Content-Type": "application/json" } });
}
async function setup(options: { admin?: boolean; restricted?: boolean; writable?: boolean;
  identified?: boolean; details?: Response[]; commands?: Response[] } = {}) {
  const identity = { user: { user_id: adminId, username_display: "合成管理员" },
    deployment_role: options.admin === false || options.restricted === true ? "NONE" : "DEPLOYMENT_ADMIN",
    password_change_required: options.restricted === true, authorized_projects: [],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    ...(options.writable === false ? {} : { csrf_token: "a".repeat(64) }) };
  const authFetcher = vi.fn();
  if (options.identified !== false) authFetcher.mockResolvedValueOnce(response(identity));
  for (const item of options.commands ?? []) authFetcher.mockResolvedValueOnce(item);
  const session = new SessionClient(authFetcher as typeof fetch);
  if (options.identified !== false) {
    if (options.writable === false) await session.current();
    else await session.login("admin", "synthetic-only");
  }
  const detailFetcher = vi.fn();
  for (const item of options.details ?? [response(before, 200, '"v0"')]) detailFetcher.mockResolvedValueOnce(item);
  const details = new AdminUserDetailClient(detailFetcher as typeof fetch);
  const names = new AdminUserNameClient(session);
  const router = createAppRouter(createMemoryHistory());
  await router.push(`/admin/users/${userId}/name`);
  await router.isReady();
  const wrapper = mount(AdminUserNameView, { props: { session, details, names },
    global: { plugins: [router] } });
  await flushPromises();
  return { wrapper, authFetcher, detailFetcher, router, names };
}

describe("AdminUserNameView", () => {
  afterEach(() => vi.restoreAllMocks());

  it.each([{ identified: false }, { admin: false }, { restricted: true }])(
    "does not read or write without unrestricted Admin identity %j", async (options) => {
      const { wrapper, detailFetcher, authFetcher } = await setup(options);
      expect(wrapper.text()).toContain("需要已登录且不受改密限制");
      expect(detailFetcher).not.toHaveBeenCalled();
      expect(authFetcher).toHaveBeenCalledTimes(options.identified === false ? 0 : 1);
      wrapper.unmount();
    });

  it("shows current safe detail but disables PATCH for a read-only Admin", async () => {
    const { wrapper, authFetcher, detailFetcher } = await setup({ writable: false });
    expect(wrapper.text()).toContain("当前会话仅可读取");
    expect(wrapper.get('input[name="new_user_name"]').attributes("disabled")).toBeDefined();
    expect(wrapper.get('button[type="submit"]').attributes("disabled")).toBeDefined();
    expect(authFetcher).toHaveBeenCalledTimes(1);
    expect(detailFetcher).toHaveBeenCalledTimes(1);
    wrapper.unmount();
  });

  it("requires target/version confirmation, keeps first receipt separate, and GETs current", async () => {
    const { wrapper, authFetcher, detailFetcher } = await setup({
      details: [response(before, 200, '"v0"'), response(after, 200, '"v1"')],
      commands: [response(after, 200, '"v1"')],
    });
    expect(wrapper.get('button[type="submit"]').attributes("disabled")).toBeDefined();
    await wrapper.get('input[name="new_user_name"]').setValue("新用户名");
    await wrapper.get('input[name="confirm_user_name"]').setValue(true);
    await wrapper.get('form').trigger("submit");
    await flushPromises();
    expect(authFetcher.mock.calls[1][0]).toBe(`/api/v1/admin/users/${userId}`);
    expect(authFetcher.mock.calls[1][1].method).toBe("PATCH");
    expect(authFetcher.mock.calls[1][1].headers["If-Match"]).toBe('"v0"');
    expect(detailFetcher).toHaveBeenCalledTimes(2);
    expect(wrapper.text()).toContain("本次写入回执");
    expect(wrapper.get('dl[aria-label="服务器当前用户详情"]').text()).toContain('"v1"');
    wrapper.unmount();
  });

  it("on unknown result, GETs for facts but blocks all further PATCH in this page", async () => {
    const { wrapper, authFetcher, detailFetcher } = await setup({
      details: [response(before, 200, '"v0"'), response(after, 200, '"v1"')],
      commands: [failure(503, "SYSTEM_UNAVAILABLE")],
    });
    await wrapper.get('input[name="new_user_name"]').setValue("新用户名");
    await wrapper.get('input[name="confirm_user_name"]').setValue(true);
    await wrapper.get('form').trigger("submit");
    await flushPromises();
    expect(wrapper.text()).toContain("结果无法确认");
    expect(wrapper.text()).toContain("核对审计");
    expect(wrapper.find('button[type="submit"]').exists()).toBe(false);
    expect(wrapper.get('dl[aria-label="服务器当前用户详情"]').text()).toContain('"v1"');
    expect(detailFetcher).toHaveBeenCalledTimes(2);
    expect(authFetcher).toHaveBeenCalledTimes(2);
    wrapper.unmount();
  });

  it("clears stale current detail on a definite version conflict", async () => {
    const { wrapper, authFetcher, detailFetcher } = await setup({ commands: [failure(409, "CONFLICT_VERSION")] });
    await wrapper.get('input[name="new_user_name"]').setValue("新用户名");
    await wrapper.get('input[name="confirm_user_name"]').setValue(true);
    await wrapper.get('form').trigger("submit");
    await flushPromises();
    expect(wrapper.text()).toContain("账户已更新");
    expect(wrapper.find('dl[aria-label="服务器当前用户详情"]').exists()).toBe(false);
    expect(detailFetcher).toHaveBeenCalledTimes(1);
    expect(authFetcher).toHaveBeenCalledTimes(2);
    wrapper.unmount();
  });

  it("clears old target and reads the new route target", async () => {
    const next = { ...before, user_id: otherId, username_display: "另一个用户" };
    const { wrapper, router, detailFetcher } = await setup({
      details: [response(before, 200, '"v0"'), response(next, 200, '"v0"')],
    });
    await router.push(`/admin/users/${otherId}/name`);
    await flushPromises();
    expect(wrapper.text()).not.toContain(before.username_display);
    expect(wrapper.text()).toContain(next.username_display);
    expect(detailFetcher.mock.calls[1][0]).toBe(`/api/v1/admin/users/${otherId}`);
    wrapper.unmount();
  });

  it("ignores a late old-target PATCH result after navigating to another user", async () => {
    const next = { ...before, user_id: otherId, username_display: "另一个用户" };
    const { wrapper, router, detailFetcher, names } = await setup({
      details: [response(before, 200, '"v0"'), response(next, 200, '"v0"')],
    });
    let finish!: () => void;
    const gate = new Promise<void>((resolve) => { finish = resolve; });
    vi.spyOn(names, "change").mockImplementation(async () => {
      await gate;
      return { ...after, account_state: "ENABLED" as const, deployment_role: "NONE" as const };
    });
    await wrapper.get('input[name="new_user_name"]').setValue("新用户名");
    await wrapper.get('input[name="confirm_user_name"]').setValue(true);
    await wrapper.get('form').trigger("submit");
    await router.push(`/admin/users/${otherId}/name`);
    await flushPromises();
    finish();
    await flushPromises();
    expect(wrapper.text()).toContain(next.username_display);
    expect(wrapper.text()).not.toContain("本次写入回执");
    expect(detailFetcher).toHaveBeenCalledTimes(2);
    wrapper.unmount();
  });
});
