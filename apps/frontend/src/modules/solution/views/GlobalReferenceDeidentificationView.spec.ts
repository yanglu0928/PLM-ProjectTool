import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { EvidenceViewerClient } from "@/modules/evidence/api/evidenceViewerClient";
import { ReferenceDeidentificationClient, ReferenceDeidentificationError } from "@/modules/solution/api/referenceDeidentificationClient";
import GlobalReferenceDeidentificationView from "./GlobalReferenceDeidentificationView.vue";

const actor = "01234567-89ab-4cde-8123-456789abcdef";
const document = "11234567-89ab-4cde-8123-456789abcdef";
const version = "21234567-89ab-4cde-8123-456789abcdef";
const evidence = "31234567-89ab-4cde-8123-456789abcdef";
const confirmation = "41234567-89ab-4cde-8123-456789abcdef";
const url = `/api/v1/global/documents/${document}/versions/${version}/content`;
const descriptor = { evidence_id: evidence, document_id: document, document_version_id: version,
  document_version_no: 1, detected_mime: "application/pdf", size_bytes: 42,
  locator: { locator_type: "PAGE", page_no: 2 }, precision: "PARSED_NODE",
  display_label: "第 2 页", short_preview: null, content_url: url };
const preview = { source_fingerprint: "f".repeat(64),
  document_refs: [{ document_id: document, document_version_id: version }],
  evidence_ids: [evidence], previewed_at: "2026-10-09T00:00:00Z" };
function response(data: unknown): Response {
  return new Response(JSON.stringify({ data, trace_id: actor }), { status: 200,
    headers: { "Content-Type": "application/json" } });
}
async function session(role: "NONE" | "DEPLOYMENT_ADMIN" = "DEPLOYMENT_ADMIN"): Promise<SessionClient> {
  const api = new SessionClient(vi.fn().mockResolvedValue(response({
    user: { user_id: actor, username_display: "合成管理员" }, deployment_role: role,
    password_change_required: false, authorized_projects: [],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64),
  })) as typeof fetch);
  await api.login("admin", "synthetic-only"); return api;
}
async function page(role: "NONE" | "DEPLOYMENT_ADMIN" = "DEPLOYMENT_ADMIN") {
  const router = createAppRouter(createMemoryHistory());
  await router.push(`/admin/reference-deidentification/${evidence}`); await router.isReady();
  const viewer = { get: vi.fn().mockResolvedValue(descriptor) };
  const attestations = { preview: vi.fn().mockResolvedValue(preview),
    confirm: vi.fn().mockResolvedValue({ confirmation_id: confirmation,
      source_fingerprint: preview.source_fingerprint, confirmed_by: actor,
      confirmed_at: "2026-10-09T00:00:00Z", expires_at: "2026-10-16T00:00:00Z", trace_id: actor }),
    revoke: vi.fn().mockResolvedValue({ confirmation_id: confirmation,
      revoked_at: "2026-10-09T00:01:00Z", trace_id: actor }),
    lookup: vi.fn().mockResolvedValue({ status: "UNCONFIRMED" }) };
  const wrapper = mount(GlobalReferenceDeidentificationView, { props: {
    session: await session(role), viewer: viewer as unknown as EvidenceViewerClient,
    attestations: attestations as unknown as ReferenceDeidentificationClient },
  global: { plugins: [router] } });
  await flushPromises(); return { wrapper, viewer, attestations };
}
function button(wrapper: Awaited<ReturnType<typeof page>>["wrapper"], text: string) {
  return wrapper.findAll("button").find(item => item.text().includes(text))!;
}

