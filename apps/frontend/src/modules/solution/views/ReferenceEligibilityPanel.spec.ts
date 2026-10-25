import { describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import type { ReferenceCurrent } from "@/modules/solution/api/referenceReadClient";
import { ReferenceEligibilityClient, ReferenceEligibilityClientError } from "@/modules/solution/api/referenceEligibilityClient";
import ReferenceEligibilityPanel from "./ReferenceEligibilityPanel.vue";

const actor = "01234567-89ab-4cde-8123-456789abcdef";
const project = "11234567-89ab-4cde-8123-456789abcdef";
const root = "21234567-89ab-4cde-8123-456789abcdef";
const version = "31234567-89ab-4cde-8123-456789abcdef";
const event = "41234567-89ab-4cde-8123-456789abcdef";
const trace = "51234567-89ab-4cde-8123-456789abcdef";
const current = { reference_solution_id: root, reference_version_id: version,
  scope: "PROJECT", project_id: project, eligibility_state: "REFERENCE_ONLY", etag: '"v0"' } as ReferenceCurrent;
const receipt = { eligibility_event_id: event, reference_solution_id: root,
  reference_version_id: version, scope: "PROJECT" as const, project_id: project,
  eligibility_state: "ELIGIBLE" as const, eligibility_reason: "核对当前固定来源", etag: '"v1"' };
async function session(role = "PROJECT_MANAGER") {
  const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ data: {
    user: { user_id: actor, username_display: "Synthetic user" }, deployment_role: "NONE",
    password_change_required: false, authorized_projects: [{ project_id: project, name: "Synthetic", role }],
    absolute_expires_at: "2030-01-11T00:00:00Z", idle_expires_at: "2030-01-10T01:00:00Z",
    csrf_token: "a".repeat(64),
  }, trace_id: trace }), { status: 200, headers: { "Content-Type": "application/json" } }));
  const value = new SessionClient(fetcher as typeof fetch);
  await value.login("user", "synthetic-only");
  return value;
}
function button(wrapper: ReturnType<typeof mount>, text: string) {
  const found = wrapper.findAll("button").find(item => item.text().includes(text));
  if (!found) throw new Error(`Missing button: ${text}`);
  return found;
}
describe("ReferenceEligibilityPanel", () => {
  it("requires reason and second confirmation before an immutable receipt", async () => {
    const identity = await session(); const set = vi.fn().mockResolvedValue(receipt);
    const wrapper = mount(ReferenceEligibilityPanel, { props: { current, session: identity,
      eligibility: { set } as unknown as ReferenceEligibilityClient } });
    expect(button(wrapper, "核对并进入确认").attributes("disabled")).toBeDefined();
    await wrapper.find('input[value="ELIGIBLE"]').setValue();
    await wrapper.find("textarea").setValue("核对当前固定来源");
    await button(wrapper, "核对并进入确认").trigger("click");
    expect(set).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("不可变资格事件和审计");
    await button(wrapper, "确认提交资格决定").trigger("click"); await flushPromises();
    expect(set).toHaveBeenCalledWith(current, "ELIGIBLE", "核对当前固定来源", expect.any(String));
    expect(wrapper.emitted("accepted")?.[0]).toEqual([receipt]);
  });
  it("keeps original operation key on an uncertain result and never invents a new key", async () => {
    const identity = await session(); const set = vi.fn()
      .mockRejectedValueOnce(new ReferenceEligibilityClientError("REFERENCE_ELIGIBILITY_UNCERTAIN"))
      .mockResolvedValueOnce(receipt);
    const wrapper = mount(ReferenceEligibilityPanel, { props: { current, session: identity,
      eligibility: { set } as unknown as ReferenceEligibilityClient } });
    await wrapper.find('input[value="ELIGIBLE"]').setValue();
    await wrapper.find("textarea").setValue("核对当前固定来源");
    await button(wrapper, "核对并进入确认").trigger("click");
    await button(wrapper, "确认提交资格决定").trigger("click"); await flushPromises();
    expect(wrapper.text()).toContain("请勿更换操作号重试");
    expect(wrapper.find('button').text()).not.toContain("返回修改");
    const key = set.mock.calls[0]?.[3];
    await button(wrapper, "按原操作号重试").trigger("click"); await flushPromises();
    expect(set.mock.calls[1]?.[3]).toBe(key);
    expect(wrapper.emitted("accepted")?.[0]).toEqual([receipt]);
  });
  it("hides the write form for a non-manager and for revoked identity", async () => {
    const identity = await session("IMPLEMENTATION_MEMBER");
    const wrapper = mount(ReferenceEligibilityPanel, { props: { current, session: identity } });
    expect(wrapper.find("textarea").exists()).toBe(false);
    await wrapper.setProps({ current: { ...current, eligibility_state: "REVOKED" } as ReferenceCurrent });
    expect(wrapper.text()).toContain("不能恢复资格");
  });
});
