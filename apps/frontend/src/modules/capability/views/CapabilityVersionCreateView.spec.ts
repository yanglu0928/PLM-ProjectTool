import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { DocumentReadClient } from "@/modules/document/api/documentReadClient";
import { EvidenceListClient } from "@/modules/evidence/api/evidenceListClient";
import { EvidenceEligibilityClient } from "@/modules/evidence/api/evidenceEligibilityClient";
import { CapabilityReadClient } from "@/modules/capability/api/capabilityReadClient";
import { CapabilityVersionCreateClient, CapabilityVersionCreateError } from "@/modules/capability/api/capabilityVersionCreateClient";
import { capabilitySourceCollectionRef } from "@/modules/capability/api/capabilitySourceCollection";
import CapabilityVersionCreateView from "./CapabilityVersionCreateView.vue";

const actor = "01234567-89ab-4cde-8123-456789abcdef";
const baselineId = "11234567-89ab-4cde-8123-456789abcdef";
const documentId = "21234567-89ab-4cde-8123-456789abcdef";
const versionId = "31234567-89ab-4cde-8123-456789abcdef";
const evidenceId = "41234567-89ab-4cde-8123-456789abcdef";
const newVersionId = "51234567-89ab-4cde-8123-456789abcdef";
const documentId2 = "61234567-89ab-4cde-8123-456789abcdef";
const versionId2 = "71234567-89ab-4cde-8123-456789abcdef";
const evidenceId2 = "81234567-89ab-4cde-8123-456789abcdef";
const document = { document_id: documentId, scope: "GLOBAL" as const,
  category: "STANDARD_CAPABILITY" as const, subtype: null, title: "合成能力来源",
  display_name: "source.txt", state: "ACTIVE" as const, latest_version_ref: versionId,
  effective_version_ref: versionId, created_at: "2026-10-24T01:00:00Z", etag: '"v0"' };
const fixed = { document_version_id: versionId, version_no: 1, content_sha256: "a".repeat(64),
  size_bytes: 99, detected_mime: "text/plain", availability_state: "AVAILABLE" as const,
  supersedes_version_ref: null, created_at: "2026-10-24T01:00:00Z", integrity_checked_at: null };
const evidence = { evidence_id: evidenceId, document_id: documentId, document_version_id: versionId,
  display_label: "已确认同源证据", display_excerpt: null, eligibility_state: "ELIGIBLE" as const,
  created_at: "2026-10-24T01:00:00Z" };
const document2 = { ...document, document_id: documentId2, title: "第二份合成来源",
  latest_version_ref: versionId2, effective_version_ref: versionId2 };
const fixed2 = { ...fixed, document_version_id: versionId2 };
const evidence2 = { ...evidence, evidence_id: evidenceId2, document_id: documentId2,
  document_version_id: versionId2, display_label: "第二份同源证据" };
function response(data: unknown): Response { return new Response(JSON.stringify({ data, trace_id: actor }),
  { status: 200, headers: { "Content-Type": "application/json" } }); }
