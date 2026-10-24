import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { DocumentReadClient } from "@/modules/document/api/documentReadClient";
import { CapabilityReadClient } from "@/modules/capability/api/capabilityReadClient";
import { EvidenceListClient } from "@/modules/evidence/api/evidenceListClient";
import { EvidenceViewerClient } from "@/modules/evidence/api/evidenceViewerClient";
import { HandoverReadClient } from "@/modules/handover/api/handoverReadClient";
import { HandoverVersionCreateClient, HandoverVersionCreateError } from "@/modules/handover/api/handoverVersionCreateClient";
import ProjectHandoverVersionCreateView from "./ProjectHandoverVersionCreateView.vue";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const document = "11234567-89ab-4cde-8123-456789abcdef";
const documentVersion = "21234567-89ab-4cde-8123-456789abcdef";
const analysis = "31234567-89ab-4cde-8123-456789abcdef";
const actor = "41234567-89ab-4cde-8123-456789abcdef";
const evidenceId = "51234567-89ab-4cde-8123-456789abcdef";
const baselineId = "61234567-89ab-4cde-8123-456789abcdef";
const baselineVersionId = "71234567-89ab-4cde-8123-456789abcdef";
const versionId = "81234567-89ab-4cde-8123-456789abcdef";
const trace = "91234567-89ab-4cde-8123-456789abcdef";
const sourceRef = `sha256:${"aa".repeat(32)}`;
const doc = { document_id: document, title: "合成技术协议", state: "ACTIVE" };
const fixed = { document_version_id: documentVersion, version_no: 1, availability_state: "AVAILABLE" };
const baseline = { baseline_id: baselineId, name: "合成标准能力", state: "ACTIVE",
  current_approved_version_ref: baselineVersionId };
const capVersion = { baseline_version_id: baselineVersionId, baseline_id: baselineId,
  version_no: 1, state: "APPROVED" };
const evidence = { evidence_id: evidenceId, document_id: document, document_version_id: documentVersion,
  display_label: "协议原文定位", eligibility_state: "ELIGIBLE" };
function response(data: unknown) { return new Response(JSON.stringify({ data, trace_id: trace }),
  { headers: { "Content-Type": "application/json" } }); }
