import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import type { OutlineCurrent, OutlineReadClient } from "@/modules/solution/api/outlineReadClient";
import type { OutlineVersionProjectCandidates } from "@/modules/solution/api/outlineVersionCandidates";
import { OutlineVersionCreateClient, OutlineVersionCreateError } from
  "@/modules/solution/api/outlineVersionCreateClient";
import View from "./ProjectOutlineVersionCreateView.vue";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const outline = "11234567-89ab-4cde-8123-456789abcdef";
const section = "21234567-89ab-4cde-8123-456789abcdef";
const requirement = "31234567-89ab-4cde-8123-456789abcdef";
const reqVersion = "41234567-89ab-4cde-8123-456789abcdef";
const reference = "51234567-89ab-4cde-8123-456789abcdef";
const refVersion = "61234567-89ab-4cde-8123-456789abcdef";
const createdVersion = "71234567-89ab-4cde-8123-456789abcdef";
const parent = { solution_outline_id: outline, project_id: project, name: "方案目录",
  outline_state: "ACTIVE", current_approved_version_ref: null,
  created_at: "2026-10-09T00:00:00Z", etag: '"v0"', created_by: project } as OutlineCurrent;
const available = { sections: [{ solution_section_id: section, solution_outline_id: outline,
  project_id: project, section_key: "业务范围", section_state: "ACTIVE",
  current_approved_version_ref: null, created_at: "2026-10-09T00:00:00Z", etag: '"v0"' }],
  requirements: [{ requirement_id: requirement, project_id: project, requirement_code: "REQ-1",
    state: "ACTIVE", current_approved_version_ref: reqVersion, created_by: project,
    created_at: "2026-10-09T00:00:00Z", updated_by: null,
    updated_at: "2026-10-09T00:00:00Z", etag: '"v0"' }],
  references: [{ reference_solution_id: reference, reference_version_id: refVersion,
    scope: "PROJECT", project_id: project, name: "参考", eligibility_state: "ELIGIBLE",
    version_no: 1, version_state: "DRAFT", created_at: "2026-10-09T00:00:00Z", etag: '"v0"' }],
} as OutlineVersionProjectCandidates;
async function session(role = "PROJECT_MANAGER") {
  const api = new SessionClient(vi.fn().mockResolvedValue(new Response(JSON.stringify({ data: {
    user: { user_id: project, username_display: "合成用户" }, deployment_role: "NONE",
    password_change_required: false,
    authorized_projects: [{ project_id: project, name: "项目", role }],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64),
  }, trace_id: project }), { status: 200, headers: { "Content-Type": "application/json" } })) as typeof fetch);
  await api.login("user", "synthetic-only"); return api;
}
async function page(role = "PROJECT_MANAGER", create = vi.fn().mockResolvedValue({ solution_outline_version_id: createdVersion })) {
  const router = createAppRouter(createMemoryHistory());
  await router.push(`/projects/${project}/solution-outlines/${outline}/versions/new`); await router.isReady();
  const wrapper = mount(View, { props: { session: await session(role),
    outlineReader: { current: vi.fn().mockResolvedValue(parent) } as unknown as OutlineReadClient,
    candidateLoader: vi.fn().mockResolvedValue(available),
    creator: { create } as unknown as OutlineVersionCreateClient }, global: { plugins: [router] } });
  await flushPromises(); return { wrapper, router, create };
}
describe("OutlineVersion PROJECT create page", () => {
  afterEach(() => { window.sessionStorage.clear(); vi.restoreAllMocks(); });
  it("hides write from customer and exposes only reviewable project candidates", async () => {
    const denied = await page("CUSTOMER_MEMBER");
    expect(denied.wrapper.find("form").exists()).toBe(false); denied.wrapper.unmount();
    const allowed = await page();
    expect(allowed.router.currentRoute.value.name).toBe("project-outline-version-create");
    expect(allowed.wrapper.text()).toContain("GLOBAL 参考候选需要独立");
    expect(allowed.wrapper.findAll("fieldset")).toHaveLength(3);
    expect(allowed.wrapper.text()).toContain("查看章节");
    allowed.wrapper.unmount();
  });
  it("persists exact selected refs and retries the original key after uncertainty", async () => {
    const create = vi.fn().mockRejectedValueOnce(new OutlineVersionCreateError("OUTLINE_VERSION_CREATE_UNCERTAIN"))
      .mockResolvedValueOnce({ solution_outline_version_id: createdVersion });
    const first = await page("PROJECT_MANAGER", create);
    const fields = first.wrapper.findAll("fieldset");
    await fields[0]!.get("input").setValue(true);
    await fields[1]!.get("input").setValue(true);
    await fields[2]!.get("input").setValue(true);
    await first.wrapper.get("form > label input[type=checkbox]").setValue(true);
    await first.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(create).toHaveBeenCalledTimes(1);
    expect(create.mock.calls[0]?.[2]).toEqual({ section_ids: [section],
      requirement_refs: [{ requirement_id: requirement, requirement_version_id: reqVersion }],
      reference_refs: [{ scope: "PROJECT", reference_solution_id: reference, reference_version_id: refVersion }],
      missing_declarations: [], conflict_declarations: [] });
    const firstKey = create.mock.calls[0]?.[3];
    expect(window.sessionStorage.length).toBe(1); first.wrapper.unmount();
    const second = await page("PROJECT_MANAGER", create);
    expect(second.wrapper.get("button[type=submit]").attributes("disabled")).toBeDefined();
    await second.wrapper.get("form > label input[type=checkbox]").setValue(true);
    await second.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(create).toHaveBeenCalledTimes(2);
    expect(create.mock.calls[1]).toEqual([project, outline, create.mock.calls[0]?.[2], firstKey]);
    expect(second.wrapper.text()).toContain(createdVersion);
    expect(window.sessionStorage.length).toBe(0); second.wrapper.unmount();
  });
  it("fails closed on missing section and corrupt pending record", async () => {
    const first = await page();
    await first.wrapper.get("form > label input[type=checkbox]").setValue(true);
    await first.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(first.create).not.toHaveBeenCalled();
    expect(first.wrapper.text()).toContain("至少选择一个当前方案章节"); first.wrapper.unmount();
    window.sessionStorage.setItem(`plm.sol.outline.version.create.pending.${project}.${project}.${outline}`, "corrupt");
    const second = await page();
    expect(second.wrapper.get("button[type=submit]").attributes("disabled")).toBeDefined();
    expect(second.wrapper.text()).toContain("已停止提交"); second.wrapper.unmount();
  });
});