async function session(admin: boolean): Promise<SessionClient> {
  const auth = new SessionClient(vi.fn().mockResolvedValue(response({ user: {
    user_id: actor, username_display: "合成用户" }, deployment_role: admin ? "DEPLOYMENT_ADMIN" : "NONE",
    password_change_required: false, authorized_projects: admin ? [] : [{ project_id: baselineId,
      name: "合成项目", role: "PROJECT_MANAGER" }], absolute_expires_at: "2030-01-01T12:00:00Z",
    idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "a".repeat(64) })) as typeof fetch);
  await auth.login("synthetic", "synthetic-only"); return auth;
}
async function view(admin = true, multi = false, legacy = false) {
  const auth = await session(admin);
  const baselines = new CapabilityReadClient(vi.fn() as typeof fetch);
  const baseline = { baseline_id: baselineId, baseline_code: "CAP.SYNTHETIC", name: "合成能力基线",
    description: null, state: "ACTIVE" as const,
    source_collection_ref: await capabilitySourceCollectionRef(multi ? [versionId, versionId2] : [versionId]),
    current_approved_version_ref: null, created_at: "2026-10-24T01:00:00Z",
    updated_at: "2026-10-24T01:00:00Z", etag: '"v0"' };
  const getBaseline = vi.spyOn(baselines, "getBaseline").mockResolvedValue(baseline);
  const documents = new DocumentReadClient(vi.fn() as typeof fetch);
  vi.spyOn(documents, "list").mockResolvedValue({ items: multi ? [document, document2] : [document],
    next_cursor: null, has_more: false });
  vi.spyOn(documents, "listVersions").mockImplementation(async (_scope, id) => ({
    items: [id === documentId2 ? fixed2 : fixed], next_cursor: null, has_more: false }));
  vi.spyOn(documents, "get").mockImplementation(async (_scope, id) => id === documentId2 ? document2 : document);
  vi.spyOn(documents, "getVersion").mockImplementation(async (_scope, id) => id === documentId2 ? fixed2 : fixed);
  const evidenceList = new EvidenceListClient(vi.fn() as typeof fetch);
  const listEvidence = vi.spyOn(evidenceList, "list").mockResolvedValue({
    items: multi ? [evidence, evidence2] : [evidence], next_cursor: null, has_more: false });
  const eligibility = new EvidenceEligibilityClient(auth, vi.fn() as typeof fetch);
  const current = vi.spyOn(eligibility, "currentGlobal").mockImplementation(async id => ({
    evidence_id: id, document_id: id === evidenceId2 ? documentId2 : documentId,
    document_version_id: id === evidenceId2 ? versionId2 : versionId,
    eligibility_state: "ELIGIBLE", etag: '"v1"' }));
  const creator = new CapabilityVersionCreateClient(auth);
  const create = vi.spyOn(creator, "create").mockResolvedValue({ baseline_version_id: newVersionId,
    baseline_id: baselineId, version_no: 1, state: "DRAFT", source_collection_ref: baseline.source_collection_ref,
    content_fingerprint: "b".repeat(64), supersedes_version_ref: null,
    created_at: "2026-10-24T01:00:00Z", baseline_etag: '"v1"' });
  if (legacy) window.sessionStorage.setItem(`plm.cap.version.create.pending.${actor}.${baselineId}`,
    JSON.stringify({ actor, baselineId, etag: '"v0"', key: "legacy-synthetic-key-001",
      item: { stable_item_id: "91234567-89ab-4cde-8123-456789abcdef", capability_code: "CAP.LEGACY",
        domain_name: "PLM", module_name: "Core", feature_name: "Legacy", name: "Legacy capability",
        description: "Synthetic legacy record", boundary: "Synthetic only", prerequisites: [],
        interface_refs: [], document_refs: [{ document_id: documentId, document_version_id: versionId }],
        evidence_refs: [evidenceId], item_state: "AVAILABLE" } }));
  const router = createAppRouter(createMemoryHistory());
  await router.push(`/admin/capability-baselines/${baselineId}/versions/new`); await router.isReady();
  const wrapper = mount(CapabilityVersionCreateView, { props: { session: auth, baselines, documents,
    evidence: evidenceList, eligibility, creator }, global: { plugins: [router] } });
  await flushPromises();
  return { wrapper, router, create, current, getBaseline, listEvidence };
}
async function fill(result: Awaited<ReturnType<typeof view>>) {
  const button = (label: string) => result.wrapper.findAll("button").find(item => item.text() === label)!;
  await button("选择版本").trigger("click"); await flushPromises();
  await button("选用此固定版本").trigger("click"); await flushPromises();
  await result.wrapper.get('input[type="checkbox"]').setValue(true);
  await result.wrapper.get("#cap-code").setValue("cap.item");
  await result.wrapper.get("#cap-domain").setValue("PLM");
  await result.wrapper.get("#cap-module").setValue("Core");
  await result.wrapper.get("#cap-feature").setValue("Identity");
  await result.wrapper.get("#cap-name").setValue("Identity");
  await result.wrapper.get("#cap-description").setValue("Synthetic capability");
  await result.wrapper.get("#cap-boundary").setValue("Synthetic only");
  await result.wrapper.findAll('input[type="checkbox"]')[1]!.setValue(true);
}
async function fillSecond(result: Awaited<ReturnType<typeof view>>, code = "cap.second") {
  const button = (label: string) => result.wrapper.findAll("button").find(item => item.text() === label)!;
  await result.wrapper.findAll("button").filter(item => item.text() === "选择版本")[1]!.trigger("click");
  await flushPromises();
  await button("选用此固定版本").trigger("click"); await flushPromises();
  await result.wrapper.get('input[type="checkbox"]').setValue(true);
  await result.wrapper.get("#cap-code").setValue(code);
  await result.wrapper.get("#cap-domain").setValue("PLM");
  await result.wrapper.get("#cap-module").setValue("Core");
  await result.wrapper.get("#cap-feature").setValue("Second");
  await result.wrapper.get("#cap-name").setValue("Second capability");
  await result.wrapper.get("#cap-description").setValue("Second synthetic capability");
  await result.wrapper.get("#cap-boundary").setValue("Synthetic only");
  await result.wrapper.get("#cap-state").setValue("DEPRECATED");
}
describe("CapabilityVersionCreateView", () => {
  afterEach(() => { vi.restoreAllMocks(); window.sessionStorage.clear(); });
  it("blocks ordinary project members before reading GLOBAL sources", async () => {
    const result = await view(false);
    expect(result.wrapper.find("form").exists()).toBe(false);
    expect(result.getBaseline).not.toHaveBeenCalled();
    expect(result.listEvidence).not.toHaveBeenCalled();
    result.wrapper.unmount();
  });
  it("creates one DRAFT from the complete baseline source and current ELIGIBLE evidence", async () => {
    const result = await view(); await fill(result);
    expect(result.wrapper.get('button[type="submit"]').attributes("disabled")).toBeUndefined();
    await result.wrapper.get("form").trigger("submit"); await flushPromises();
    await vi.waitFor(() => expect(result.current).toHaveBeenCalledWith(evidenceId));
    await vi.waitFor(() => expect(result.create).toHaveBeenCalledOnce());
    expect(result.create).toHaveBeenCalledOnce();
    const [id, etag, items, key] = result.create.mock.calls[0]!;
    expect(id).toBe(baselineId); expect(etag).toBe('"v0"'); expect(key).toMatch(/^[0-9a-f-]{36}$/);
    expect(items[0]).toMatchObject({ capability_code: "CAP.ITEM", item_state: "AVAILABLE",
      document_refs: [{ document_id: documentId, document_version_id: versionId }],
      evidence_refs: [evidenceId] });
    expect(result.router.currentRoute.value.name).toBe("capability-baseline-detail");
    result.wrapper.unmount();
  });
  it("rejects a stale qualification before sending the version command", async () => {
    const result = await view(); await fill(result);
    expect(result.wrapper.get('button[type="submit"]').attributes("disabled")).toBeUndefined();
    result.current.mockResolvedValueOnce({ evidence_id: evidenceId, document_id: documentId,
      document_version_id: versionId, eligibility_state: "REVOKED", etag: '"v2"' });
    await result.wrapper.get("form").trigger("submit"); await flushPromises();
    await vi.waitFor(() => expect(result.wrapper.text()).toContain("证据资格或同源关系已变化"));
    expect(result.create).not.toHaveBeenCalled();
    result.wrapper.unmount();
  });
  it("rejects an incomplete fixed source collection before sending the version command", async () => {
    const result = await view(); await fill(result);
    const original = await result.getBaseline.mock.results[0]!.value;
    result.getBaseline.mockResolvedValueOnce({ ...original, source_collection_ref: `sha256:${"0".repeat(64)}` });
    await result.wrapper.get("form").trigger("submit"); await flushPromises();
    await vi.waitFor(() => expect(result.wrapper.text()).toContain("固定来源与基线来源集合不一致"));
    expect(result.create).not.toHaveBeenCalled();
    result.wrapper.unmount();
  });
  it("retains the original body, ETag and key after an uncertain response", async () => {
    const result = await view(); await fill(result);
    result.create.mockRejectedValueOnce(new CapabilityVersionCreateError("CAP_VERSION_UNCERTAIN"));
    await result.wrapper.get("form").trigger("submit"); await flushPromises();
    await vi.waitFor(() => expect(result.wrapper.text()).toContain("原操作号与原条目清单已保留"));
    const first = result.create.mock.calls[0]!;
    await result.wrapper.get('input[type="checkbox"]').setValue(true);
    await result.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(result.create.mock.calls[1]).toEqual(first);
    result.wrapper.unmount();
  });
  it("creates two independent source/evidence items and preserves their batch for retry", async () => {
    const result = await view(true, true); await fill(result);
    await result.wrapper.findAll("button").find(button => button.text() === "加入条目清单")!.trigger("click");
    expect(result.wrapper.get('[aria-label="已加入能力条目"]').text()).toContain("CAP.ITEM");
    await fillSecond(result);
    await result.wrapper.findAll("button").find(button => button.text() === "加入条目清单")!.trigger("click");
    expect(result.wrapper.get('[aria-label="已加入能力条目"]').findAll("li")).toHaveLength(2);
    await result.wrapper.get('input[type="checkbox"]').setValue(true);
    result.create.mockRejectedValueOnce(new CapabilityVersionCreateError("CAP_VERSION_UNCERTAIN"));
    await result.wrapper.get("form").trigger("submit"); await flushPromises();
    await vi.waitFor(() => expect(result.create).toHaveBeenCalledOnce());
    const first = result.create.mock.calls[0]!;
    expect(first[2]).toHaveLength(2);
    expect(first[2][0]).toMatchObject({ capability_code: "CAP.ITEM", item_state: "AVAILABLE",
      document_refs: [{ document_id: documentId, document_version_id: versionId }], evidence_refs: [evidenceId] });
    expect(first[2][1]).toMatchObject({ capability_code: "CAP.SECOND", item_state: "DEPRECATED",
      document_refs: [{ document_id: documentId2, document_version_id: versionId2 }], evidence_refs: [evidenceId2] });
    await result.wrapper.get('input[type="checkbox"]').setValue(true);
    await result.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(result.create.mock.calls[1]).toEqual(first);
    result.wrapper.unmount();
  });
  it("rejects an incomplete source union and never omits an unfinished current item", async () => {
    const result = await view(true, true); await fill(result);
    await result.wrapper.findAll("button").find(button => button.text() === "加入条目清单")!.trigger("click");
    await result.wrapper.get('input[type="checkbox"]').setValue(true);
    await result.wrapper.get("form").trigger("submit"); await flushPromises();
    await vi.waitFor(() => expect(result.wrapper.text()).toContain("固定来源与基线来源集合不一致"));
    expect(result.create).not.toHaveBeenCalled();
    await result.wrapper.get("#cap-code").setValue("unfinished");
    await result.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(result.wrapper.text()).toContain("当前条目尚未加入清单");
    expect(result.create).not.toHaveBeenCalled();
    result.wrapper.unmount();
  });
  it("rejects duplicate codes across items before any server write", async () => {
    const result = await view(true, true); await fill(result);
    await result.wrapper.findAll("button").find(button => button.text() === "加入条目清单")!.trigger("click");
    await fillSecond(result, "cap.item");
    await result.wrapper.findAll("button").find(button => button.text() === "加入条目清单")!.trigger("click");
    expect(result.wrapper.get('[aria-label="已加入能力条目"]').findAll("li")).toHaveLength(1);
    expect(result.wrapper.text()).toContain("请核对基线版本条目");
    expect(result.create).not.toHaveBeenCalled();
    result.wrapper.unmount();
  });
  it("restores a legacy one-item pending operation without changing its key or body", async () => {
    const result = await view(true, false, true);
    expect(result.wrapper.text()).toContain("原操作号与原条目清单已保留");
    await result.wrapper.get('input[type="checkbox"]').setValue(true);
    await result.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(result.create).toHaveBeenCalledOnce();
    expect(result.create.mock.calls[0]?.[2][0]?.capability_code).toBe("CAP.LEGACY");
    expect(result.create.mock.calls[0]?.[3]).toBe("legacy-synthetic-key-001");
    result.wrapper.unmount();
  });
  it("rechecks every item evidence and blocks a revoked second source", async () => {
    const result = await view(true, true); await fill(result);
    await result.wrapper.findAll("button").find(button => button.text() === "加入条目清单")!.trigger("click");
    await fillSecond(result);
    await result.wrapper.findAll("button").find(button => button.text() === "加入条目清单")!.trigger("click");
    result.current.mockImplementation(async id => ({ evidence_id: id,
      document_id: id === evidenceId2 ? documentId2 : documentId,
      document_version_id: id === evidenceId2 ? versionId2 : versionId,
      eligibility_state: id === evidenceId2 ? "REVOKED" : "ELIGIBLE", etag: '"v2"' }));
    await result.wrapper.get('input[type="checkbox"]').setValue(true);
    await result.wrapper.get("form").trigger("submit"); await flushPromises();
    await vi.waitFor(() => expect(result.wrapper.text()).toContain("证据资格或同源关系已变化"));
    expect(result.create).not.toHaveBeenCalled();
    result.wrapper.unmount();
  });
});