async function session(role = "PROJECT_MANAGER") {
  const api = new SessionClient(vi.fn().mockResolvedValue(response({
    user: { user_id: actor, username_display: "合成用户" }, deployment_role: "NONE",
    password_change_required: false, authorized_projects: [{ project_id: project, name: "合成项目", role }],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64),
  })) as typeof fetch);
  await api.login("synthetic", "synthetic-only"); return api;
}
function dependencies(match = true) {
  const getAnalysis = vi.fn().mockResolvedValue({ handover_analysis_id: analysis, project_id: project,
    analysis_purpose: "合成协议差异", state: "ACTIVE", etag: '"v0"',
    source_set_ref: match ? sourceRef : `sha256:${"bb".repeat(32)}` });
  const list = vi.fn().mockResolvedValue({ items: [doc], next_cursor: null, has_more: false });
  const listVersions = vi.fn().mockResolvedValue({ items: [fixed], next_cursor: null, has_more: false });
  const listBaselines = vi.fn().mockResolvedValue({ items: [baseline], next_cursor: null, has_more: false });
  const getBaseline = vi.fn().mockResolvedValue(baseline);
  const getVersion = vi.fn().mockResolvedValue(capVersion);
  const listItems = vi.fn().mockResolvedValue({ items: [], next_cursor: null, has_more: false });
  const listEvidence = vi.fn().mockResolvedValue({ items: [evidence], next_cursor: null, has_more: false });
  const locate = vi.fn().mockResolvedValue({ evidence_id: evidenceId, display_label: evidence.display_label,
    document_version_no: 1, content_url: "/api/v1/synthetic-content" });
  const create = vi.fn().mockResolvedValue({ handover_analysis_version_id: versionId });
  return { handover: { getAnalysis } as unknown as HandoverReadClient,
    documents: { list, listVersions } as unknown as DocumentReadClient,
    capabilities: { listBaselines, getBaseline, getVersion, listItems } as unknown as CapabilityReadClient,
    evidence: { list: listEvidence } as unknown as EvidenceListClient,
    viewer: { get: locate } as unknown as EvidenceViewerClient,
    creator: { create } as unknown as HandoverVersionCreateClient,
    getAnalysis, list, listVersions, listBaselines, listEvidence, locate, create };
}
async function view(auth: SessionClient, deps = dependencies()) {
  const router = createAppRouter(createMemoryHistory());
  await router.push(`/projects/${project}/handover/${analysis}/versions/new`); await router.isReady();
  const wrapper = mount(ProjectHandoverVersionCreateView, { props: { session: auth,
    handover: deps.handover, documents: deps.documents, capabilities: deps.capabilities,
    evidence: deps.evidence, viewer: deps.viewer, creator: deps.creator }, global: { plugins: [router] } });
  await flushPromises(); return { wrapper, router, ...deps };
}
function button(wrapper: Awaited<ReturnType<typeof view>>["wrapper"], label: string) {
  const found = wrapper.findAll("button").find(item => item.text().includes(label));
  if (!found) throw new Error(`missing button: ${label}`); return found;
}
async function selectSources(result: Awaited<ReturnType<typeof view>>) {
  await button(result.wrapper, "选择固定版本").trigger("click"); await flushPromises();
  await button(result.wrapper, "选用此固定版本").trigger("click"); await flushPromises();
  await button(result.wrapper, "选用已批准版").trigger("click"); await flushPromises();
  await result.wrapper.get("article.issue-card input[type=checkbox]").setValue(true);
}
async function fillCard(result: Awaited<ReturnType<typeof view>>) {
  await result.wrapper.get('input[placeholder="例如：物料编码映射规则待确认"]').setValue("接口差异候选");
  const areas = result.wrapper.findAll("article.issue-card textarea");
  await areas[0]!.setValue("经人工核对的合成差异"); await areas[1]!.setValue("需评估映射规则");
}

