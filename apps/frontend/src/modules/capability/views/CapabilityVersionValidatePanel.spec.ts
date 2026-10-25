import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { CapabilityVersionValidateClient, CapabilityValidateError } from "@/modules/capability/api/capabilityVersionValidateClient";
import CapabilityVersionValidatePanel from "./CapabilityVersionValidatePanel.vue";

const actor = "01234567-89ab-4cde-8123-456789abcdef";
const baselineId = "11234567-89ab-4cde-8123-456789abcdef";
const versionId = "21234567-89ab-4cde-8123-456789abcdef";
const version = { baseline_id: baselineId, baseline_version_id: versionId, version_no: 1,
  state: "DRAFT" as const, source_collection_ref: `sha256:${"a".repeat(64)}`,
  content_fingerprint: "b".repeat(64), declared_item_count: 1, declared_document_ref_count: 1,
  declared_evidence_ref_count: 1, supersedes_version_ref: null, review_ref: null,
  review_round_ref: null, created_at: "2026-10-24T01:00:00Z" };
const report = { audit_event_id: "31234567-89ab-4cde-8123-456789abcdef", baseline_id: baselineId,
  baseline_version_id: versionId, version_no: 1, state: "DRAFT" as const,
  source_collection_ref: version.source_collection_ref, content_fingerprint: version.content_fingerprint,
  item_count: 1, document_ref_count: 1, evidence_ref_count: 1, valid: false,
  blocking_issues: ["EVIDENCE_UNAVAILABLE" as const], warnings: [], checked_at: "2026-10-24T01:01:00Z" };
async function setup(admin = true) {
  const session = new SessionClient(vi.fn().mockResolvedValue(new Response(JSON.stringify({
    data: { user: { user_id: actor, username_display: "合成用户" },
      deployment_role: admin ? "DEPLOYMENT_ADMIN" : "NONE", password_change_required: false,
      authorized_projects: admin ? [] : [{ project_id: baselineId, name: "合成项目", role: "PROJECT_MANAGER" }],
      absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
      csrf_token: "a".repeat(64) }, trace_id: actor }),
    { status: 200, headers: { "Content-Type": "application/json" } })) as typeof fetch);
  await session.login("synthetic", "synthetic-only");
  const validator = new CapabilityVersionValidateClient(session);
  const validate = vi.spyOn(validator, "validate").mockResolvedValue(report);
  const wrapper = mount(CapabilityVersionValidatePanel, { props: { version, session, validator } });
  return { wrapper, validate, session };
}
describe("CapabilityVersionValidatePanel", () => {
  afterEach(() => { vi.restoreAllMocks(); window.sessionStorage.clear(); });
  it("shows a blocking report without treating it as approval", async () => {
    const { wrapper, validate } = await setup();
    await wrapper.get("button").trigger("click"); await flushPromises();
    expect(validate).toHaveBeenCalledOnce();
    expect(wrapper.text()).toContain("当前来源校验未通过，不能送审");
    expect(wrapper.text()).toContain("证据资格或同源关系不可用");
    expect(wrapper.text()).toContain("不是审批结论");
    expect(window.sessionStorage.length).toBe(0);
    wrapper.unmount();
  });
  it("preserves the same operation key after an uncertain outcome", async () => {
    const { wrapper, validate } = await setup();
    validate.mockRejectedValueOnce(new CapabilityValidateError("CAP_VALIDATE_UNCERTAIN"));
    await wrapper.get("button").trigger("click"); await flushPromises();
    expect(wrapper.text()).toContain("原校验操作号已保留");
    const firstKey = validate.mock.calls[0]![1];
    expect(window.sessionStorage.length).toBe(1);
    await wrapper.get('input[type="checkbox"]').setValue(true);
    await wrapper.get("button").trigger("click"); await flushPromises();
    expect(validate.mock.calls[1]![1]).toBe(firstKey);
    expect(window.sessionStorage.length).toBe(0);
    wrapper.unmount();
  });
  it("does not expose validation to ordinary project members", async () => {
    const { wrapper, validate } = await setup(false);
    expect(wrapper.find("button").exists()).toBe(false);
    expect(validate).not.toHaveBeenCalled();
    wrapper.unmount();
  });
});
