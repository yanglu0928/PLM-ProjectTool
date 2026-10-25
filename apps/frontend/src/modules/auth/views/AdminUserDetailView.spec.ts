import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { AdminUserDetailClient } from "@/modules/auth/api/adminUserDetailClient";
import { AdminUserStateClient } from "@/modules/auth/api/adminUserStateClient";
import AdminUserDetailView from "./AdminUserDetailView.vue";

const adminId = "01234567-89ab-4cde-8123-456789abcdef";
const userId = "11234567-89ab-4cde-8123-456789abcdef";
const detail = { user_id: userId, username_display: "<script>合成用户</script>",
  account_state: "ENABLED", deployment_role: "NONE", credential_version: 1,
  created_at: "2026-09-28T08:30:00Z", updated_at: "2026-09-28T09:30:00Z", etag: '"v1"' };
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
  for (const command of options.commands ?? []) authFetcher.mockResolvedValueOnce(command);
  const auth = new SessionClient(authFetcher as typeof fetch);
  if (options.identified !== false) {
    if (options.writable === false) await auth.current();
    else await auth.login("admin", "synthetic-only");
  }
  const detailFetcher = vi.fn();
  for (const item of options.details ?? [response(detail, 200, '"v1"')]) detailFetcher.mockResolvedValueOnce(item);
  const details = new AdminUserDetailClient(detailFetcher as typeof fetch);
  const states = new AdminUserStateClient(auth);
  const router = createAppRouter(createMemoryHistory());
  await router.push(`/admin/users/${userId}`);
  await router.isReady();
  const wrapper = mount(AdminUserDetailView, { props: { session: auth, details, states },
    global: { plugins: [router] } });
  await flushPromises();
  return { wrapper, authFetcher, detailFetcher, auth, router, states };
}

