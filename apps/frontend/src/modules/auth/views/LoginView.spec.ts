import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import LoginView from "./LoginView.vue";
import { SessionClient } from "../api/sessionClient";
import { createAppRouter } from "@/app/router";

const id = "01234567-89ab-4cde-8123-456789abcdef";
function payload(restricted = false, csrf = true) {
  return { user: { user_id: id, username_display: "测试用户" }, deployment_role: restricted ? "NONE" : "DEPLOYMENT_ADMIN",
    password_change_required: restricted, authorized_projects: [], absolute_expires_at: "2030-01-01T12:00:00Z",
    idle_expires_at: "2030-01-01T11:00:00Z", ...(csrf ? { csrf_token: "a".repeat(64) } : {}) };
}
function response(data: unknown) {
  return new Response(JSON.stringify({ data, trace_id: id }), { headers: { "Content-Type": "application/json" } });
}
function setup(...responses: Response[]) {
  const fetcher = vi.fn();
  for (const item of responses) fetcher.mockResolvedValueOnce(item);
  const wrapper = mount(LoginView, { props: { client: new SessionClient(fetcher as typeof fetch) } });
  return { wrapper, fetcher };
}
async function submit(wrapper: ReturnType<typeof setup>["wrapper"]) {
  await wrapper.get('input[name="username"]').setValue("测试用户");
  await wrapper.get('input[name="password"]').setValue("synthetic-input");
  await wrapper.get("form").trigger("submit");
  await flushPromises();
}

describe("LoginView", () => {
  afterEach(() => vi.unstubAllGlobals());
  it("shows accessible labels and no automatic auth request", () => {
    const { wrapper, fetcher } = setup();
    expect(wrapper.get('label[for="login-password"]').text()).toBe("密码");
    expect(wrapper.get('input[name="password"]').attributes("type")).toBe("password");
    expect(wrapper.text()).toContain("重新登录");
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("logs in with the actual client, clears password and shows safe identity", async () => {
    const { wrapper } = setup(response(payload()));
    await submit(wrapper);
    expect(wrapper.text()).toContain("登录成功");
    expect(wrapper.text()).toContain("部署管理员");
    expect((wrapper.get('input[name="password"]').element as HTMLInputElement).value).toBe("");
    expect(wrapper.html()).not.toContain("synthetic-input");
    expect(wrapper.html()).not.toContain("a".repeat(64));
  });
  it("renders server display strings as text, not executable markup", async () => {
    const data = payload();
    data.user.username_display = '<img src=x onerror="alert(1)">';
    const { wrapper } = setup(response(data));
    await submit(wrapper);
    expect(wrapper.text()).toContain('<img src=x onerror="alert(1)">');
    expect(wrapper.find("img").exists()).toBe(false);
  });
  it("shows restricted state instead of admin/project rights", async () => {
    const { wrapper } = setup(response(payload(true)));
    await submit(wrapper);
    expect(wrapper.text()).toContain("改密页面尚待接入");
    expect(wrapper.text()).not.toContain("部署角色：部署管理员");
    expect(wrapper.text()).not.toContain("授权项目：");
  });
  it("restores read-only identity with explicit relogin and disabled writes", async () => {
    const { wrapper } = setup(response(payload(false, false)));
    await wrapper.get(".auth-actions button").trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("提交操作前请重新登录");
    expect(wrapper.findAll(".auth-actions button").slice(1).every((item) => item.attributes("disabled") !== undefined)).toBe(true);
  });
  it("renews then confirms logout with the actual client and clears identity", async () => {
    const { wrapper, fetcher } = setup(response(payload()), response(payload()), response({ revoked: true }));
    await submit(wrapper);
    await wrapper.findAll(".auth-actions button")[1]!.trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("会话已续期");
    await wrapper.findAll(".auth-actions button")[2]!.trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("已退出当前会话");
    expect(wrapper.find(".auth-identity").exists()).toBe(false);
    expect(fetcher.mock.calls[2][1].headers["Idempotency-Key"]).toMatch(/^[0-9a-f-]{36}$/);
  });
  it("does not claim logout after a network failure or expose private details", async () => {
    const { wrapper, fetcher } = setup(response(payload()));
    fetcher.mockRejectedValueOnce(new Error("private host/password"));
    await submit(wrapper);
    await wrapper.findAll(".auth-actions button")[2]!.trigger("click");
    await flushPromises();
    expect(wrapper.get('[role="alert"]').text()).toContain("重新登录");
    expect(wrapper.text()).not.toContain("已退出当前会话");
    expect(wrapper.text()).not.toContain("private");
    expect(wrapper.find(".auth-identity").exists()).toBe(false);
  });
  it("blocks duplicate submit and clears the password before the pending response", async () => {
    const { wrapper, fetcher } = setup();
    let resolve!: (value: Response) => void;
    fetcher.mockReturnValueOnce(new Promise<Response>((done) => { resolve = done; }));
    await wrapper.get('input[name="username"]').setValue("user");
    await wrapper.get('input[name="password"]').setValue("synthetic-input");
    await wrapper.get("form").trigger("submit");
    await wrapper.get("form").trigger("submit");
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect((wrapper.get('input[name="password"]').element as HTMLInputElement).value).toBe("");
    expect(wrapper.get('button[type="submit"]').attributes("disabled")).toBeDefined();
    resolve(response(payload()));
    await flushPromises();
  });
  it("discards an async result after leaving the page", async () => {
    const { wrapper, fetcher } = setup();
    let resolve!: (value: Response) => void;
    fetcher.mockReturnValueOnce(new Promise<Response>((done) => { resolve = done; }));
    await wrapper.get(".auth-actions button").trigger("click");
    wrapper.unmount();
    resolve(response(payload(false, false)));
    await flushPromises();
    expect(wrapper.find(".auth-identity").exists()).toBe(false);
  });
  it("registers the real login page without redirecting unknown routes into auth", async () => {
    const router = createAppRouter(createMemoryHistory());
    await router.push("/login");
    await router.isReady();
    expect(router.currentRoute.value.name).toBe("login");
    expect(router.resolve("/unknown").name).toBe("not-found");
  });
});
