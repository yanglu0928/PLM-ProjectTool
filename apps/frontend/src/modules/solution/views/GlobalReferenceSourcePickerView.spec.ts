import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import type { EvidenceListClient } from "@/modules/evidence/api/evidenceListClient";
import type { EvidenceViewerClient } from "@/modules/evidence/api/evidenceViewerClient";
import type { EvidenceEligibilityClient } from "@/modules/evidence/api/evidenceEligibilityClient";
import type { ReferenceDeidentificationClient } from "@/modules/solution/api/referenceDeidentificationClient";
import type { GlobalReferenceCreateClient } from "@/modules/solution/api/globalReferenceCreateClient";
import GlobalReferenceSourcePickerView from "./GlobalReferenceSourcePickerView.vue";

const actor = "01234567-89ab-4cde-8123-456789abcdef";
const documentA = "11234567-89ab-4cde-8123-456789abcdef";
const documentB = "21234567-89ab-4cde-8123-456789abcdef";
const versionA = "31234567-89ab-4cde-8123-456789abcdef";
const versionB = "41234567-89ab-4cde-8123-456789abcdef";
const evidenceA = "51234567-89ab-4cde-8123-456789abcdef";
const evidenceB = "61234567-89ab-4cde-8123-456789abcdef";
const evidenceC = "71234567-89ab-4cde-8123-456789abcdef";
const trace = "81234567-89ab-4cde-8123-456789abcdef";
const item = (evidenceId: string, documentId: string, versionId: string,
  eligibilityState: "ELIGIBLE" | "CANDIDATE" = "ELIGIBLE") => ({
  evidence_id: evidenceId, document_id: documentId, document_version_id: versionId,
  display_label: `来源 ${evidenceId.slice(0, 2)}`, display_excerpt: null,
  eligibility_state: eligibilityState, created_at: "2026-10-09T00:00:00Z",
});
const first = item(evidenceA, documentA, versionA);
const second = item(evidenceB, documentA, versionA);
const third = item(evidenceC, documentB, versionB);
const descriptor = (entry: typeof first) => ({ ...entry, document_version_no: 1,
  detected_mime: "text/plain", size_bytes: 12, locator: { locator_type: "DOCUMENT" },
  precision: "DOCUMENT", short_preview: null,
  content_url: `/api/v1/global/documents/${entry.document_id}/versions/${entry.document_version_id}/content`,
});
function envelope(data: unknown): Response {
  return new Response(JSON.stringify({ data, trace_id: trace }), { status: 200,
    headers: { "Content-Type": "application/json" } });
}
async function session(admin = true): Promise<SessionClient> {
  const api = new SessionClient(vi.fn().mockResolvedValue(envelope({
    user: { user_id: actor, username_display: "Synthetic" },
    deployment_role: admin ? "DEPLOYMENT_ADMIN" : "NONE",
    password_change_required: false, authorized_projects: [],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64),
  })) as typeof fetch);
  await api.login("synthetic", "synthetic-only");
  return api;
}
async function view(admin: boolean, pages: unknown[], currentState = "ELIGIBLE",
  attestation?: object, createClient?: object) {
  const list = vi.fn(); for (const page of pages) list.mockResolvedValueOnce(page);
  const get = vi.fn().mockImplementation(async (_scope, evidenceId) =>
    descriptor([first, second, third].find((entry) => entry.evidence_id === evidenceId)!));
  const currentGlobal = vi.fn().mockImplementation(async (evidenceId) => {
    const entry = [first, second, third].find((candidate) => candidate.evidence_id === evidenceId)!;
    return { evidence_id: entry.evidence_id, document_id: entry.document_id,
      document_version_id: entry.document_version_id, eligibility_state: currentState, etag: '"v1"' };
  });
  const router = createAppRouter(createMemoryHistory());
  await router.push("/admin/reference-deidentification"); await router.isReady();
  const wrapper = mount(GlobalReferenceSourcePickerView, { props: {
    session: await session(admin), listClient: { list } as unknown as EvidenceListClient,
    viewerClient: { get } as unknown as EvidenceViewerClient,
    eligibilityClient: { currentGlobal } as unknown as EvidenceEligibilityClient,
    attestationClient: attestation as ReferenceDeidentificationClient | undefined,
    createClient: createClient as GlobalReferenceCreateClient | undefined,
  }, global: { plugins: [router] } });
  await flushPromises();
  return { wrapper, list, get, currentGlobal };
}
function button(wrapper: Awaited<ReturnType<typeof view>>["wrapper"], label: string) {
  return wrapper.findAll("button").find((entry) => entry.text() === label)!;
}

