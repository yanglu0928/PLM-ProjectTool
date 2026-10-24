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
async function view(admin = true) {
  const auth = await session(admin);
  const baselines = new CapabilityReadClient(vi.fn() as typeof fetch);
  const baseline = { baseline_id: baselineId, baseline_code: "CAP.SYNTHETIC", name: "合成能力基线",
    description: null, state: "ACTIVE" as const,
    source_collection_ref: await capabilitySourceCollectionRef([versionId]),
    current_approved_version_ref: null, created_at: "2026-10-24T01:00:00Z",
    updated_at: "2026-10-24T01:00:00Z", etag: '"v0"' };
  const getBaseline = vi.spyOn(baselines, "getBaseline").mockResolvedValue(baseline);
  const documents = new DocumentReadClient(vi.fn() as typeof fetch);
  vi.spyOn(documents, "list").mockResolvedValue({ items: [document], next_cursor: null, has_more: false });
  vi.spyOn(documents, "listVersions").mockResolvedValue({ items: [fixed], next_cursor: null, has_more: false });
  vi.spyOn(documents, "get").mockResolvedValue(document);
  vi.spyOn(documents, "getVersion").mockResolvedValue(fixed);
  const evidenceList = new EvidenceListClient(vi.fn() as typeof fetch);
  const listEvidence = vi.spyOn(evidenceList, "list").mockResolvedValue({ items: [evidence], next_cursor: null, has_more: false });
  const eligibility = new EvidenceEligibilityClient(auth, vi.fn() as typeof fetch);
  const current = vi.spyOn(eligibility, "currentGlobal").mockResolvedValue({
    evidence_id: evidenceId, document_id: documentId, document_version_id: versionId,
    eligibility_state: "ELIGIBLE", etag: '"v1"' });
  const creator = new CapabilityVersionCreateClient(auth);
  const create = vi.spyOn(creator, "create").mockResolvedValue({ baseline_version_id: newVersionId,
    baseline_id: baselineId, version_no: 1, state: "DRAFT", source_collection_ref: baseline.source_collection_ref,
    content_fingerprint: "b".repeat(64), supersedes_version_ref: null,
    created_at: "2026-10-24T01:00:00Z", baseline_etag: '"v1"' });
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
    await vi.waitFor(() => expect(result.wrapper.text()).toContain("原操作号与原条目已保留"));
    const first = result.create.mock.calls[0]!;
    await result.wrapper.get('input[type="checkbox"]').setValue(true);
    await result.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(result.create.mock.calls[1]).toEqual(first);
    result.wrapper.unmount();
  });
});
