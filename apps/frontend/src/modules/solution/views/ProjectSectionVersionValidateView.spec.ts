import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import type { SectionVersionReadClient } from "@/modules/solution/api/sectionVersionReadClient";
import { SectionVersionValidateError, type SectionVersionValidateClient } from
  "@/modules/solution/api/sectionVersionValidateClient";
import ProjectSectionVersionDetailView from "./ProjectSectionVersionDetailView.vue";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const section = "11234567-89ab-4cde-8123-456789abcdef";
const version = "21234567-89ab-4cde-8123-456789abcdef";
const other = "31234567-89ab-4cde-8123-456789abcdef";
const item = { solution_section_version_id: version, solution_section_id: section,
  project_id: project, version_no: 1, version_state: "DRAFT", title: "方案草案",
  content_fingerprint: "a".repeat(64), declared_requirement_count: 1,
  declared_evidence_count: 1, assumption_count: 0, exclusion_count: 0,
  supersedes_version_ref: null, review_ref: null, review_round_ref: null,
  created_by: project, created_at: "2026-10-12T00:00:00Z",
  content_document_version_ref: other, content_artifact_ref: null,
  requirement_refs: [{ requirement_id: other, requirement_version_id: other }],
  evidence_ids: [other], assumptions: [], exclusions: [] };
const report = { audit_event_id: other, observation_trace_id: version,
  project_id: project, solution_section_id: section, solution_section_version_id: version,
  version_no: 1, version_state: "DRAFT", content_fingerprint: "a".repeat(64),
  requirement_count: 1, evidence_count: 1, facts: {
    integrity: "PASS", content: "PASS", requirements: "PASS", evidence: "PASS",
    trace: "UNAVAILABLE", spec: "UNAVAILABLE" },
  valid: true, ready_for_review: false,
  issue_codes: ["TRACE_COVERAGE_UNAVAILABLE", "STRUCTURED_SPEC_UNAVAILABLE"],
  observed_at: "2026-10-12T00:00:00Z" };
async function session(role = "PROJECT_MANAGER") {
  const client = new SessionClient(vi.fn().mockResolvedValue(new Response(JSON.stringify({ data: {
    user: { user_id: project, username_display: "合成用户" }, deployment_role: "NONE",
    password_change_required: false,
    authorized_projects: [{ project_id: project, name: "项目", role }],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64),
  }, trace_id: project }), { status: 200, headers: { "Content-Type": "application/json" } })) as typeof fetch);
  await client.login("user", "synthetic-only"); return client;
}
async function page(role = "PROJECT_MANAGER", validate = vi.fn().mockResolvedValue(report),
  actorSession?: SessionClient) {
  const router = createAppRouter(createMemoryHistory());
  await router.push(`/projects/${project}/solution-sections/${section}/versions/${version}`);
  await router.isReady();
  const reader = { detail: vi.fn().mockResolvedValue(item) };
  const wrapper = mount(ProjectSectionVersionDetailView, { props: {
    session: actorSession ?? await session(role), reader: reader as unknown as SectionVersionReadClient,
    validator: { validate } as unknown as SectionVersionValidateClient,
  }, global: { plugins: [router] } });
  await flushPromises(); return { wrapper, router, reader, validate };
}
function validationButton(wrapper: Awaited<ReturnType<typeof page>>["wrapper"]) {
  return wrapper.findAll("button").find(button => button.text().includes("验证当前来源")
    || button.text().includes("重试验证"))!;
}

describe("SectionVersion detail validation report", () => {
  afterEach(() => { window.sessionStorage.clear(); vi.restoreAllMocks(); });

  it("shows six audited dimensions but not a false review approval", async () => {
    const view = await page();
    await validationButton(view.wrapper).trigger("click"); await flushPromises();
    expect(view.validate).toHaveBeenCalledExactlyOnceWith(project, section, version, expect.any(String));
    expect(view.wrapper.text()).toContain("固定内容与来源核验通过");
    expect(view.wrapper.text()).toContain("追溯覆盖：暂无法核验");
    expect(view.wrapper.text()).toContain("结构化规格：暂无法核验");
    expect(view.wrapper.text()).toContain("尚不具备送审条件");
    expect(view.wrapper.text()).toContain("TRACE_COVERAGE_UNAVAILABLE");
    expect(view.wrapper.text()).toContain("审计记录");
    expect(view.wrapper.text()).toContain("不能给出来源文档的精确位置");
    expect(window.sessionStorage.length).toBe(0); view.wrapper.unmount();
  });

  it("hides validation for customer member while keeping fixed history readable", async () => {
    const view = await page("CUSTOMER_MEMBER");
    expect(view.wrapper.text()).toContain("方案草案");
    expect(view.wrapper.findAll("button").some(button => button.text().includes("验证当前来源"))).toBe(false);
    expect(view.validate).not.toHaveBeenCalled(); view.wrapper.unmount();
  });

  it("restores an uncertain request and retries only its original key after confirmation", async () => {
    const actorSession = await session();
    const validate = vi.fn().mockRejectedValueOnce(new SectionVersionValidateError(
      "SECTION_VERSION_VALIDATE_UNCERTAIN")).mockResolvedValueOnce(report);
    const first = await page("PROJECT_MANAGER", validate, actorSession);
    await validationButton(first.wrapper).trigger("click"); await flushPromises();
    expect(window.sessionStorage.length).toBe(1);
    const original = validate.mock.calls[0]; first.wrapper.unmount();
    const second = await page("PROJECT_MANAGER", validate, actorSession);
    expect(validationButton(second.wrapper).attributes("disabled")).toBeDefined();
    await second.wrapper.get('input[type="checkbox"]').setValue(true);
    await validationButton(second.wrapper).trigger("click"); await flushPromises();
    expect(validate.mock.calls[1]).toEqual(original);
    expect(second.wrapper.text()).toContain("尚不具备送审条件");
    expect(window.sessionStorage.length).toBe(0); second.wrapper.unmount();
  });

  it("does not send without durable key and clears report on route change", async () => {
    const view = await page();
    const blocked = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
    await validationButton(view.wrapper).trigger("click"); await flushPromises();
    expect(view.validate).not.toHaveBeenCalled();
    expect(view.wrapper.text()).toContain("本次未发送验证"); blocked.mockRestore();
    await validationButton(view.wrapper).trigger("click"); await flushPromises();
    expect(view.wrapper.text()).toContain("审计记录");
    await view.router.push(`/projects/${project}/solution-sections/${section}/versions/${other}`);
    await flushPromises();
    expect(view.wrapper.text()).not.toContain("TRACE_COVERAGE_UNAVAILABLE");
    view.wrapper.unmount();
  });
});
