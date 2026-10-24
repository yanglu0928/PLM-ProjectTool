import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { ProjectMemberReadClient } from "@/modules/project/api/projectMemberReadClient";
import { OutlineVersionReadClient } from "@/modules/solution/api/outlineVersionReadClient";
import { OutlineReviewSubmitError, OutlineVersionSubmitReviewClient } from
  "@/modules/solution/api/outlineVersionSubmitReviewClient";
import OutlineReviewSubmitPanel from "./OutlineReviewSubmitPanel.vue";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const outline = "11234567-89ab-4cde-8123-456789abcdef";
const version = "21234567-89ab-4cde-8123-456789abcdef";
const actor = "31234567-89ab-4cde-8123-456789abcdef";
const customer = "41234567-89ab-4cde-8123-456789abcdef";
const implementation = "51234567-89ab-4cde-8123-456789abcdef";
const review = "61234567-89ab-4cde-8123-456789abcdef";
const round = "71234567-89ab-4cde-8123-456789abcdef";
const detail = { solution_outline_version_id: version, solution_outline_id: outline,
  project_id: project, version_no: 1, version_state: "DRAFT",
  content_fingerprint: "a".repeat(64), declared_section_count: 0,
  declared_requirement_count: 0, declared_reference_count: 0,
  missing_declaration_count: 0, conflict_declaration_count: 0,
  supersedes_version_ref: null, review_ref: null, review_round_ref: null,
  created_by: actor, created_at: "2026-10-24T00:00:00Z",
  section_ids: [], requirement_refs: [], reference_refs: [],
  missing_declarations: [], conflict_declarations: [] } as const;
const receipt = { review_id: review, review_round_id: round, subject_type: "SOL-03",
  project_id: project, solution_outline_id: outline,
  solution_outline_version_id: version, policy_ref: "SOLUTION_OUTLINE_ALL_V1",
  reviewer_ids: [customer], state: "IN_REVIEW", round_no: 1,
  review_etag: '"v1"', submitted_by: actor,
  submitted_at: "2026-10-24T00:01:00Z" };
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
async function panel(role = "PROJECT_MANAGER", outcome = vi.fn().mockResolvedValue(receipt),
  versionDetail: unknown = detail) {
  const router = createAppRouter(createMemoryHistory());
  await router.push(`/projects/${project}/solution-outlines/${outline}/versions/${version}`);
  await router.isReady();
  const memberClient = { list: vi.fn().mockResolvedValue({ items: members,
    next_cursor: null, has_more: false }) };
  const submitter = { submit: outcome };
  const wrapper = mount(OutlineReviewSubmitPanel, { props: {
    session: await session(role), detail: versionDetail as
      Awaited<ReturnType<OutlineVersionReadClient["detail"]>>,
    members: memberClient as unknown as ProjectMemberReadClient,
    submitter: submitter as unknown as OutlineVersionSubmitReviewClient,
  }, global: { plugins: [router] } });
  await flushPromises();
  return { wrapper, memberClient, submitter };
}
describe("OutlineReviewSubmitPanel", () => {
  afterEach(() => { vi.restoreAllMocks(); sessionStorage.clear(); });
  it("offers active customer reviewers and links accepted Review without calling it approval", async () => {
    const { wrapper, submitter } = await panel();
    expect(wrapper.text()).toContain("客户甲");
    expect(wrapper.text()).not.toContain("实施乙");
    await wrapper.get(`input[value="${customer}"]`).setValue(true);
    await wrapper.get('input[type="checkbox"]:not([value])').setValue(true);
    await wrapper.findAll("button").find(button => button.text() === "提交客户方案大纲评审")!.trigger("click");
    await flushPromises();
    expect(submitter.submit).toHaveBeenCalledWith(project, outline, version,
      [customer], expect.stringMatching(/^outline-review-/));
    expect(wrapper.get(`a[href="/projects/${project}/reviews/${review}"]`).text())
      .toContain("打开评审");
    expect(wrapper.text()).toContain("这不是批准");
    expect(sessionStorage.length).toBe(0);
    wrapper.unmount();
  });
  it("retains exact reviewer/key on uncertain result until explicit retry", async () => {
    const outcome = vi.fn().mockRejectedValueOnce(new OutlineReviewSubmitError(
      "OUTLINE_REVIEW_UNCERTAIN")).mockResolvedValueOnce(receipt);
    const { wrapper, submitter } = await panel("PROJECT_MANAGER", outcome);
    await wrapper.get(`input[value="${customer}"]`).setValue(true);
    await wrapper.get('input[type="checkbox"]:not([value])').setValue(true);
    await wrapper.findAll("button").find(button => button.text() === "提交客户方案大纲评审")!.trigger("click");
    await flushPromises();
    expect(sessionStorage.length).toBe(1);
    const first = submitter.submit.mock.calls[0];
    await wrapper.get('input[type="checkbox"]:not([value])').setValue(true);
    await wrapper.findAll("button").find(button => button.text() === "按原操作号重试送审")!.trigger("click");
    await flushPromises();
    expect(submitter.submit.mock.calls[1]).toEqual(first);
    expect(sessionStorage.length).toBe(0);
    wrapper.unmount();
  });
  it("does not load candidates or submit for customer or non-draft", async () => {
    const customerPage = await panel("CUSTOMER_MEMBER");
    expect(customerPage.wrapper.text()).toContain("仅当前项目负责人可送审");
    expect(customerPage.memberClient.list).not.toHaveBeenCalled();
    expect(customerPage.submitter.submit).not.toHaveBeenCalled();
    customerPage.wrapper.unmount();
    const reviewed = await panel("PROJECT_MANAGER", vi.fn(), { ...detail,
      version_state: "IN_REVIEW", review_ref: review, review_round_ref: round });
    expect(reviewed.wrapper.text()).toContain("当前版本不是未送审草稿");
    expect(reviewed.wrapper.findAll("button").some(button =>
      button.text() === "提交客户方案大纲评审")).toBe(false);
    reviewed.wrapper.unmount();
  });
});
