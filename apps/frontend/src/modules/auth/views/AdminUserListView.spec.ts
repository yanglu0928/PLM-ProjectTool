import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { AdminUserListClient } from "@/modules/auth/api/adminUserListClient";
import AdminUserListView from "./AdminUserListView.vue";

const adminId = "01234567-89ab-4cde-8123-456789abcdef";
const otherId = "11234567-89ab-4cde-8123-456789abcdef";
const cursor = "u1.synthetic_cursor";
const enabled = { user_id: otherId, username_display: "<script>负责人</script>",
  account_state: "ENABLED", deployment_role: "NONE", private: "never-show" };
function reply(data: unknown, status = 200, code?: string) {
  return new Response(JSON.stringify(code ? { error: { code, message: "private server details" }, trace_id: adminId }
    : { data, trace_id: adminId }), { status, headers: { "Content-Type": "application/json" } });
}
function page(items: unknown[], next_cursor: string | null = null) {
  return reply({ items, next_cursor, has_more: next_cursor !== null });
}
async function session(admin = true, restricted = false, login = true) {
  const auth = new SessionClient(vi.fn().mockResolvedValue(reply({
    user: { user_id: adminId, username_display: "合成管理员" },
    deployment_role: admin ? "DEPLOYMENT_ADMIN" : "NONE", password_change_required: restricted,
    authorized_projects: [], absolute_expires_at: "2030-01-01T12:00:00Z",
    idle_expires_at: "2030-01-01T11:00:00Z",
  })) as typeof fetch);
  if (login) await auth.current();
  return auth;
}
async function view(auth: SessionClient, ...results: Response[]) {
  const fetcher = vi.fn();
  for (const result of results) fetcher.mockResolvedValueOnce(result);
  const users = new AdminUserListClient(fetcher as typeof fetch);
  const router = createAppRouter(createMemoryHistory());
  await router.push("/admin/users");
  await router.isReady();
  const wrapper = mount(AdminUserListView, { props: { session: auth, users },
    global: { plugins: [router] } });
  await flushPromises();
  return { wrapper, fetcher };
}

describe("AdminUserListView", () => {
  afterEach(() => vi.restoreAllMocks());

  it.each([[false, false, false], [false, false, true], [false, true, true]] as const)(
    "does not read users without current unrestricted Admin identity %s %s %s",
    async (admin, restricted, login) => {
      const { wrapper, fetcher } = await view(await session(admin, restricted, login));
      expect(wrapper.text()).toContain("需要已登录且不受改密限制的部署管理员会话");
      expect(fetcher).not.toHaveBeenCalled();
      wrapper.unmount();
    });

  it("reads only server data from a read-only Admin session and escapes names", async () => {
    const { wrapper, fetcher } = await view(await session(), page([enabled]));
    expect(fetcher).toHaveBeenCalledExactlyOnceWith("/api/v1/admin/users?page_size=50", expect.objectContaining({
      method: "GET", credentials: "same-origin", cache: "no-store", redirect: "error",
    }));
    expect(wrapper.text()).toContain(enabled.username_display);
    expect(wrapper.find("script").exists()).toBe(false);
    expect(wrapper.html()).not.toContain("never-show");
    expect(wrapper.get('a[href="/admin/users/new"]').text()).toBe("创建账户");
    expect(wrapper.get(`a[href="/admin/users/${otherId}"]`).text()).toBe("查看详情与状态");
    wrapper.unmount();
  });

  it("shows an empty authorized page without inventing accounts", async () => {
    const { wrapper } = await view(await session(), page([]));
    expect(wrapper.text()).toContain("当前没有可显示的用户账户");
    expect(wrapper.findAll('ul[aria-label="部署用户账户"] li')).toHaveLength(0);
    wrapper.unmount();
  });

  it("loads an explicit second page once and preserves only unique safe rows", async () => {
    const first = Array.from({ length: 50 }, (_, index) => ({ ...enabled,
      user_id: `01234567-89ab-4cde-8123-${String(index).padStart(12, "0")}` }));
    const { wrapper, fetcher } = await view(await session(), page(first, cursor),
      page([{ ...enabled, user_id: otherId, username_display: "停用用户", account_state: "DISABLED" }]));
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(wrapper.findAll('ul[aria-label="部署用户账户"] li')).toHaveLength(50);
    await wrapper.get("button:last-of-type").trigger("click");
    await flushPromises();
    expect(fetcher.mock.calls[1][0]).toBe(`/api/v1/admin/users?page_size=50&cursor=${cursor}`);
    expect(wrapper.findAll('ul[aria-label="部署用户账户"] li')).toHaveLength(51);
    expect(wrapper.text()).toContain("停用用户");
    wrapper.unmount();
  });

  it("clears stale users on a failed refresh without exposing server details", async () => {
    const { wrapper, fetcher } = await view(await session(), page([enabled]),
      reply(null, 503, "SYSTEM_UNAVAILABLE"));
    expect(wrapper.text()).toContain(enabled.username_display);
    await wrapper.get("button").trigger("click");
    await flushPromises();
    expect(wrapper.text()).not.toContain(enabled.username_display);
    expect(wrapper.text()).toContain("暂时无法读取用户列表");
    expect(wrapper.html()).not.toContain("private server details");
    expect(fetcher).toHaveBeenCalledTimes(2);
    wrapper.unmount();
  });
});
