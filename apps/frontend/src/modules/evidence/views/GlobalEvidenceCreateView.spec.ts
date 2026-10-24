import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { DocumentReadClient } from "@/modules/document/api/documentReadClient";
import { GlobalEvidenceCreateClient, GlobalEvidenceCreateError } from "@/modules/evidence/api/globalEvidenceCreateClient";
import GlobalEvidenceCreateView from "./GlobalEvidenceCreateView.vue";

const actor = "01234567-89ab-4cde-8123-456789abcdef";
const document = "21234567-89ab-4cde-8123-456789abcdef";
const version = "31234567-89ab-4cde-8123-456789abcdef";
const evidence = "41234567-89ab-4cde-8123-456789abcdef";
const candidate = { document_id: document, scope: "GLOBAL" as const,
  category: "STANDARD_CAPABILITY" as const, subtype: null, title: "标准能力资料",
  display_name: "standard.pdf", state: "ACTIVE" as const, latest_version_ref: version,
  effective_version_ref: version, created_at: "2026-10-24T01:00:00Z", etag: '"v0"' };
const fixed = { document_version_id: version, version_no: 1, content_sha256: "a".repeat(64),
  size_bytes: 99, detected_mime: "application/pdf", availability_state: "AVAILABLE" as const,
  supersedes_version_ref: null, created_at: "2026-10-24T01:00:00Z", integrity_checked_at: null };
const created = { evidence_id: evidence, document_id: document, document_version_id: version,
  locator: { locator_type: "DOCUMENT" as const }, display_label: "整份标准能力资料",
  display_excerpt: null, content_fingerprint: "a".repeat(64), eligibility_state: "CANDIDATE" as const,
  created_at: "2026-10-24T01:00:00Z", etag: '"v0"' as const };
function response(data: unknown): Response { return new Response(JSON.stringify({ data, trace_id: actor }),
  { status: 200, headers: { "Content-Type": "application/json" } }); }
async function session(admin: boolean, login = true): Promise<SessionClient> {
  const auth = new SessionClient(vi.fn().mockResolvedValue(response({ user: {
    user_id: actor, username_display: "合成用户" }, deployment_role: admin ? "DEPLOYMENT_ADMIN" : "NONE",
    password_change_required: false, authorized_projects: admin ? [] : [{ project_id: document,
      name: "合成项目", role: "PROJECT_MANAGER" }], absolute_expires_at: "2030-01-01T12:00:00Z",
    idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "a".repeat(64) })) as typeof fetch);
  if (login) await auth.login("synthetic", "synthetic-only"); return auth;
}
async function view(auth: SessionClient, docs = [candidate]) {
  const documents = new DocumentReadClient(vi.fn() as typeof fetch);
  const list = vi.spyOn(documents, "list").mockResolvedValue({ items: docs,
    next_cursor: null, has_more: false });
  const versions = vi.spyOn(documents, "listVersions").mockResolvedValue({ items: [fixed],
    next_cursor: null, has_more: false });
  const creator = new GlobalEvidenceCreateClient(auth);
  const create = vi.spyOn(creator, "create").mockResolvedValue(created);
  const router = createAppRouter(createMemoryHistory()); await router.push("/admin/evidence/new");
  await router.isReady();
  const wrapper = mount(GlobalEvidenceCreateView, { props: { session: auth, documents, creator },
    global: { plugins: [router] } });
  await flushPromises();
  return { wrapper, router, list, versions, create };
}
async function choose(result: Awaited<ReturnType<typeof view>>) {
  await result.wrapper.findAll("button").find(button => button.text() === "选择固定版本")!.trigger("click");
  await flushPromises();
  await result.wrapper.findAll("button").find(button => button.text() === "选用此版本")!.trigger("click");
  await flushPromises();
}
describe("GlobalEvidenceCreateView", () => {
  afterEach(() => { vi.restoreAllMocks(); window.sessionStorage.clear(); });
  it("blocks anonymous and ordinary members without a GLOBAL read or write", async () => {
    for (const auth of [await session(true, false), await session(false)]) {
      const result = await view(auth); expect(result.wrapper.find("form").exists()).toBe(false);
      expect(result.list).not.toHaveBeenCalled(); expect(result.create).not.toHaveBeenCalled();
      result.wrapper.unmount();
    }
  });
  it("chooses an AVAILABLE GLOBAL standard fixed version and creates only a CANDIDATE", async () => {
    const result = await view(await session(true), [{ ...candidate, category: "REFERENCE_MATERIAL" as never }, candidate]);
    expect(result.list).toHaveBeenCalledWith({ kind: "GLOBAL" }, null);
    await choose(result);
    expect(result.versions).toHaveBeenCalledWith({ kind: "GLOBAL" }, document, null);
    await result.wrapper.get("#global-evidence-label").setValue("整份标准能力资料");
    await result.wrapper.get('input[type="checkbox"]').setValue(true);
    await result.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(result.create).toHaveBeenCalledWith({ document_id: document, document_version_id: version,
      locator: { locator_type: "DOCUMENT" }, display_label: "整份标准能力资料", display_excerpt: null },
    expect.any(String));
    expect(result.wrapper.text()).toContain("CANDIDATE，不可作为能力版本的合格引用");
    expect(result.wrapper.text()).toContain("人工资格确认"); result.wrapper.unmount();
  });
  it("retains the exact input and key after an uncertain result", async () => {
    const result = await view(await session(true));
    result.create.mockRejectedValueOnce(new GlobalEvidenceCreateError("EVIDENCE_CREATE_UNCERTAIN"));
    await choose(result); await result.wrapper.get("#global-evidence-label").setValue("整份标准能力资料");
    await result.wrapper.get('input[type="checkbox"]').setValue(true);
    await result.wrapper.get("form").trigger("submit"); await flushPromises();
    const firstKey = result.create.mock.calls[0]?.[1];
    expect(result.wrapper.text()).toContain("原操作记录已保留");
    await result.wrapper.get('input[type="checkbox"]').setValue(true);
    await result.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(result.create.mock.calls[1]?.[0]).toEqual(result.create.mock.calls[0]?.[0]);
    expect(result.create.mock.calls[1]?.[1]).toBe(firstKey); result.wrapper.unmount();
  });
  it("cannot create without a fixed source", async () => {
    const result = await view(await session(true), []);
    expect(result.wrapper.text()).toContain("暂无合格的全局标准能力文档");
    expect(result.wrapper.get('button[type="submit"]').attributes("disabled")).toBeDefined();
    expect(result.create).not.toHaveBeenCalled(); result.wrapper.unmount();
  });
});
