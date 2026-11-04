import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { OutputRequestCreateClient, OutputRequestCreateError } from "@/modules/output/api/outputRequestCreateClient";
import type { RequirementVersionView } from "@/modules/requirement/api/requirementReadClient";
import OutputRequestCreateAction from "./OutputRequestCreateAction.vue";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const versionId = "11234567-89ab-4cde-8123-456789abcdef";
const requestId = "21234567-89ab-4cde-8123-456789abcdef";
const version = { requirement_version_id: versionId, project_id: project, state: "APPROVED" } as RequirementVersionView;
async function session(role = "PROJECT_MANAGER") {
  const response = new Response(JSON.stringify({ data: { user: { user_id: project, username_display: "合成用户" },
    deployment_role: "NONE", password_change_required: false,
    authorized_projects: [{ project_id: project, name: "合成项目", role }],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "a".repeat(64) },
    trace_id: project }), { headers: { "Content-Type": "application/json" } });
  const auth = new SessionClient(vi.fn().mockResolvedValue(response) as typeof fetch);
  await auth.login("user", "synthetic-only"); return auth;
}
async function mountAction(auth: SessionClient, creator: OutputRequestCreateClient, approved: string | null = versionId,
  selected = version) {
  const router = createAppRouter(createMemoryHistory());
  await router.push("/projects/" + project + "/requirements/" + versionId); await router.isReady();
  const wrapper = mount(OutputRequestCreateAction, { props: { projectId: project, version: selected,
    approvedVersionRef: approved, session: auth, creator }, global: { plugins: [router] } });
  await flushPromises(); return wrapper;
}
describe("OutputRequestCreateAction", () => {
  it("shows only for the current approved version and reports request receipt without claiming a file", async () => {
    const creator = { create: vi.fn().mockResolvedValue({ output_request_id: requestId, state: "QUEUED" }) } as unknown as OutputRequestCreateClient;
    const wrapper = await mountAction(await session(), creator);
    expect(wrapper.text()).toContain("请求受理不代表文件已生成");
    await wrapper.get("button").trigger("click"); await flushPromises();
    expect(creator.create).toHaveBeenCalledTimes(1);
    expect(creator.create).toHaveBeenCalledWith(project, versionId, expect.stringMatching(/^[\x20-\x7e]{16,128}$/));
    expect(wrapper.text()).toContain(requestId); expect(wrapper.text()).not.toContain("可下载");
    wrapper.unmount();
  });
  it("keeps the receipt area mounted while SessionClient is busy posting", async () => {
    let resolvePost!: (value: Response) => void;
    const loginResponse = new Response(JSON.stringify({ data: {
      user: { user_id: project, username_display: "合成用户" }, deployment_role: "NONE",
      password_change_required: false,
      authorized_projects: [{ project_id: project, name: "合成项目", role: "PROJECT_MANAGER" }],
      absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
      csrf_token: "a".repeat(64) }, trace_id: project }), { headers: { "Content-Type": "application/json" } });
    const transport = vi.fn()
      .mockResolvedValueOnce(loginResponse)
      .mockImplementationOnce(() => new Promise<Response>(resolve => { resolvePost = resolve; }));
    const auth = new SessionClient(transport as typeof fetch);
    await auth.login("user", "synthetic-only");
    const creator = new OutputRequestCreateClient(auth);
    const wrapper = await mountAction(auth, creator);
    await wrapper.get("button").trigger("click");
    await flushPromises();
    expect(auth.canSubmit).toBe(false);
    expect(wrapper.find(".output-create").exists()).toBe(true);
    expect(wrapper.get("button").element.disabled).toBe(true);
    resolvePost(new Response(JSON.stringify({ data: { output_request_id: requestId,
      job_id: "51234567-89ab-4cde-8123-456789abcdef", state: "QUEUED" }, trace_id: trace }),
      { status: 202, headers: { "Content-Type": "application/json" } }));
    await flushPromises();
    expect(wrapper.text()).toContain("请求已受理");
    expect(wrapper.text()).toContain(requestId);
    wrapper.unmount();
  });
  it("hides the action for a non-current approval and a customer member", async () => {
    const creator = { create: vi.fn() } as unknown as OutputRequestCreateClient;
    const mismatch = await mountAction(await session(), creator, "31234567-89ab-4cde-8123-456789abcdef");
    expect(mismatch.find("button").exists()).toBe(false); mismatch.unmount();
    const crossProject = await mountAction(await session(), creator, versionId,
      { ...version, project_id: "31234567-89ab-4cde-8123-456789abcdef" });
    expect(crossProject.find("button").exists()).toBe(false); crossProject.unmount();
    const member = await mountAction(await session("CUSTOMER_MEMBER"), creator);
    expect(member.find("button").exists()).toBe(false); expect(creator.create).not.toHaveBeenCalled(); member.unmount();
  });
  it("retains an uncertain result message and never retries automatically", async () => {
    const creator = { create: vi.fn().mockRejectedValue(new OutputRequestCreateError("OUTPUT_CREATE_UNCERTAIN")) } as unknown as OutputRequestCreateClient;
    const wrapper = await mountAction(await session(), creator);
    await wrapper.get("button").trigger("click"); await flushPromises();
    expect(wrapper.get('[role="alert"]').text()).toContain("不要换操作号重复提交");
    expect(wrapper.text()).toContain("查看输出请求历史"); expect(creator.create).toHaveBeenCalledTimes(1);
    expect(wrapper.find("button").exists()).toBe(false); wrapper.unmount();
  });
});
