import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import type { HandoverAnalysisVersionView } from "@/modules/handover/api/handoverReadClient";
import { HandoverVersionValidateClient, HandoverVersionValidateError } from "@/modules/handover/api/handoverVersionValidateClient";
import HandoverVersionValidatePanel from "./HandoverVersionValidatePanel.vue";

const actor = "01234567-89ab-4cde-8123-456789abcdef";
const project = "11234567-89ab-4cde-8123-456789abcdef";
const analysis = "21234567-89ab-4cde-8123-456789abcdef";
const versionId = "31234567-89ab-4cde-8123-456789abcdef";
const version: HandoverAnalysisVersionView = {
  handover_analysis_version_id: versionId, handover_analysis_id: analysis, project_id: project,
  version_no: 1, state: "DRAFT", source_set_ref: `sha256:${"a".repeat(64)}`,
  capability_baseline_id: "41234567-89ab-4cde-8123-456789abcdef",
  capability_baseline_version_ref: "51234567-89ab-4cde-8123-456789abcdef",
  content_fingerprint: "b".repeat(64), declared_source_count: 1, declared_item_count: 2,
  declared_evidence_count: 2, declared_capability_ref_count: 0, declared_ai_task_count: 0,
  supersedes_version_ref: null, review_ref: null, review_round_ref: null,
  created_by: actor, created_at: "2026-10-25T01:00:00Z",
  source_documents: [], ai_tasks: [],
};
const report = { audit_event_id: "61234567-89ab-4cde-8123-456789abcdef",
  handover_analysis_id: analysis, handover_analysis_version_id: versionId, project_id: project,
  version_no: 1, state: "DRAFT" as const, item_count: 2, source_count: 1,
  evidence_count: 2, capability_ref_count: 0, ai_task_count: 0, valid: false,
  blocking_issues: ["SOURCE_UNAVAILABLE" as const, "ACTION_ITEM_REQUIRED" as const], warnings: [],
  checked_at: "2026-10-25T01:01:00Z" };
async function setup(role: "PROJECT_MANAGER" | "IMPLEMENTATION_MEMBER" | "CUSTOMER_MANAGER" = "PROJECT_MANAGER") {
  const session = new SessionClient(vi.fn().mockResolvedValue(new Response(JSON.stringify({
    data: { user: { user_id: actor, username_display: "合成用户" }, deployment_role: "NONE",
      password_change_required: false, authorized_projects: [{ project_id: project,
        name: "合成项目", role }], absolute_expires_at: "2030-01-01T12:00:00Z",
      idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "a".repeat(64) }, trace_id: actor }),
  { status: 200, headers: { "Content-Type": "application/json" } })) as typeof fetch);
  await session.login("synthetic", "synthetic-only");
  const validator = new HandoverVersionValidateClient(session);
  const validate = vi.spyOn(validator, "validate").mockResolvedValue(report);
  const wrapper = mount(HandoverVersionValidatePanel, { props: { version, session, validator } });
  return { wrapper, validate, validator, session };
}
describe("HandoverVersionValidatePanel", () => {
  afterEach(() => { vi.restoreAllMocks(); window.sessionStorage.clear(); });
  it("shows the current blocking report without calling it approval", async () => {
    const { wrapper, validate } = await setup();
    await wrapper.get("button").trigger("click"); await flushPromises();
    expect(validate).toHaveBeenCalledOnce();
    expect(wrapper.text()).toContain("本次校验未通过");
    expect(wrapper.text()).toContain("原固定文档已不可用");
    expect(wrapper.text()).toContain("实施待办承接");
    expect(wrapper.text()).toContain("不是客户确认、送审或评审批准");
    expect(window.sessionStorage.length).toBe(0);
    wrapper.unmount();
  });
  it("requires explicit audit check before replaying the same operation key", async () => {
    const { wrapper, validate } = await setup();
    validate.mockRejectedValueOnce(new HandoverVersionValidateError("HND_VALIDATE_UNCERTAIN"));
    await wrapper.get("button").trigger("click"); await flushPromises();
    const key = validate.mock.calls[0]![1];
    expect(wrapper.text()).toContain("原校验操作号已保留");
    expect(wrapper.get("button").attributes("disabled")).toBeDefined();
    expect(window.sessionStorage.length).toBe(1);
    await wrapper.get('input[type="checkbox"]').setValue(true);
    await wrapper.get("button").trigger("click"); await flushPromises();
    expect(validate.mock.calls[1]![1]).toBe(key);
    expect(window.sessionStorage.length).toBe(0);
    wrapper.unmount();
  });
  it("hides write action from customer role and non-DRAFT version", async () => {
    const customer = await setup("CUSTOMER_MANAGER");
    expect(customer.wrapper.find("button").exists()).toBe(false);
    customer.wrapper.unmount();
    const manager = await setup();
    await manager.wrapper.setProps({ version: { ...version, state: "APPROVED" } });
    expect(manager.wrapper.find("button").exists()).toBe(false);
    manager.wrapper.unmount();
  });
  it("does not restore another version's pending key", async () => {
    const { wrapper, validator, session } = await setup();
    const key = `plm.hnd.version.validate.pending.${actor}.${project}.${analysis}.${versionId}`;
    window.sessionStorage.setItem(key, JSON.stringify({ actor, project, analysis, version: versionId,
      key: "synthetic-hnd-validate-pending" }));
    wrapper.unmount();
    const second = mount(HandoverVersionValidatePanel, { props: { version: { ...version,
      handover_analysis_version_id: "71234567-89ab-4cde-8123-456789abcdef", version_no: 2 },
    session, validator } });
    expect(second.text()).not.toContain("原校验操作号已保留");
    expect(second.find("button").exists()).toBe(true);
    second.unmount();
  });
  it("keeps the report surface mounted during a transient Session write", async () => {
    const { wrapper, validate, session } = await setup();
    let allow = true; let finish!: (value: typeof report) => void;
    vi.spyOn(session, "canSubmit", "get").mockImplementation(() => allow);
    validate.mockImplementationOnce(() => { allow = false;
      return new Promise(resolve => { finish = resolve; }); });
    await wrapper.get("button").trigger("click"); await flushPromises();
    expect(wrapper.find('[aria-label="交接版本当前来源校验"]').exists()).toBe(true);
    allow = true; finish(report); await flushPromises();
    expect(wrapper.text()).toContain("本次校验未通过");
    wrapper.unmount();
  });
});
