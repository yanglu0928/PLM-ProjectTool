import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { SectionVersionCreateClient, SectionVersionCreateError } from
  "@/modules/solution/api/sectionVersionCreateClient";
import type { SectionReadClient } from "@/modules/solution/api/sectionReadClient";
import ProjectSectionVersionCreateView from "./ProjectSectionVersionCreateView.vue";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const section = "11234567-89ab-4cde-8123-456789abcdef";
const document = "21234567-89ab-4cde-8123-456789abcdef";
const version = "31234567-89ab-4cde-8123-456789abcdef";
const requirement = "41234567-89ab-4cde-8123-456789abcdef";
const evidence = "51234567-89ab-4cde-8123-456789abcdef";
const created = "61234567-89ab-4cde-8123-456789abcdef";
const parent = { solution_section_id: section, project_id: project, solution_outline_id: project,
  section_key: "设计方案", section_state: "ACTIVE" };
const candidates = { documents: [{ document_id: document, scope: "PROJECT", state: "ACTIVE", title: "方案正文" }],
  requirements: [{ requirement_id: requirement, project_id: project, requirement_code: "REQ-1",
    current_approved_version_ref: version, state: "ACTIVE" }],
  evidence: [{ evidence_id: evidence, display_label: "调研证据", eligibility_state: "ELIGIBLE" }] };
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
async function page(role = "PROJECT_MANAGER", create = vi.fn().mockResolvedValue({ solution_section_version_id: created }),
  current = vi.fn().mockResolvedValue(parent), candidateLoader = vi.fn().mockResolvedValue(candidates)) {
  const router = createAppRouter(createMemoryHistory());
  await router.push(`/projects/${project}/solution-sections/${section}/versions/new`); await router.isReady();
  const wrapper = mount(ProjectSectionVersionCreateView, { props: { session: await session(role),
    reader: { current } as unknown as SectionReadClient,
    creator: { create } as unknown as SectionVersionCreateClient,
    candidateLoader, versionLoader: vi.fn().mockResolvedValue([{ document_version_id: version,
      version_no: 1, availability_state: "AVAILABLE", created_at: "2026-10-12T00:00:00Z" }]) },
  global: { plugins: [router] } });
  await flushPromises(); return { wrapper, router, create, current, candidateLoader };
}
async function fill(wrapper: Awaited<ReturnType<typeof page>>["wrapper"]) {
  await wrapper.get("#section-version-title").setValue("  设计方案草案  ");
  await wrapper.get("#section-version-document").setValue(document); await flushPromises();
  await wrapper.get("#section-version-document-version").setValue(version);
  await wrapper.get('input[value="' + requirement + '"]').setValue(true);
  await wrapper.get('input[value="' + evidence + '"]').setValue(true);
  const confirmations = wrapper.findAll('input[type="checkbox"]');
  await confirmations[confirmations.length - 1]!.setValue(true);
}
describe("ProjectSectionVersionCreateView", () => {
  afterEach(() => { window.sessionStorage.clear(); vi.restoreAllMocks(); });
  it("gates write role, archived parent and candidate-read failure", async () => {
    const denied = await page("CUSTOMER_MEMBER");
    expect(denied.wrapper.find("form").exists()).toBe(false);
    expect(denied.current).not.toHaveBeenCalled(); denied.wrapper.unmount();
    const archived = await page("PROJECT_MANAGER", vi.fn(),
      vi.fn().mockResolvedValue({ ...parent, section_state: "ARCHIVED" }));
    expect(archived.wrapper.find("form").exists()).toBe(false); archived.wrapper.unmount();
    const unavailable = await page("PROJECT_MANAGER", vi.fn(), vi.fn().mockResolvedValue(parent),
      vi.fn().mockRejectedValue(new Error("incomplete")));
    expect(unavailable.wrapper.find("form").exists()).toBe(false);
    expect(unavailable.wrapper.text()).toContain("incomplete"); unavailable.wrapper.unmount();
  });
  it("submits fixed current metadata as DRAFT and links the created version", async () => {
    const view = await page();
    expect(view.router.currentRoute.value.name).toBe("project-section-version-create");
    await fill(view.wrapper);
    await view.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(view.create).toHaveBeenCalledExactlyOnceWith(project, section, {
      title: "设计方案草案", content_document_version_ref: version, content_artifact_ref: null,
      requirement_refs: [{ requirement_id: requirement, requirement_version_id: version }],
      evidence_ids: [evidence], assumptions: [], exclusions: [],
    }, expect.any(String));
    expect(view.wrapper.text()).toContain("草案版本已创建");
    expect(window.sessionStorage.length).toBe(0); view.wrapper.unmount();
  });
  it("restores uncertain commit and retries identical key and body only after confirmation", async () => {
    const create = vi.fn().mockRejectedValueOnce(new SectionVersionCreateError("SECTION_VERSION_CREATE_UNCERTAIN"))
      .mockResolvedValueOnce({ solution_section_version_id: created });
    const first = await page("PROJECT_MANAGER", create); await fill(first.wrapper);
    await first.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(window.sessionStorage.length).toBe(1);
    const original = create.mock.calls[0]; first.wrapper.unmount();
    const second = await page("PROJECT_MANAGER", create);
    expect(second.wrapper.find("#section-version-title").exists()).toBe(false);
    expect(second.wrapper.get("button[type=submit]").attributes("disabled")).toBeDefined();
    await second.wrapper.get('input[type="checkbox"]').setValue(true);
    await second.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(create.mock.calls[1]).toEqual(original);
    expect(window.sessionStorage.length).toBe(0); second.wrapper.unmount();
  });
  it("does not send when original operation cannot be stored or parsed", async () => {
    const create = vi.fn(); const view = await page("PROJECT_MANAGER", create); await fill(view.wrapper);
    const storage = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
    await view.wrapper.get("form").trigger("submit"); await flushPromises();
    expect(create).not.toHaveBeenCalled(); storage.mockRestore(); view.wrapper.unmount();
    window.sessionStorage.setItem(`plm.sol.section.version.create.pending.${project}.${project}.${section}`, "corrupt");
    const restored = await page("PROJECT_MANAGER", create);
    expect(restored.wrapper.text()).toContain("已停止提交");
    expect(restored.wrapper.get("button[type=submit]").attributes("disabled")).toBeDefined();
    restored.wrapper.unmount();
  });
});
