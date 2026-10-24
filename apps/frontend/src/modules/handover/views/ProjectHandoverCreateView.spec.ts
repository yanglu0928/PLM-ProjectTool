import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { DocumentReadClient } from "@/modules/document/api/documentReadClient";
import { HandoverCreateClient, HandoverCreateError } from "@/modules/handover/api/handoverCreateClient";
import ProjectHandoverCreateView from "./ProjectHandoverCreateView.vue";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const document = "11234567-89ab-4cde-8123-456789abcdef";
const version = "21234567-89ab-4cde-8123-456789abcdef";
const analysis = "31234567-89ab-4cde-8123-456789abcdef";
const actor = "41234567-89ab-4cde-8123-456789abcdef";
const trace = "51234567-89ab-4cde-8123-456789abcdef";
const doc = { document_id: document, scope: "PROJECT", category: "CONTRACTUAL", subtype: null,
  title: "合成技术协议", display_name: "协议.pdf", state: "ACTIVE", latest_version_ref: version,
  effective_version_ref: version, created_at: "2026-10-24T12:00:00Z", etag: '"v0"' };
const fixed = { document_version_id: version, version_no: 1, content_sha256: "a".repeat(64),
  size_bytes: 100, detected_mime: "application/pdf", availability_state: "AVAILABLE",
  supersedes_version_ref: null, created_at: "2026-10-24T12:00:00Z", integrity_checked_at: null };
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
function dependencies() {
  const list = vi.fn().mockResolvedValue({ items: [doc], next_cursor: null, has_more: false });
  const listVersions = vi.fn().mockResolvedValue({ items: [fixed], next_cursor: null, has_more: false });
  const create = vi.fn().mockResolvedValue({ handover_analysis_id: analysis });
  return { documents: { list, listVersions } as unknown as DocumentReadClient,
    creator: { create } as unknown as HandoverCreateClient, list, listVersions, create };
}
async function view(auth: SessionClient, deps = dependencies()) {
  const router = createAppRouter(createMemoryHistory());
  await router.push(`/projects/${project}/handover/new`); await router.isReady();
  const wrapper = mount(ProjectHandoverCreateView, { props: { session: auth,
    documents: deps.documents, creator: deps.creator }, global: { plugins: [router] } });
  await flushPromises(); return { wrapper, router, ...deps };
}
async function selectSource(wrapper: Awaited<ReturnType<typeof view>>["wrapper"]) {
  await wrapper.get("button").trigger("click"); await flushPromises();
  await wrapper.findAll("button").find(button => button.text() === "选用此版本")!.trigger("click");
}
describe("ProjectHandoverCreateView", () => {
  beforeEach(() => window.sessionStorage.clear());
  afterEach(() => { vi.restoreAllMocks(); window.sessionStorage.clear(); });
  it("shows metadata-only document and fixed version, then submits exact references", async () => {
    const result = await view(await session());
    expect(result.wrapper.text()).toContain("合成技术协议");
    expect(result.wrapper.text()).not.toContain("11234567-89ab");
    await selectSource(result.wrapper);
    await result.wrapper.get("#handover-purpose").setValue("  ＰＬＭ交接  ");
    await result.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(result.create).toHaveBeenCalledWith(project, { analysis_purpose: "PLM交接",
      source_documents: [{ document_id: document, document_version_id: version }] }, expect.any(String));
    expect(result.router.currentRoute.value.name).toBe("project-handover-detail");
    expect(window.sessionStorage.length).toBe(0); result.wrapper.unmount();
  });
  it("does not submit without a fixed source or for a non-editor", async () => {
    const allowed = await view(await session());
    await allowed.wrapper.get("#handover-purpose").setValue("合成目的");
    await allowed.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(allowed.create).not.toHaveBeenCalled(); allowed.wrapper.unmount();
    const denied = await view(await session("CUSTOMER_MEMBER"));
    expect(denied.wrapper.text()).toContain("仅当前项目负责人或实施成员");
    expect(denied.list).not.toHaveBeenCalled(); expect(denied.wrapper.find("form").exists()).toBe(false);
    denied.wrapper.unmount();
  });
  it("retains one operation key and immutable sources after an uncertain result", async () => {
    const deps = dependencies(); deps.create.mockRejectedValueOnce(new HandoverCreateError("HANDOVER_CREATE_UNCERTAIN"));
    const result = await view(await session(), deps); await selectSource(result.wrapper);
    await result.wrapper.get("#handover-purpose").setValue("合成目的");
    await result.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(result.create).toHaveBeenCalledTimes(1);
    expect(window.sessionStorage.length).toBe(1);
    const key = result.create.mock.calls[0]![2];
    expect(result.wrapper.get("form button[type=submit]").attributes("disabled")).toBeDefined();
    await result.wrapper.get("input[type=checkbox]").setValue(true);
    await result.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(result.create.mock.calls[1]![2]).toBe(key);
    expect(window.sessionStorage.length).toBe(0); result.wrapper.unmount();
  });
  it("locks malformed persisted operations instead of generating a new key", async () => {
    window.sessionStorage.setItem(`plm.hnd.analysis.create.pending.${actor}.${project}`, "{broken");
    const result = await view(await session());
    expect(result.wrapper.get("[role=alert]").text()).toContain("无法安全读取");
    expect(result.wrapper.get("form button[type=submit]").attributes("disabled")).toBeDefined();
    expect(result.create).not.toHaveBeenCalled(); result.wrapper.unmount();
  });
  it("pages document and fixed-version metadata without fetching content", async () => {
    const deps = dependencies(); const cursor = `${"A".repeat(24)}.${"B".repeat(43)}`;
    deps.list.mockResolvedValueOnce({ items: [], next_cursor: cursor, has_more: true })
      .mockResolvedValueOnce({ items: [doc], next_cursor: null, has_more: false });
    deps.listVersions.mockResolvedValueOnce({ items: [], next_cursor: cursor, has_more: true })
      .mockResolvedValueOnce({ items: [fixed], next_cursor: null, has_more: false });
    const result = await view(await session(), deps);
    await result.wrapper.findAll("button").find(button => button.text() === "加载更多文档")!.trigger("click");
    await flushPromises(); expect(result.list.mock.calls[1]![1]).toBe(cursor);
    await result.wrapper.findAll("button").find(button => button.text() === "选择固定版本")!.trigger("click");
    await flushPromises();
    await result.wrapper.findAll("button").find(button => button.text() === "加载更多版本")!.trigger("click");
    await flushPromises(); expect(result.listVersions.mock.calls[1]![2]).toBe(cursor);
    await result.wrapper.findAll("button").find(button => button.text() === "选用此版本")!.trigger("click");
    expect(result.wrapper.text()).toContain("合成技术协议");
    result.wrapper.unmount();
  });
  it("restores the original key after a page remount for deliberate same-operation retry", async () => {
    const deps = dependencies(); deps.create.mockRejectedValueOnce(new HandoverCreateError("HANDOVER_CREATE_UNCERTAIN"));
    const auth = await session(); const first = await view(auth, deps);
    await selectSource(first.wrapper); await first.wrapper.get("#handover-purpose").setValue("合成目的");
    await first.wrapper.get("form").trigger("submit"); await flushPromises();
    const originalKey = deps.create.mock.calls[0]![2]; first.wrapper.unmount();
    const second = await view(auth, deps);
    expect(second.wrapper.text()).toContain("原操作号与固定来源已保存");
    expect(second.wrapper.get("#handover-purpose").attributes("disabled")).toBeDefined();
    await second.wrapper.get("input[type=checkbox]").setValue(true);
    await second.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(deps.create.mock.calls[1]![2]).toBe(originalKey);
    expect(window.sessionStorage.length).toBe(0); second.wrapper.unmount();
  });
});
