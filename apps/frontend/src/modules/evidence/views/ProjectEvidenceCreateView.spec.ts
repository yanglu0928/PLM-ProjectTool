import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { DocumentReadClient } from "@/modules/document/api/documentReadClient";
import { ProjectEvidenceCreateClient, ProjectEvidenceCreateError } from "@/modules/evidence/api/projectEvidenceCreateClient";
import ProjectEvidenceCreateView from "./ProjectEvidenceCreateView.vue";

const actor = "01234567-89ab-4cde-8123-456789abcdef";
const project = "11234567-89ab-4cde-8123-456789abcdef";
const other = "21234567-89ab-4cde-8123-456789abcdef";
const document = "31234567-89ab-4cde-8123-456789abcdef";
const version = "41234567-89ab-4cde-8123-456789abcdef";
const evidence = "51234567-89ab-4cde-8123-456789abcdef";
const doc = { document_id: document, scope: "PROJECT" as const, category: "CONTRACTUAL" as const,
  subtype: null, title: "合成技术协议", display_name: "agreement.pdf", state: "ACTIVE" as const,
  latest_version_ref: version, effective_version_ref: version,
  created_at: "2026-10-25T01:00:00Z", etag: '"v0"' };
const fixed = { document_version_id: version, version_no: 1, content_sha256: "a".repeat(64),
  size_bytes: 99, detected_mime: "application/pdf", availability_state: "AVAILABLE" as const,
  supersedes_version_ref: null, created_at: "2026-10-25T01:00:00Z", integrity_checked_at: null };
const created = { evidence_id: evidence, document_id: document, document_version_id: version,
  locator: { locator_type: "DOCUMENT" as const }, display_label: "技术协议整文档依据",
  display_excerpt: null, content_fingerprint: "a".repeat(64), eligibility_state: "CANDIDATE" as const,
  created_at: "2026-10-25T01:00:00Z", etag: '"v0"' as const };
function response(data: unknown): Response { return new Response(JSON.stringify({ data, trace_id: actor }),
  { status: 200, headers: { "Content-Type": "application/json" } }); }
async function session(role = "PROJECT_MANAGER", login = true): Promise<SessionClient> {
  const result = new SessionClient(vi.fn().mockResolvedValue(response({ user: {
    user_id: actor, username_display: "合成用户" }, deployment_role: "NONE",
    password_change_required: false, authorized_projects: [{ project_id: project,
      name: "合成项目", role }], absolute_expires_at: "2030-01-01T12:00:00Z",
    idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "a".repeat(64) })) as typeof fetch);
  if (login) await result.login("synthetic", "synthetic-only"); return result;
}
function dependencies() {
  const list = vi.fn().mockResolvedValue({ items: [doc], next_cursor: null, has_more: false });
  const listVersions = vi.fn().mockResolvedValue({ items: [fixed], next_cursor: null, has_more: false });
  const create = vi.fn().mockResolvedValue(created);
  return { documents: { list, listVersions } as unknown as DocumentReadClient,
    creator: { create } as unknown as ProjectEvidenceCreateClient, list, listVersions, create };
}
async function view(auth: SessionClient, deps = dependencies(), projectId = project) {
  const router = createAppRouter(createMemoryHistory());
  await router.push(`/projects/${projectId}/evidence/new`); await router.isReady();
  const wrapper = mount(ProjectEvidenceCreateView, { props: { session: auth,
    documents: deps.documents, creator: deps.creator }, global: { plugins: [router] } });
  await flushPromises(); return { wrapper, router, ...deps };
}
async function select(result: Awaited<ReturnType<typeof view>>) {
  await result.wrapper.findAll("button").find(button => button.text() === "选择固定版本")!.trigger("click");
  await flushPromises();
  await result.wrapper.findAll("button").find(button => button.text() === "选用此版本")!.trigger("click");
  await flushPromises();
}
describe("ProjectEvidenceCreateView", () => {
  beforeEach(() => window.sessionStorage.clear());
  afterEach(() => { vi.restoreAllMocks(); window.sessionStorage.clear(); });
  it("keeps anonymous and non-editor accounts outside read and write", async () => {
    for (const auth of [await session("PROJECT_MANAGER", false), await session("CUSTOMER_MANAGER")]) {
      const result = await view(auth); expect(result.wrapper.find("form").exists()).toBe(false);
      expect(result.list).not.toHaveBeenCalled(); expect(result.create).not.toHaveBeenCalled();
      result.wrapper.unmount();
    }
  });
  it("chooses only current project AVAILABLE fixed document and creates a CANDIDATE", async () => {
    const result = await view(await session());
    expect(result.list).toHaveBeenCalledWith({ kind: "PROJECT", projectId: project }, null);
    await select(result); expect(result.listVersions).toHaveBeenCalledWith({ kind: "PROJECT", projectId: project }, document, null);
    await result.wrapper.get("#project-evidence-label").setValue("技术协议整文档依据");
    await result.wrapper.get('input[type="checkbox"]').setValue(true);
    await result.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(result.create).toHaveBeenCalledWith(project, { document_id: document, document_version_id: version,
      locator: { locator_type: "DOCUMENT" }, display_label: "技术协议整文档依据", display_excerpt: null },
    expect.any(String));
    expect(result.wrapper.text()).toContain("CANDIDATE，须人工核定为 ELIGIBLE");
    expect(window.sessionStorage.length).toBe(0); result.wrapper.unmount();
  });
  it("retains the exact input and key after uncertain response", async () => {
    const deps = dependencies(); deps.create.mockRejectedValueOnce(new ProjectEvidenceCreateError("EVIDENCE_CREATE_UNCERTAIN"));
    const result = await view(await session(), deps); await select(result);
    await result.wrapper.get("#project-evidence-label").setValue("技术协议整文档依据");
    await result.wrapper.get('input[type="checkbox"]').setValue(true);
    await result.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(window.sessionStorage.length).toBe(1);
    const first = result.create.mock.calls[0];
    expect(result.wrapper.get('button[type="submit"]').attributes("disabled")).toBeDefined();
    await result.wrapper.get('input[type="checkbox"]').setValue(true);
    await result.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(result.create.mock.calls[1]).toEqual(first);
    expect(window.sessionStorage.length).toBe(0); result.wrapper.unmount();
  });
  it("locks corrupt pending state and rejects empty or cross-project sources", async () => {
    window.sessionStorage.setItem(`plm.evidence.project.create.pending.${actor}.${project}`, "{broken");
    const locked = await view(await session());
    expect(locked.wrapper.get("[role=alert]").text()).toContain("无法安全读取");
    expect(locked.wrapper.get('button[type="submit"]').attributes("disabled")).toBeDefined();
    locked.wrapper.unmount(); window.sessionStorage.clear();
    const deps = dependencies(); deps.list.mockResolvedValueOnce({ items: [{ ...doc, scope: "GLOBAL" }],
      next_cursor: null, has_more: false });
    const filtered = await view(await session(), deps);
    expect(filtered.wrapper.text()).toContain("暂无可选的有效项目文档");
    expect(filtered.create).not.toHaveBeenCalled(); filtered.wrapper.unmount();
    const wrong = await view(await session(), dependencies(), other);
    expect(wrong.wrapper.find("form").exists()).toBe(false); wrong.wrapper.unmount();
  });
});
