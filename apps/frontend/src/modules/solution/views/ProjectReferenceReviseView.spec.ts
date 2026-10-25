import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import type { ReferenceReadClient } from "@/modules/solution/api/referenceReadClient";
import type { DocumentReadClient } from "@/modules/document/api/documentReadClient";
import type { EvidenceListClient } from "@/modules/evidence/api/evidenceListClient";
import type { EvidenceViewerClient } from "@/modules/evidence/api/evidenceViewerClient";
import type { EvidenceEligibilityClient } from "@/modules/evidence/api/evidenceEligibilityClient";
import type { ReferenceReviseClient } from "@/modules/solution/api/referenceReviseClient";
import ProjectReferenceReviseView from "./ProjectReferenceReviseView.vue";

const actor = "01234567-89ab-4cde-8123-456789abcdef";
const project = "11234567-89ab-4cde-8123-456789abcdef";
const root = "21234567-89ab-4cde-8123-456789abcdef";
const prior = "31234567-89ab-4cde-8123-456789abcdef";
const document = "41234567-89ab-4cde-8123-456789abcdef";
const version = "51234567-89ab-4cde-8123-456789abcdef";
const newVersion = "61234567-89ab-4cde-8123-456789abcdef";
const evidence = "71234567-89ab-4cde-8123-456789abcdef";
const date = "2026-10-09T00:00:00Z";
const current = { reference_solution_id: root, reference_version_id: prior, scope: "PROJECT",
  project_id: project, name: "项目参考方案", eligibility_state: "REFERENCE_ONLY",
  version_no: 1, version_state: "DRAFT", created_at: date, etag: '"v0"',
  eligibility_reason: null, source_project_class: "PLM", deidentification_class: "PROJECT_INTERNAL",
  applicability: {}, document_version_ids: [version], document_refs: [{ document_id: document,
    document_version_id: version }], evidence_ids: [], source_fingerprint: "a".repeat(64),
  content_fingerprint: "b".repeat(64), created_by: actor, version_created_by: actor,
  version_created_at: date };
const candidate = { document_id: document, scope: "PROJECT", category: "PROJECT_RECORD",
  subtype: null, title: "调研记录", display_name: "调研记录.pdf", state: "ACTIVE",
  latest_version_ref: version, effective_version_ref: version, created_at: date, etag: '"v0"' };
const fixed = { document_version_id: version, version_no: 1, content_sha256: "c".repeat(64),
  size_bytes: 10, detected_mime: "application/pdf", availability_state: "AVAILABLE",
  supersedes_version_ref: null, created_at: date, integrity_checked_at: date };
const revised = { reference_solution_id: root, reference_version_id: newVersion,
  scope: "PROJECT", project_id: project, version_no: 2, version_state: "DRAFT",
  supersedes_version_ref: prior, created_at: date, etag: '"v1"' };
const evidenceItem = { evidence_id: evidence, document_id: document, document_version_id: version,
  display_label: "第三页证据", display_excerpt: null, eligibility_state: "ELIGIBLE", created_at: date };
const viewer = { evidence_id: evidence, document_id: document, document_version_id: version,
  document_version_no: 1, detected_mime: "application/pdf", size_bytes: 10,
  locator: { locator_type: "PAGE", page_no: 3 }, precision: "PARSED_NODE",
  display_label: "第三页证据", short_preview: null,
  content_url: `/api/v1/projects/${project}/evidence/${evidence}/content` };