describe("AdminUserDetailView", () => {
  afterEach(() => vi.restoreAllMocks());

  it.each([{ identified: false }, { admin: false }, { restricted: true }])(
    "does not read or write without unrestricted DeploymentAdmin identity %j", async (options) => {
      const { wrapper, detailFetcher, authFetcher } = await setup(options);
      expect(wrapper.text()).toContain("需要已登录且不受改密限制的部署管理员会话");
      expect(detailFetcher).not.toHaveBeenCalled();
      expect(authFetcher).toHaveBeenCalledTimes(options.identified === false ? 0 : 1);
      wrapper.unmount();
    });

  it("shows server detail in a read-only Admin session without state controls enabled", async () => {
    const { wrapper, detailFetcher, authFetcher } = await setup({ writable: false });
    expect(wrapper.text()).toContain(detail.username_display);
    expect(wrapper.find("script").exists()).toBe(false);
    expect(wrapper.text()).toContain("当前会话仅可读取");
    expect(wrapper.get('button[type="button"]').attributes("disabled")).toBeDefined();
    expect(detailFetcher).toHaveBeenCalledTimes(1);
    expect(authFetcher).toHaveBeenCalledTimes(1);
    wrapper.unmount();
  });

  it("requires explicit confirmation and the current strong version for disable, then rereads state", async () => {
    const updated = { ...detail, account_state: "DISABLED", etag: '"v2"',
      updated_at: "2026-09-28T10:00:00Z" };
    const { wrapper, authFetcher, detailFetcher } = await setup({
      details: [response(detail, 200, '"v1"'), response(updated, 200, '"v2"')],
      commands: [response(updated, 200, '"v2"')],
    });
    expect(wrapper.get('button[type="button"]').attributes("disabled")).toBeDefined();
    await wrapper.get('input[name="confirm_user_state"]').setValue(true);
    await wrapper.get('button[type="button"]').trigger("click");
    await flushPromises();
    expect(authFetcher.mock.calls[1][0]).toBe(`/api/v1/admin/users/${userId}:disable`);
    expect(authFetcher.mock.calls[1][1].headers["If-Match"]).toBe('"v1"');
    expect(authFetcher.mock.calls[1][1].headers["Idempotency-Key"]).toMatch(/^[\x20-\x7e]{16,128}$/);
    expect(detailFetcher).toHaveBeenCalledTimes(2);
    expect(wrapper.text()).toContain("首次操作结果");
    expect(wrapper.text()).toContain("当前状态");
    expect(wrapper.text()).toContain('"v2"');
    wrapper.unmount();
  });

  it("locks an uncertain result to the original operation, version and key", async () => {
    const updated = { ...detail, account_state: "DISABLED", etag: '"v2"' };
    const { wrapper, authFetcher, detailFetcher } = await setup({
      details: [response(detail, 200, '"v1"'), response(updated, 200, '"v2"')],
      commands: [failure(503, "SYSTEM_UNAVAILABLE"), response(updated, 200, '"v2"')],
    });
    await wrapper.get('input[name="confirm_user_state"]').setValue(true);
    await wrapper.get('button[type="button"]').trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("结果无法确认");
    expect(wrapper.text()).toContain("原版本");
    expect(wrapper.find('input[name="confirm_user_state"]').exists()).toBe(false);
    expect(detailFetcher).toHaveBeenCalledTimes(1);
    const firstOptions = authFetcher.mock.calls[1][1];
    await wrapper.get('input[name="confirm_original_user_state"]').setValue(true);
    const recover = wrapper.findAll("button").find((node) => node.text().includes("按原操作恢复"));
    if (!recover) throw new Error("recovery control missing");
    await recover.trigger("click");
    await flushPromises();
    expect(authFetcher.mock.calls[2][0]).toBe(authFetcher.mock.calls[1][0]);
    expect(authFetcher.mock.calls[2][1].headers["If-Match"]).toBe(firstOptions.headers["If-Match"]);
    expect(authFetcher.mock.calls[2][1].headers["Idempotency-Key"]).toBe(firstOptions.headers["Idempotency-Key"]);
    expect(detailFetcher).toHaveBeenCalledTimes(2);
    wrapper.unmount();
  });

  it("clears stale detail on a definite version conflict and requires a fresh read", async () => {
    const { wrapper, detailFetcher } = await setup({
      commands: [failure(409, "CONFLICT_VERSION")],
    });
    await wrapper.get('input[name="confirm_user_state"]').setValue(true);
    await wrapper.get('button[type="button"]').trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("账户已更新");
    expect(wrapper.find('dl[aria-label="服务器当前用户详情"]').exists()).toBe(false);
    expect(wrapper.find('input[name="confirm_original_user_state"]').exists()).toBe(false);
    expect(detailFetcher).toHaveBeenCalledTimes(1);
    wrapper.unmount();
  });

  it("keeps a historical first result separate from a later current detail", async () => {
    const first = { ...detail, account_state: "DISABLED", etag: '"v2"' };
    const current = { ...detail, account_state: "ENABLED", etag: '"v3"' };
    const { wrapper, detailFetcher } = await setup({
      details: [response(detail, 200, '"v1"'), response(current, 200, '"v3"')],
      commands: [response(first, 200, '"v2"')],
    });
    await wrapper.get('input[name="confirm_user_state"]').setValue(true);
    await wrapper.get('button[type="button"]').trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain('首次操作结果：<script>合成用户</script>（停用，版本 "v2"）');
    expect(wrapper.get('dl[aria-label="服务器当前用户详情"]').text()).toContain("启用");
    expect(wrapper.get('dl[aria-label="服务器当前用户详情"]').text()).toContain('"v3"');
    expect(detailFetcher).toHaveBeenCalledTimes(2);
    wrapper.unmount();
  });

  it("does not keep a stale actionable detail when the post-command read loses its session", async () => {
    const first = { ...detail, account_state: "DISABLED", etag: '"v2"' };
    const { wrapper, detailFetcher } = await setup({
      details: [response(detail, 200, '"v1"'), failure(401, "AUTH_SESSION_EXPIRED")],
      commands: [response(first, 200, '"v2"')],
    });
    await wrapper.get('input[name="confirm_user_state"]').setValue(true);
    await wrapper.get('button[type="button"]').trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("首次操作结果");
    expect(wrapper.text()).toContain("会话已失效");
    expect(wrapper.find('dl[aria-label="服务器当前用户详情"]').exists()).toBe(false);
    expect(detailFetcher).toHaveBeenCalledTimes(2);
    wrapper.unmount();
  });

  it("blocks an enable attempt for a disabled account without a credential", async () => {
    const missing = { ...detail, account_state: "DISABLED", credential_version: 0 };
    const { wrapper, authFetcher } = await setup({ details: [response(missing, 200, '"v1"')] });
    await wrapper.get('input[name="confirm_user_state"]').setValue(true);
    expect(wrapper.text()).toContain("没有可用凭据");
    expect(wrapper.get('button[type="button"]').attributes("disabled")).toBeDefined();
    expect(authFetcher).toHaveBeenCalledTimes(1);
    wrapper.unmount();
  });

  it("treats an unexpected write failure as uncertain and retains original recovery data", async () => {
    const { wrapper, states, authFetcher } = await setup();
    vi.spyOn(states, "change").mockRejectedValueOnce(new Error("private failure"));
    await wrapper.get('input[name="confirm_user_state"]').setValue(true);
    await wrapper.get('button[type="button"]').trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("结果无法确认");
    expect(wrapper.text()).toContain("原版本");
    expect(wrapper.html()).not.toContain("private failure");
    expect(authFetcher).toHaveBeenCalledTimes(1);
    wrapper.unmount();
  });
});