describe("ProjectHandoverVersionCreateView", () => {
  beforeEach(() => { window.sessionStorage.clear(); let uuidCounter = 0; vi.stubGlobal("crypto", {
    randomUUID: () => `${(++uuidCounter).toString(16).padStart(8, "0")}-89ab-4cde-8123-456789abcdef`,
    subtle: { digest: async () => Uint8Array.from(Array(32).fill(0xaa)).buffer },
  }); });
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); window.sessionStorage.clear(); });

  it("creates one grounded DRAFT card from matched fixed source, approved baseline and eligible project evidence", async () => {
    const result = await view(await session()); await selectSources(result); await fillCard(result);
    expect(result.wrapper.text()).toContain("固定来源与原分析完全匹配");
    await button(result.wrapper, "定位原文").trigger("click"); await flushPromises();
    expect(result.wrapper.text()).toContain("打开受权固定版本");
    await button(result.wrapper, "保存 DRAFT").trigger("click"); await flushPromises();
    expect(result.create).toHaveBeenCalledWith(project, analysis, '"v0"', expect.objectContaining({
      source_documents: [{ document_id: document, document_version_id: documentVersion }],
      capability_baseline_id: baselineId, capability_baseline_version_id: baselineVersionId,
      ai_task_refs: [], items: [expect.objectContaining({ item_type: "GAP", title: "接口差异候选",
        source_missing: false, evidence_refs: [evidenceId] })],
    }), expect.any(String));
    expect(result.router.currentRoute.value.name).toBe("project-handover-detail");
    expect(window.sessionStorage.length).toBe(0); result.wrapper.unmount();
  });

  it("does not permit a wrong fixed source or non-editor to write", async () => {
    const wrong = await view(await session(), dependencies(false));
    await selectSources(wrong); await fillCard(wrong);
    expect(wrong.wrapper.text()).toContain("所选固定来源与原分析不一致");
    expect(button(wrong.wrapper, "保存 DRAFT").attributes("disabled")).toBeDefined();
    expect(wrong.create).not.toHaveBeenCalled(); wrong.wrapper.unmount();
    const denied = await view(await session("CUSTOMER_MEMBER"));
    expect(denied.wrapper.text()).toContain("仅当前项目负责人或实施成员");
    expect(denied.getAnalysis).not.toHaveBeenCalled(); denied.wrapper.unmount();
  });

  it("requires concrete human-input guidance for NEED_CONFIRM and permits multiple grounded cards", async () => {
    const result = await view(await session()); await selectSources(result); await fillCard(result);
    await button(result.wrapper, "增加一张问题卡片").trigger("click");
    const second = result.wrapper.findAll("article.issue-card")[1]!;
    await second.get("select").setValue("NEED_CONFIRM");
    await second.get('input[placeholder="例如：物料编码映射规则待确认"]').setValue("编码规则待确认");
    const areas = second.findAll("textarea");
    await areas[0]!.setValue("合成调研尚无编码映射结论"); await areas[1]!.setValue("影响迁移范围");
    await areas[2]!.setValue("请客户确认编码映射方式");
    await areas[3]!.setValue("历史编码应如何处理？");
    await second.get('input[placeholder="例如：旧编码、新编码、映射负责人"]').setValue("旧编码和新编码");
    await second.get('input[placeholder="例如：两列编码对照表"]').setValue("两列编码表");
    await second.get('input[placeholder="例如：OLD-001 → NEW-001（仅示例）"]').setValue("OLD-001 → NEW-001");
    await second.get('input[placeholder="例如：沿用旧编码并建立映射"]').setValue("沿用旧编码");
    await second.get('input[placeholder="例如：统一切换新编码"]').setValue("统一新编码");
    await second.get("input[type=checkbox]").setValue(true);
    await button(result.wrapper, "保存 DRAFT").trigger("click"); await flushPromises();
    const input = result.create.mock.calls[0]![3];
    expect(input.items).toHaveLength(2);
    expect(input.items[0].analysis_item_id).not.toBe(input.items[1].analysis_item_id);
    expect(input.items[1]).toMatchObject({ item_type: "NEED_CONFIRM", source_missing: false,
      evidence_refs: [evidenceId], required_input_spec: { fields: [{ name: "旧编码和新编码",
        format: "两列编码表", example: "OLD-001 → NEW-001", required: true }] },
      options: [{ option_code: "A", label: "沿用旧编码", description: null },
        { option_code: "B", label: "统一新编码", description: null }] });
    result.wrapper.unmount();
  });

  it("preserves exact original Key/body/ETag on uncertainty and deliberate retry", async () => {
    const deps = dependencies(); deps.create.mockRejectedValueOnce(new HandoverVersionCreateError("HANDOVER_VERSION_UNCERTAIN"));
    const result = await view(await session(), deps); await selectSources(result); await fillCard(result);
    await button(result.wrapper, "保存 DRAFT").trigger("click"); await flushPromises();
    expect(result.create).toHaveBeenCalledTimes(1); expect(window.sessionStorage.length).toBe(1);
    const first = result.create.mock.calls[0]!;
    expect(button(result.wrapper, "按原操作重试").attributes("disabled")).toBeDefined();
    await result.wrapper.findAll("input[type=checkbox]").at(-1)!.setValue(true);
    await button(result.wrapper, "按原操作重试").trigger("click"); await flushPromises();
    expect(result.create.mock.calls[1]).toEqual(first);
    expect(window.sessionStorage.length).toBe(0); result.wrapper.unmount();
  });

  it("locks corrupted persisted command instead of issuing a fresh Key", async () => {
    window.sessionStorage.setItem(`plm.hnd.version.create.pending.${actor}.${project}.${analysis}`, "{broken");
    const result = await view(await session());
    expect(result.wrapper.text()).toContain("原操作记录损坏");
    expect(button(result.wrapper, "保存 DRAFT").attributes("disabled")).toBeDefined();
    expect(result.create).not.toHaveBeenCalled(); result.wrapper.unmount();
  });
});
