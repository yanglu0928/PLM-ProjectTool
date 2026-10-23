import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { ProjectMemberReadClient } from "@/modules/project/api/projectMemberReadClient";
import { SectionVersionReadClient } from "@/modules/solution/api/sectionVersionReadClient";
import { SectionVersionValidateClient } from "@/modules/solution/api/sectionVersionValidateClient";
import { SectionReviewSubmitError, SectionVersionSubmitReviewClient } from
  "@/modules/solution/api/sectionVersionSubmitReviewClient";
import SectionReviewSubmitPanel from "./SectionReviewSubmitPanel.vue";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const section = "11234567-89ab-4cde-8123-456789abcdef";
const version = "21234567-89ab-4cde-8123-456789abcdef";
const actor = "31234567-89ab-4cde-8123-456789abcdef";
const customer = "41234567-89ab-4cde-8123-456789abcdef";
const implementation = "51234567-89ab-4cde-8123-456789abcdef";
const review = "61234567-89ab-4cde-8123-456789abcdef";
const round = "71234567-89ab-4cde-8123-456789abcdef";
const detail = { solution_section_version_id: version, solution_section_id: section,
  project_id: project, version_no: 1, version_state: "DRAFT", title: "方案章节",
  content_fingerprint: "a".repeat(64), declared_requirement_count: 0,
  declared_evidence_count: 0, assumption_count: 0, exclusion_count: 0,
  supersedes_version_ref: null, review_ref: null, review_round_ref: null,
  created_by: actor, created_at: "2026-10-23T00:00:00Z",
  content_document_version_ref: version, content_artifact_ref: null,
  requirement_refs: [], evidence_ids: [], assumptions: [], exclusions: [] } as const;
const report = { project_id: project, solution_section_id: section,
  solution_section_version_id: version, version_no: 1, version_state: "DRAFT",
  content_fingerprint: "a".repeat(64), ready_for_review: true };
const receipt = { review_id: review, review_round_id: round, subject_type: "SOL-05",
  project_id: project, solution_section_id: section,
  solution_section_version_id: version, policy_ref: "SOLUTION_SECTION_ALL_V1",
  reviewer_ids: [customer], state: "IN_REVIEW", round_no: 1,
  review_etag: '"v1"', submitted_by: actor,
  submitted_at: "2026-10-23T00:01:00Z" };
const members = [
  { member_id: customer, user: { user_id: customer, display_name: "客户甲" },
    role: "CUSTOMER_MEMBER", state: "ACTIVE" },
  { member_id: implementation, user: { user_id: implementation,
    display_name: "实施乙" }, role: "IMPLEMENTATION_MEMBER", state: "ACTIVE" },
];
async function session(role: string) {
  const login = new Response(JSON.stringify({ data: {
    user: { user_id: actor, username_display: "合成用户" }, deployment_role: "NONE",
    password_change_required: false,
    authorized_projects: [{ project_id: project, name: "项目", role }],
    absolute_expires_at: "2030-01-01T12:00:00Z",
    idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "a".repeat(64),
  }, trace_id: project }), { status: 200,
    headers: { "Content-Type": "application/json" } });
  const client = new SessionClient(vi.fn().mockResolvedValue(login) as typeof fetch);
  await client.login("user", "synthetic-only"); return client;
}
async function panel(role = "PROJECT_MANAGER", outcome = vi.fn().mockResolvedValue(receipt)) {
  const router = createAppRouter(createMemoryHistory());
  await router.push(`/projects/${project}/solution-sections/${section}/versions/${version}`);
  await router.isReady();
  const memberClient = { list: vi.fn().mockResolvedValue({ items: members,
    next_cursor: null, has_more: false }) };
  const submitter = { submit: outcome };
  const wrapper = mount(SectionReviewSubmitPanel, { props: {
    session: await session(role), detail: detail as unknown as
      Awaited<ReturnType<SectionVersionReadClient["detail"]>>,
    report: report as unknown as Awaited<ReturnType<SectionVersionValidateClient["validate"]>>,
    members: memberClient as unknown as ProjectMemberReadClient,
    submitter: submitter as unknown as SectionVersionSubmitReviewClient,
  }, global: { plugins: [router] } });
  await flushPromises();
  return { wrapper, memberClient, submitter };
}
describe("SectionReviewSubmitPanel", () => {
  afterEach(() => { vi.restoreAllMocks(); sessionStorage.clear(); });
  it("offers only active customer reviewers and links the accepted Review", async () => {
    const { wrapper, submitter } = await panel();
    expect(wrapper.text()).toContain("客户甲");
    expect(wrapper.text()).not.toContain("实施乙");
    await wrapper.get(`input[value="${customer}"]`).setValue(true);
    await wrapper.findAll("button").find(button => button.text() === "提交客户章节评审")!.trigger("click");
    await flushPromises();
    expect(submitter.submit).toHaveBeenCalledWith(project, section, version,
      [customer], expect.stringMatching(/^section-review-/));
    expect(wrapper.get(`a[href="/projects/${project}/reviews/${review}"]`).text())
      .toContain("打开评审");
    expect(sessionStorage.length).toBe(0);
    wrapper.unmount();
  });
  it("retains exact reviewer/key on uncertain result until explicit retry", async () => {
    const outcome = vi.fn().mockRejectedValueOnce(new SectionReviewSubmitError(
      "SECTION_REVIEW_UNCERTAIN")).mockResolvedValueOnce(receipt);
    const { wrapper, submitter } = await panel("PROJECT_MANAGER", outcome);
    await wrapper.get(`input[value="${customer}"]`).setValue(true);
    await wrapper.findAll("button").find(button => button.text() === "提交客户章节评审")!.trigger("click");
    await flushPromises();
    expect(sessionStorage.length).toBe(1);
    const first = submitter.submit.mock.calls[0];
    await wrapper.get('input[type="checkbox"]').setValue(true);
    await wrapper.findAll("button").find(button => button.text() === "按原操作号重试送审")!.trigger("click");
    await flushPromises();
    expect(submitter.submit.mock.calls[1]).toEqual(first);
    expect(sessionStorage.length).toBe(0);
    wrapper.unmount();
  });
  it("does not load candidates or submit for a customer", async () => {
    const { wrapper, memberClient, submitter } = await panel("CUSTOMER_MEMBER");
    expect(wrapper.text()).toContain("仅当前项目负责人可送审");
    expect(memberClient.list).not.toHaveBeenCalled();
    expect(wrapper.findAll("button").some(button => button.text() === "提交客户章节评审"))
      .toBe(false);
    expect(submitter.submit).not.toHaveBeenCalled();
    wrapper.unmount();
  });
});