describe("GLOBAL human deidentification view", () => {
  afterEach(() => { vi.restoreAllMocks(); window.sessionStorage.clear(); });

  it("requires admin, preview, both opened sources and explicit human attestation", async () => {
    const denied = await page("NONE");
    expect(denied.viewer.get).not.toHaveBeenCalled();
    expect(denied.wrapper.text()).toContain("需要当前 DeploymentAdmin");
    denied.wrapper.unmount();
    const { wrapper, viewer, attestations } = await page();
    expect(viewer.get).toHaveBeenCalledWith({ kind: "GLOBAL" }, evidence);
    const inputs = wrapper.findAll('input:not([type="checkbox"])');
    await inputs[0]!.setValue("PLM"); await inputs[1]!.setValue("DEIDENTIFIED");
    await button(wrapper, "预览当前固定来源").trigger("click"); await flushPromises();
    expect(attestations.preview).toHaveBeenCalledWith({ document_version_ids: [version],
      evidence_ids: [evidence], source_project_class: "PLM",
      deidentification_class: "DEIDENTIFIED", applicability: {} });
    expect(button(wrapper, "提交人工脱敏确认").attributes("disabled")).toBeDefined();
    const links = wrapper.findAll(`a[href="${url}"]`);
    expect(links).toHaveLength(2);
    await links[0]!.trigger("click"); await links[1]!.trigger("click");
    const checks = wrapper.findAll('input[type="checkbox"]');
    await checks[0]!.setValue(true); await checks[1]!.setValue(true);
    expect(button(wrapper, "提交人工脱敏确认").attributes("disabled")).toBeDefined();
    await checks[2]!.setValue(true);
    await button(wrapper, "提交人工脱敏确认").trigger("click"); await flushPromises();
    expect(attestations.confirm).toHaveBeenCalledTimes(1);
    expect(attestations.confirm.mock.calls[0]![1]).toBe(preview.source_fingerprint);
    expect(wrapper.text()).toContain("确认号");
    expect(window.sessionStorage.length).toBe(0);
    await button(wrapper, "撤回此确认").trigger("click"); await flushPromises();
    expect(attestations.revoke).toHaveBeenCalledWith(confirmation, "ADMIN_REVIEW", expect.any(String));
    wrapper.unmount();
  });

  it("locks on unresolved prior operation and never posts a new key", async () => {
    window.sessionStorage.setItem(`plm.sol.global.deidentification.pending.${actor}`,
      JSON.stringify({ actor, evidence_id: evidence, kind: "confirm", key: "k".repeat(16) }));
    const { wrapper, attestations } = await page();
    expect(wrapper.text()).toContain("上次确认结果尚待核对");
    expect(button(wrapper, "预览当前固定来源").attributes("disabled")).toBeDefined();
    await button(wrapper, "按原操作号回查").trigger("click"); await flushPromises();
    expect(attestations.lookup).toHaveBeenCalledWith("CONFIRM", "k".repeat(16));
    expect(wrapper.text()).toContain("尚不能确认首次操作");
    expect(button(wrapper, "预览当前固定来源").attributes("disabled")).toBeDefined();
    attestations.lookup.mockResolvedValueOnce({ status: "COMPLETED", confirmation_id: confirmation,
      first_status_code: 201, current_state: "REVOKED" });
    await button(wrapper, "按原操作号回查").trigger("click"); await flushPromises();
    expect(button(wrapper, "清除本地待核对提醒").attributes("disabled")).toBeDefined();
    await wrapper.findAll('input[type="checkbox"]').find(item => !item.attributes("disabled"))!.setValue(true);
    await button(wrapper, "清除本地待核对提醒").trigger("click");
    expect(window.sessionStorage.length).toBe(0);
    expect(attestations.confirm).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it("drops a stale preview on source drift and keeps uncertain writes locked", async () => {
    const { wrapper, attestations } = await page();
    const inputs = wrapper.findAll('input:not([type="checkbox"])');
    await inputs[0]!.setValue("PLM"); await inputs[1]!.setValue("DEIDENTIFIED");
    await button(wrapper, "预览当前固定来源").trigger("click"); await flushPromises();
    for (const link of wrapper.findAll(`a[href="${url}"]`)) await link.trigger("click");
    const checks = wrapper.findAll('input[type="checkbox"]');
    for (const check of checks) await check.setValue(true);
    attestations.confirm.mockRejectedValueOnce(new ReferenceDeidentificationError("SOURCE_SNAPSHOT_CHANGED"));
    await button(wrapper, "提交人工脱敏确认").trigger("click"); await flushPromises();
    expect(wrapper.text()).toContain("重新预览并逐项核查");
    expect(wrapper.find('[aria-label="预览与逐项核查"]').exists()).toBe(false);
    expect(window.sessionStorage.length).toBe(0);
    await button(wrapper, "预览当前固定来源").trigger("click"); await flushPromises();
    for (const link of wrapper.findAll(`a[href="${url}"]`)) await link.trigger("click");
    for (const check of wrapper.findAll('input[type="checkbox"]')) await check.setValue(true);
    attestations.confirm.mockRejectedValueOnce(new ReferenceDeidentificationError("DEIDENTIFICATION_UNCERTAIN"));
    await button(wrapper, "提交人工脱敏确认").trigger("click"); await flushPromises();
    expect(wrapper.text()).toContain("上次确认结果尚待核对");
    expect(window.sessionStorage.length).toBe(1);
    expect(button(wrapper, "预览当前固定来源").attributes("disabled")).toBeDefined();
    wrapper.unmount();
  });
});
