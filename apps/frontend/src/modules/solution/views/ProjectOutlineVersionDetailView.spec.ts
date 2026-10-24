import { flushPromises, shallowMount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { OutlineVersionReadClient } from "@/modules/solution/api/outlineVersionReadClient";
import ProjectOutlineVersionDetailView from "./ProjectOutlineVersionDetailView.vue";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const outline = "11234567-89ab-4cde-8123-456789abcdef";
const version = "21234567-89ab-4cde-8123-456789abcdef";
const actor = "31234567-89ab-4cde-8123-456789abcdef";
const detail = { solution_outline_version_id: version, solution_outline_id: outline,
  project_id: project, version_no: 1, version_state: "DRAFT",
  content_fingerprint: "a".repeat(64), declared_section_count: 0,
  declared_requirement_count: 0, declared_reference_count: 0,
  missing_declaration_count: 0, conflict_declaration_count: 0,
  supersedes_version_ref: null, review_ref: null, review_round_ref: null,
  created_by: actor, created_at: "2026-10-24T00:00:00Z",
  section_ids: [], requirement_refs: [], reference_refs: [],
  missing_declarations: [], conflict_declarations: [] };
describe("ProjectOutlineVersionDetailView", () => {
  it("mounts Outline submission against the exact fixed version after authorized read", async () => {
    const router = createAppRouter(createMemoryHistory());
    await router.push(`/projects/${project}/solution-outlines/${outline}/versions/${version}`);
    await router.isReady();
    const login = new Response(JSON.stringify({ data: {
      user: { user_id: actor, username_display: "合成负责人" }, deployment_role: "NONE",
      password_change_required: false,
      authorized_projects: [{ project_id: project, name: "项目", role: "PROJECT_MANAGER" }],
      absolute_expires_at: "2030-01-01T12:00:00Z",
      idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "a".repeat(64),
    }, trace_id: project }), { status: 200, headers: { "Content-Type": "application/json" } });
    const session = new SessionClient(vi.fn().mockResolvedValue(login) as typeof fetch);
    await session.login("manager", "synthetic-only");
    const reader = { detail: vi.fn().mockResolvedValue(detail) };
    const wrapper = shallowMount(ProjectOutlineVersionDetailView, {
      props: { session, reader: reader as unknown as OutlineVersionReadClient },
      global: { plugins: [router] },
    });
    await flushPromises();
    expect(reader.detail).toHaveBeenCalledWith(project, outline, version);
    const panel = wrapper.getComponent({ name: "OutlineReviewSubmitPanel" });
    expect(panel.props("detail")).toEqual(detail);
    expect(panel.props("session")).toBe(session);
    wrapper.unmount();
  });
});
