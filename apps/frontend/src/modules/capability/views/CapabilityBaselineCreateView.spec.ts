import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { DocumentReadClient } from "@/modules/document/api/documentReadClient";
import { CapabilityCreateClient, CapabilityCreateError } from "@/modules/capability/api/capabilityCreateClient";
import CapabilityBaselineCreateView from "./CapabilityBaselineCreateView.vue";

const actor = "01234567-89ab-4cde-8123-456789abcdef";
const baseline = "11234567-89ab-4cde-8123-456789abcdef";
const document = "21234567-89ab-4cde-8123-456789abcdef";
const version = "31234567-89ab-4cde-8123-456789abcdef";
const candidate = { document_id: document, scope: "GLOBAL" as const,
  category: "STANDARD_CAPABILITY" as const, subtype: null, title: "标准能力资料",
  display_name: "standard.pdf", state: "ACTIVE" as const, latest_version_ref: version,
  effective_version_ref: version, created_at: "2026-10-24T01:00:00Z", etag: '"v0"' };
const fixed = { document_version_id: version, version_no: 1, content_sha256: "a".repeat(64),
  size_bytes: 99, detected_mime: "application/pdf", availability_state: "AVAILABLE" as const,
  supersedes_version_ref: null, created_at: "2026-10-24T01:00:00Z", integrity_checked_at: null };
const created = { baseline_id: baseline, baseline_code: "STD-01", name: "标准能力基线",
  description: null, state: "ACTIVE" as const, source_collection_ref: `sha256:${"a".repeat(64)}`,
  current_approved_version_ref: null, created_at: "2026-10-24T01:00:00Z", etag: '"v0"' as const };
function response(data: unknown): Response { return new Response(JSON.stringify({ data, trace_id: actor }),
  { status: 200, headers: { "Content-Type": "application/json" } }); }
async function session(admin: boolean, login = true): Promise<SessionClient> {
  const auth = new SessionClient(vi.fn().mockResolvedValue(response({ user: {
    user_id: actor, username_display: "合成用户" }, deployment_role: admin ? "DEPLOYMENT_ADMIN" : "NONE",
    password_change_required: false, authorized_projects: admin ? [] : [{ project_id: baseline,
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
  const creator = new CapabilityCreateClient(auth);
  const create = vi.spyOn(creator, "create").mockResolvedValue(created);
  const router = createAppRouter(createMemoryHistory()); await router.push("/admin/capability-baselines/new");
  await router.isReady();
  const wrapper = mount(CapabilityBaselineCreateView, { props: { session: auth, documents, creator },
    global: { plugins: [router] } });
  await flushPromises();
  return { wrapper, router, list, versions, create };
}
async function choose(result: Awaited<ReturnType<typeof view>>) {
  await result.wrapper.get("button").trigger("click"); await flushPromises();
  await result.wrapper.findAll("button").find(button => button.text() === "选用此版本")!.trigger("click");
  await flushPromises();
}
describe("CapabilityBaselineCreateView", () => {
  afterEach(() => { vi.restoreAllMocks(); window.sessionStorage.clear(); });
  it("blocks anonymous and ordinary project members without GLOBAL document requests", async () => {
    for (const auth of [await session(true, false), await session(false)]) {
      const result = await view(auth);
      expect(result.wrapper.find("form").exists()).toBe(false);
      expect(result.list).not.toHaveBeenCalled();
      expect(result.create).not.toHaveBeenCalled(); result.wrapper.unmount();
    }
  });
  it("offers only active GLOBAL STANDARD_CAPABILITY fixed versions and creates an unapproved identity", async () => {
    const result = await view(await session(true), [{ ...candidate, category: "REFERENCE_MATERIAL" as never }, candidate]);
    expect(result.list).toHaveBeenCalledWith({ kind: "GLOBAL" }, null);
    expect(result.wrapper.text()).not.toContain("参考资料");
    await choose(result);
    expect(result.versions).toHaveBeenCalledWith({ kind: "GLOBAL" }, document, null);
    await result.wrapper.get("#baseline-code").setValue("std-01");
    await result.wrapper.get("#baseline-name").setValue("标准能力基线");
    await result.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(result.create).toHaveBeenCalledWith({ baseline_code: "STD-01", name: "标准能力基线",
      description: null, source_documents: [{ document_id: document, document_version_id: version }] },
    expect.any(String));
    expect(result.wrapper.text()).toContain("重新读取已创建基线");
    expect(result.router.currentRoute.value.name).toBe("capability-baseline-detail");
    result.wrapper.unmount();
  });
  it("keeps original key and source set after an unknown result", async () => {
    const result = await view(await session(true));
    result.create.mockRejectedValueOnce(new CapabilityCreateError("CAPABILITY_CREATE_UNCERTAIN"));
    await choose(result);
    await result.wrapper.get("#baseline-code").setValue("STD-01");
    await result.wrapper.get("#baseline-name").setValue("标准能力基线");
    await result.wrapper.get("form").trigger("submit"); await flushPromises();
    const firstKey = result.create.mock.calls[0]?.[1];
    expect(result.wrapper.text()).toContain("原操作记录已保留");
    expect(result.wrapper.get('button[type="submit"]').attributes("disabled")).toBeDefined();
    await result.wrapper.get('input[type="checkbox"]').setValue(true);
    await result.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(result.create.mock.calls[1]?.[1]).toBe(firstKey);
    expect(result.create.mock.calls[1]?.[0]).toEqual(result.create.mock.calls[0]?.[0]);
    result.wrapper.unmount();
  });
  it("does not submit with zero available sources", async () => {
    const result = await view(await session(true), []);
    expect(result.wrapper.text()).toContain("暂无合格的全局标准能力文档");
    expect(result.wrapper.get('button[type="submit"]').attributes("disabled")).toBeDefined();
    expect(result.create).not.toHaveBeenCalled(); result.wrapper.unmount();
  });
});