async function session(role = "PROJECT_MANAGER") {
  const api = new SessionClient(vi.fn().mockResolvedValue(new Response(JSON.stringify({ data: {
    user: { user_id: actor, username_display: "合成用户" }, deployment_role: "NONE",
    password_change_required: false, authorized_projects: [{ project_id: project, name: "项目", role }],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64),
  }, trace_id: actor }), { status: 200, headers: { "Content-Type": "application/json" } })) as typeof fetch);
  await api.login("user", "synthetic-only"); return api;
}
async function page(role = "PROJECT_MANAGER", overrides: { root?: ReturnType<typeof vi.fn>;
  revise?: ReturnType<typeof vi.fn>; evidenceItems?: unknown[];
  currentEligibility?: ReturnType<typeof vi.fn> } = {}) {
  const router = createAppRouter(createMemoryHistory());
  await router.push(`/projects/${project}/reference-solutions/${root}/revise`); await router.isReady();
  const rootRead = overrides.root ?? vi.fn().mockResolvedValue(current);
  const revise = overrides.revise ?? vi.fn().mockResolvedValue(revised);
  const documents = { list: vi.fn().mockResolvedValue({ items: [candidate], next_cursor: null, has_more: false }),
    listVersions: vi.fn().mockResolvedValue({ items: [fixed], next_cursor: null, has_more: false }),
    get: vi.fn().mockResolvedValue(candidate), getVersion: vi.fn().mockResolvedValue(fixed) };
  const evidences = { list: vi.fn().mockResolvedValue({ items: overrides.evidenceItems ?? [], next_cursor: null, has_more: false }) };
  const viewers = { get: vi.fn().mockResolvedValue(viewer) };
  const eligibility = { current: overrides.currentEligibility ?? vi.fn().mockResolvedValue({
    evidence_id: evidence, document_id: document, document_version_id: version,
    eligibility_state: "ELIGIBLE", etag: '"v0"' }) };
  const wrapper = mount(ProjectReferenceReviseView, { props: {
    session: await session(role), reader: { current: rootRead } as unknown as ReferenceReadClient,
    documents: documents as unknown as DocumentReadClient,
    evidences: evidences as unknown as EvidenceListClient,
    viewers: viewers as unknown as EvidenceViewerClient,
    eligibility: eligibility as unknown as EvidenceEligibilityClient,
    revises: { revise } as unknown as ReferenceReviseClient,
  }, global: { plugins: [router] } });
  await flushPromises(); return { wrapper, router, rootRead, revise, documents, evidences, viewers, eligibility };
}
async function selectDocument(wrapper: Awaited<ReturnType<typeof page>>["wrapper"]) {
  const button = (label: string) => wrapper.findAll("button").find(item => item.text() === label)!;
  await button("读取项目文档候选").trigger("click"); await flushPromises();
  await button("查看可用版本").trigger("click"); await flushPromises();
  await button("选择此版本").trigger("click"); await flushPromises();
}
async function reviewSelected(wrapper: Awaited<ReturnType<typeof page>>["wrapper"], withEvidence = false) {
  await wrapper.get(`input[type=checkbox][value="${version}"]`).setValue(true);
  if (withEvidence) await wrapper.get(`input[type=checkbox][value="${evidence}"]`).setValue(true);
  await wrapper.findAll("input[type=checkbox]").at(-1)!.setValue(true);
}
describe("ProjectReferenceReviseView", () => {
  afterEach(() => { window.sessionStorage.clear(); vi.restoreAllMocks(); });
  it("gates customer role and exposes route without reading sources", async () => {
    const denied = await page("CUSTOMER_MEMBER");
    expect(denied.router.currentRoute.value.name).toBe("project-reference-revise");
    expect(denied.wrapper.text()).toContain("仅项目经理或实施成员");
    expect(denied.rootRead).not.toHaveBeenCalled();
    expect(denied.documents.list).not.toHaveBeenCalled(); denied.wrapper.unmount();
  });
  it("selects a named fixed document version without evidence and rechecks before one write", async () => {
    const view = await page();
    await selectDocument(view.wrapper);
    expect(view.wrapper.text()).toContain("调研记录");
    expect(view.wrapper.findAll("input").every(input => input.attributes("placeholder") !== "UUID")).toBe(true);
    expect(view.wrapper.findAll("button").find(item => item.text() === "重新核验并修订")!.attributes("disabled"))
      .toBeDefined();
    await reviewSelected(view.wrapper);
    await view.wrapper.findAll("button").find(item => item.text() === "重新核验并修订")!.trigger("click");
    await flushPromises();
    expect(view.rootRead).toHaveBeenCalledTimes(3); // initial, pre-submit, post-submit current
    expect(view.revise).toHaveBeenCalledExactlyOnceWith("PROJECT", root, project,
      { document_version_ids: [version], evidence_ids: [], source_project_class: "PLM",
        deidentification_class: "PROJECT_INTERNAL", applicability: {} }, '"v0"', expect.any(String));
    expect(view.wrapper.text()).toContain("首次结果快照");
    expect(view.wrapper.text()).toContain("当前 ETag");
    expect(window.sessionStorage.length).toBe(0); view.wrapper.unmount();
  });
  it("keeps uncertain original body, If-Match and key for explicit same-key recovery", async () => {
    const revise = vi.fn().mockRejectedValueOnce(new Error("网络结果不确定")).mockResolvedValueOnce(revised);
    const first = await page("PROJECT_MANAGER", { revise });
    await selectDocument(first.wrapper); await reviewSelected(first.wrapper);
    await first.wrapper.findAll("button").find(item => item.text() === "重新核验并修订")!.trigger("click");
    await flushPromises();
    expect(first.wrapper.text()).toContain("上次修订结果待核对");
    const original = revise.mock.calls[0]; expect(window.sessionStorage.length).toBe(1);
    first.wrapper.unmount();
    const second = await page("PROJECT_MANAGER", { revise });
    expect(second.wrapper.findAll("button").find(item => item.text() === "重新核验并修订")!.attributes("disabled")).toBeDefined();
    await second.wrapper.findAll("button").find(item => item.text() === "同键恢复原操作")!.trigger("click");
    await flushPromises();
    expect(revise.mock.calls[1]).toEqual(original);
    expect(window.sessionStorage.length).toBe(0); second.wrapper.unmount();
  });
  it("accepts valid Chinese project classifications supported by the frozen API", async () => {
    const view = await page(); await selectDocument(view.wrapper);
    await view.wrapper.get('input[placeholder="PLM"]').setValue("离散制造");
    await view.wrapper.get('input[placeholder="PROJECT_INTERNAL"]').setValue("项目内部");
    await reviewSelected(view.wrapper);
    await view.wrapper.findAll("button").find(item => item.text() === "重新核验并修订")!.trigger("click");
    await flushPromises();
    expect(view.revise.mock.calls[0]?.[3]).toMatchObject({ source_project_class: "离散制造",
      deidentification_class: "项目内部" });
    view.wrapper.unmount();
  });
  it("rejects stale root before allocating a key or posting", async () => {
    const rootRead = vi.fn().mockResolvedValueOnce(current).mockResolvedValueOnce({ ...current, etag: '"v1"' });
    const view = await page("PROJECT_MANAGER", { root: rootRead });
    await selectDocument(view.wrapper); await reviewSelected(view.wrapper);
    await view.wrapper.findAll("button").find(item => item.text() === "重新核验并修订")!.trigger("click");
    await flushPromises();
    expect(view.wrapper.text()).toContain("当前参考版本已变化");
    expect(view.revise).not.toHaveBeenCalled();
    expect(window.sessionStorage.length).toBe(0); view.wrapper.unmount();
  });
  it("allows only selected-version eligible evidence and rechecks it before POST", async () => {
    const wrong = { ...evidenceItem, evidence_id: "81234567-89ab-4cde-8123-456789abcdef",
      document_version_id: newVersion };
    const view = await page("IMPLEMENTATION_MEMBER", { evidenceItems: [wrong, evidenceItem] });
    await selectDocument(view.wrapper);
    await view.wrapper.findAll("button").find(item => item.text() === "读取项目证据")!.trigger("click");
    await flushPromises();
    const buttons = view.wrapper.findAll("button").filter(item => item.text() === "核验并加入");
    expect(buttons[0]?.attributes("disabled")).toBeDefined();
    await buttons[1]!.trigger("click"); await flushPromises();
    expect(view.viewers.get).toHaveBeenCalledWith({ kind: "PROJECT", projectId: project }, evidence);
    await reviewSelected(view.wrapper, true);
    await view.wrapper.findAll("button").find(item => item.text() === "重新核验并修订")!.trigger("click");
    await flushPromises();
    expect(view.revise.mock.calls[0]?.[3]).toMatchObject({ evidence_ids: [evidence] });
    expect(view.eligibility.current).toHaveBeenCalledTimes(2);
    view.wrapper.unmount();
  });
  it("fails closed for damaged pending storage", async () => {
    window.sessionStorage.setItem(`plm.sol.project.reference.revise.pending.${actor}.${project}.${root}`, "corrupt");
    const view = await page();
    expect(view.wrapper.text()).toContain("本地操作记录损坏");
    expect(view.wrapper.findAll("button").find(item => item.text() === "重新核验并修订")!.attributes("disabled"))
      .toBeDefined();
    expect(view.revise).not.toHaveBeenCalled(); view.wrapper.unmount();
  });
});