describe("GlobalReferenceSourcePickerView", () => {
  afterEach(() => { vi.restoreAllMocks(); window.sessionStorage.clear(); });

  it("keeps ordered Evidence while counting the same fixed document once", async () => {
    const result = await view(true, [{ items: [first, second], next_cursor: "next", has_more: true },
      { items: [third], next_cursor: null, has_more: false }]);
    expect(result.list).toHaveBeenCalledWith({ kind: "GLOBAL" }, null);
    await result.wrapper.findAll("button").filter((entry) => entry.text() === "加入核查候选")[0]!.trigger("click");
    await flushPromises();
    await result.wrapper.findAll("button").filter((entry) => entry.text() === "加入核查候选")[1]!.trigger("click");
    await flushPromises();
    expect(result.wrapper.text()).toContain("2 条证据、1 个固定文档版本");
    await button(result.wrapper, "继续加载").trigger("click"); await flushPromises();
    expect(result.list).toHaveBeenLastCalledWith({ kind: "GLOBAL" }, "next");
    await result.wrapper.findAll("button").filter((entry) => entry.text() === "加入核查候选")[2]!.trigger("click");
    await flushPromises();
    expect(result.wrapper.text()).toContain("3 条证据、2 个固定文档版本");
    expect(result.wrapper.findAll('ol[aria-label="已选固定来源"] li a')).toHaveLength(3);
    expect(result.wrapper.text()).toContain("至少选择两条证据");
    expect(result.wrapper.text()).not.toContain("提交人工脱敏确认");
  });

  it("rejects stale eligibility and clears the collection on refresh", async () => {
    const result = await view(true, [{ items: [first], next_cursor: null, has_more: false },
      { items: [first], next_cursor: null, has_more: false }], "REVOKED");
    await button(result.wrapper, "加入核查候选").trigger("click"); await flushPromises();
    expect(result.wrapper.text()).toContain("固定来源已变化");
    expect(result.wrapper.text()).toContain("0 条证据");
    await button(result.wrapper, "重新读取并清空候选").trigger("click"); await flushPromises();
    expect(result.wrapper.text()).not.toContain("固定来源已变化");
  });

  it("does not list or reveal candidates to a non-admin", async () => {
    const result = await view(false, []);
    expect(result.list).not.toHaveBeenCalled();
    expect(result.wrapper.text()).toContain("需要当前 DeploymentAdmin");
    expect(result.wrapper.find('ol[aria-label="已选固定来源"]').exists()).toBe(false);
  });

  it("requires a fresh ordered Preview and every document/Evidence inspection before Confirm", async () => {
    const fingerprint = "f".repeat(64);
    const preview = vi.fn().mockResolvedValue({ source_fingerprint: fingerprint,
      document_refs: [{ document_id: documentA, document_version_id: versionA },
        { document_id: documentB, document_version_id: versionB }],
      evidence_ids: [evidenceA, evidenceC], previewed_at: "2026-10-09T00:00:00Z" });
    const confirm = vi.fn().mockResolvedValue({ confirmation_id: trace,
      source_fingerprint: fingerprint, confirmed_by: actor,
      confirmed_at: "2026-10-09T00:00:00Z", expires_at: "2026-10-16T00:00:00Z",
      trace_id: trace });
    const result = await view(true, [{ items: [first, third], next_cursor: null,
      has_more: false }], "ELIGIBLE", { preview, confirm });
    for (const action of result.wrapper.findAll("button").filter((entry) =>
      entry.text() === "加入核查候选")) {
      await action.trigger("click"); await flushPromises();
    }
    await result.wrapper.find('input[placeholder="PLM"]').setValue("PLM");
    await result.wrapper.find('input[placeholder="DEIDENTIFIED"]').setValue("DEIDENTIFIED");
    await flushPromises();
    await button(result.wrapper, "预览所选来源集合").trigger("click"); await flushPromises();
    expect(preview).toHaveBeenCalledWith({ document_version_ids: [versionA, versionB],
      evidence_ids: [evidenceA, evidenceC], source_project_class: "PLM",
      deidentification_class: "DEIDENTIFIED", applicability: {} });
    const section = result.wrapper.get('section[aria-label="集合预览与逐项原文核查"]');
    expect(section.findAll("a")).toHaveLength(4);
    expect(button(result.wrapper, "提交集合人工脱敏确认（有效期 7 天）").attributes("disabled"))
      .toBeDefined();
    for (const link of section.findAll("a")) await link.trigger("click");
    for (const checkbox of section.findAll('input[type="checkbox"]')) await checkbox.setValue(true);
    await flushPromises();
    expect(button(result.wrapper, "提交集合人工脱敏确认（有效期 7 天）").attributes("disabled"))
      .toBeUndefined();
    await button(result.wrapper, "提交集合人工脱敏确认（有效期 7 天）").trigger("click");
    await flushPromises();
    expect(confirm).toHaveBeenCalledOnce();
    expect(confirm.mock.calls[0]?.[1]).toBe(fingerprint);
    expect(result.wrapper.text()).toContain("集合人工确认已提交");
    expect(button(result.wrapper, "重新读取并清空候选").attributes("disabled")).toBeDefined();
  });

  it("fails closed when Preview returns a different ordered source identity", async () => {
    const preview = vi.fn().mockResolvedValue({ source_fingerprint: "f".repeat(64),
      document_refs: [{ document_id: documentB, document_version_id: versionB },
        { document_id: documentA, document_version_id: versionA }],
      evidence_ids: [evidenceA, evidenceC], previewed_at: "2026-10-09T00:00:00Z" });
    const confirm = vi.fn();
    const result = await view(true, [{ items: [first, third], next_cursor: null,
      has_more: false }], "ELIGIBLE", { preview, confirm });
    for (const action of result.wrapper.findAll("button").filter((entry) =>
      entry.text() === "加入核查候选")) {
      await action.trigger("click"); await flushPromises();
    }
    await result.wrapper.find('input[placeholder="PLM"]').setValue("PLM");
    await result.wrapper.find('input[placeholder="DEIDENTIFIED"]').setValue("DEIDENTIFIED");
    await button(result.wrapper, "预览所选来源集合").trigger("click"); await flushPromises();
    expect(result.wrapper.text()).toContain("预览身份不一致");
    expect(result.wrapper.find('section[aria-label="集合预览与逐项原文核查"]').exists()).toBe(false);
    expect(confirm).not.toHaveBeenCalled();
  });

  it("invalidates a preview and all checkboxes after classification changes", async () => {
    const preview = vi.fn().mockResolvedValue({ source_fingerprint: "f".repeat(64),
      document_refs: [{ document_id: documentA, document_version_id: versionA }],
      evidence_ids: [evidenceA, evidenceB], previewed_at: "2026-10-09T00:00:00Z" });
    const result = await view(true, [{ items: [first, second], next_cursor: null,
      has_more: false }], "ELIGIBLE", { preview, confirm: vi.fn() });
    for (const action of result.wrapper.findAll("button").filter((entry) =>
      entry.text() === "加入核查候选")) {
      await action.trigger("click"); await flushPromises();
    }
    await result.wrapper.find('input[placeholder="PLM"]').setValue("PLM");
    await result.wrapper.find('input[placeholder="DEIDENTIFIED"]').setValue("DEIDENTIFIED");
    await button(result.wrapper, "预览所选来源集合").trigger("click"); await flushPromises();
    expect(result.wrapper.find('section[aria-label="集合预览与逐项原文核查"]').exists()).toBe(true);
    await result.wrapper.find('input[placeholder="DEIDENTIFIED"]').setValue("REDACTED");
    await flushPromises();
    expect(result.wrapper.find('section[aria-label="集合预览与逐项原文核查"]').exists()).toBe(false);
  });

  it("keeps an uncertain Confirm locked until same-key receipt and current state are reviewed", async () => {
    const fingerprint = "f".repeat(64);
    const preview = vi.fn().mockResolvedValue({ source_fingerprint: fingerprint,
      document_refs: [{ document_id: documentA, document_version_id: versionA }],
      evidence_ids: [evidenceA, evidenceB], previewed_at: "2026-10-09T00:00:00Z" });
    const confirm = vi.fn().mockRejectedValue(new TypeError("network unknown"));
    const lookup = vi.fn().mockResolvedValueOnce({ status: "UNCONFIRMED" })
      .mockResolvedValueOnce({ status: "COMPLETED", confirmation_id: trace,
        first_status_code: 201, current_state: "REVOKED" });
    const result = await view(true, [{ items: [first, second], next_cursor: null,
      has_more: false }], "ELIGIBLE", { preview, confirm, lookup });
    for (const action of result.wrapper.findAll("button").filter((entry) =>
      entry.text() === "加入核查候选")) {
      await action.trigger("click"); await flushPromises();
    }
    await result.wrapper.find('input[placeholder="PLM"]').setValue("PLM");
    await result.wrapper.find('input[placeholder="DEIDENTIFIED"]').setValue("DEIDENTIFIED");
    await button(result.wrapper, "预览所选来源集合").trigger("click"); await flushPromises();
    const section = result.wrapper.get('section[aria-label="集合预览与逐项原文核查"]');
    for (const link of section.findAll("a")) await link.trigger("click");
    for (const checkbox of section.findAll('input[type="checkbox"]')) await checkbox.setValue(true);
    await button(result.wrapper, "提交集合人工脱敏确认（有效期 7 天）").trigger("click");
    await flushPromises();
    const pendingKey = `plm.sol.global.deidentification.multi.pending.${actor}`;
    const saved = JSON.parse(window.sessionStorage.getItem(pendingKey)!) as { key: string };
    expect(saved.key).toMatch(/^[\x20-\x7e]{16,128}$/);
    expect(result.wrapper.text()).toContain("结果尚待核对");
    await button(result.wrapper, "按原操作号回查").trigger("click"); await flushPromises();
    expect(lookup).toHaveBeenCalledWith("CONFIRM", saved.key);
    expect(result.wrapper.text()).toContain("继续锁定");
    await button(result.wrapper, "按原操作号回查").trigger("click"); await flushPromises();
    expect(result.wrapper.text()).toContain("REVOKED");
    expect(window.sessionStorage.getItem(pendingKey)).not.toBeNull();
    await result.wrapper.get('section[aria-label="待核对集合操作"] input[type="checkbox"]').setValue(true);
    await button(result.wrapper, "清除本地待核对提醒").trigger("click");
    expect(window.sessionStorage.getItem(pendingKey)).toBeNull();
  });

  it("rechecks ordered sources after historical confirmation before explicit Create", async () => {
    const fingerprint = "f".repeat(64);
    const preview = vi.fn().mockResolvedValue({ source_fingerprint: fingerprint,
      document_refs: [{ document_id: documentA, document_version_id: versionA }],
      evidence_ids: [evidenceA, evidenceB], previewed_at: "2026-10-09T00:00:00Z" });
    const confirm = vi.fn().mockResolvedValue({ confirmation_id: trace,
      source_fingerprint: fingerprint, confirmed_by: actor,
      confirmed_at: "2026-10-09T00:00:00Z", expires_at: "2030-10-16T00:00:00Z",
      trace_id: trace });
    const create = vi.fn().mockResolvedValue({ reference_solution_id: trace,
      reference_version_id: documentA, scope: "GLOBAL", project_id: null,
      name: "合成参考", eligibility_state: "REFERENCE_ONLY", version_state: "DRAFT",
      created_by: actor, created_at: "2026-10-09T00:00:00Z", etag: '"v0"' });
    const result = await view(true, [{ items: [first, second], next_cursor: null,
      has_more: false }], "ELIGIBLE", { preview, confirm }, { create });
    for (const action of result.wrapper.findAll("button").filter((entry) =>
      entry.text() === "加入核查候选")) {
      await action.trigger("click"); await flushPromises();
    }
    await result.wrapper.find('input[placeholder="PLM"]').setValue("PLM");
    await result.wrapper.find('input[placeholder="DEIDENTIFIED"]').setValue("DEIDENTIFIED");
    await button(result.wrapper, "预览所选来源集合").trigger("click"); await flushPromises();
    const section = result.wrapper.get('section[aria-label="集合预览与逐项原文核查"]');
    for (const link of section.findAll("a")) await link.trigger("click");
    for (const checkbox of section.findAll('input[type="checkbox"]')) await checkbox.setValue(true);
    await button(result.wrapper, "提交集合人工脱敏确认（有效期 7 天）").trigger("click");
    await flushPromises();
    expect(result.wrapper.text()).toContain("本会话历史确认");
    await result.wrapper.find('input[placeholder="填写便于识别的参考名称"]').setValue("合成参考");
    await button(result.wrapper, "重新核验并创建全局参考方案").trigger("click");
    await flushPromises();
    expect(preview).toHaveBeenCalledTimes(2);
    expect(result.get).toHaveBeenCalledTimes(6);
    expect(result.currentGlobal).toHaveBeenCalledTimes(6);
    expect(create).toHaveBeenCalledOnce();
    expect(create.mock.calls[0]?.[0]).toEqual({ name: "合成参考",
      document_version_ids: [versionA], evidence_ids: [evidenceA, evidenceB],
      source_project_class: "PLM", deidentification_class: "DEIDENTIFIED", applicability: {} });
    expect(create.mock.calls[0]?.[1]).toMatch(/^[\x20-\x7e]{16,128}$/);
    expect(result.wrapper.text()).toContain("不是正式方案批准");
    expect(result.wrapper.get(`a[href="/admin/reference-solutions/${trace}"]`).text())
      .toContain("打开刚创建的参考方案详情");
    expect(window.sessionStorage.getItem(`plm.sol.global.create.pending.${actor}`)).toBeNull();
  });

  it("keeps an unknown Create locked under the original key", async () => {
    const fingerprint = "f".repeat(64);
    const preview = vi.fn().mockResolvedValue({ source_fingerprint: fingerprint,
      document_refs: [{ document_id: documentA, document_version_id: versionA }],
      evidence_ids: [evidenceA, evidenceB], previewed_at: "2026-10-09T00:00:00Z" });
    const confirm = vi.fn().mockResolvedValue({ confirmation_id: trace,
      source_fingerprint: fingerprint, confirmed_by: actor,
      confirmed_at: "2026-10-09T00:00:00Z", expires_at: "2030-10-16T00:00:00Z",
      trace_id: trace });
    const create = vi.fn().mockRejectedValue(new TypeError("response unknown"));
    const result = await view(true, [{ items: [first, second], next_cursor: null,
      has_more: false }], "ELIGIBLE", { preview, confirm }, { create });
    for (const action of result.wrapper.findAll("button").filter((entry) =>
      entry.text() === "加入核查候选")) {
      await action.trigger("click"); await flushPromises();
    }
    await result.wrapper.find('input[placeholder="PLM"]').setValue("PLM");
    await result.wrapper.find('input[placeholder="DEIDENTIFIED"]').setValue("DEIDENTIFIED");
    await button(result.wrapper, "预览所选来源集合").trigger("click"); await flushPromises();
    const section = result.wrapper.get('section[aria-label="集合预览与逐项原文核查"]');
    for (const link of section.findAll("a")) await link.trigger("click");
    for (const checkbox of section.findAll('input[type="checkbox"]')) await checkbox.setValue(true);
    await button(result.wrapper, "提交集合人工脱敏确认（有效期 7 天）").trigger("click");
    await flushPromises();
    await result.wrapper.find('input[placeholder="填写便于识别的参考名称"]').setValue("合成参考");
    await button(result.wrapper, "重新核验并创建全局参考方案").trigger("click");
    await flushPromises();
    const saved = JSON.parse(window.sessionStorage.getItem(
      `plm.sol.global.create.pending.${actor}`)!) as { key: string; request: string };
    expect(saved.key).toMatch(/^[\x20-\x7e]{16,128}$/);
    expect(JSON.parse(saved.request)).toHaveProperty("name", "合成参考");
    expect(result.wrapper.text()).toContain("创建结果尚待核对");
    expect(button(result.wrapper, "重新核验并创建全局参考方案").attributes("disabled"))
      .toBeDefined();
    expect(create).toHaveBeenCalledOnce();
  });
});
