import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { ProjectReviewListClient } from "@/modules/review/api/projectReviewListClient";
import ProjectReviewListView from "./ProjectReviewListView.vue";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const other = "11234567-89ab-4cde-8123-456789abcdef";
const review = "21234567-89ab-4cde-8123-456789abcdef";
const round = "31234567-89ab-4cde-8123-456789abcdef";
const actor = "41234567-89ab-4cde-8123-456789abcdef";
const pending = { review_id: review, project_id: project,
  subject_ref: { resource_type: "SOL-06", resource_id: other },
  policy_code: "STRUCTURED_SPEC_ALL_V1", state: "IN_REVIEW", created_by: actor,
  created_at: "2026-10-19T04:00:00Z", etag: '"v1"', active_round: {
    review_round_id: round, round_no: 1, subject_version_ref: other,
    started_at: "2026-10-19T04:01:00Z", my_assignment: {
      assignment_id: actor, state: "PENDING", decision: null, decided_at: null,
    },
  },
};
const terminal = { ...pending, state: "APPROVED", etag: '"v2"', active_round: null };
async function session(): Promise<SessionClient> {
  const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ data: {
    user: { user_id: actor, username_display: "合成评审人" }, deployment_role: "NONE",
    password_change_required: false,
    authorized_projects: [{ project_id: project, name: "项目", role: "CUSTOMER_MEMBER" }],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64),
  }, trace_id: other }), { status: 200, headers: { "Content-Type": "application/json" } }));
  const api = new SessionClient(fetcher as typeof fetch);
  await api.login("reviewer", "synthetic-only"); return api;
}
async function page(reader: unknown) {
  const router = createAppRouter(createMemoryHistory());
  await router.push(`/projects/${project}/reviews`); await router.isReady();
  const account = await session();
  const wrapper = mount(ProjectReviewListView, { props: { session: account,
    reader: reader as ProjectReviewListClient }, global: { plugins: [router] } });
  await flushPromises(); return { router, wrapper, account };
}

describe("ProjectReviewListView", () => {
  afterEach(() => vi.restoreAllMocks());

  it("discovers pending Reviews through automatic empty-page continuation and exact detail links", async () => {
    const list = vi.fn().mockResolvedValueOnce({ items: [], next_cursor: "cursor-1", has_more: true })
      .mockResolvedValueOnce({ items: [pending], next_cursor: null, has_more: false });
    const { router, wrapper } = await page({ list });
    expect(router.resolve(`/projects/${project}/reviews`).name).toBe("project-reviews");
    expect(list.mock.calls).toEqual([[project, "my_pending", 50, null],
      [project, "my_pending", 50, "cursor-1"]]);
    expect(wrapper.text()).toContain("我的待决定");
    expect(wrapper.text()).not.toContain("输入评审编号");
    expect(wrapper.get(`a[href="/projects/${project}/reviews/${review}"]`).text())
      .toContain("打开评审并核对当前状态");
    wrapper.unmount();
  });

  it("labels a Section customer decision as a solution chapter", async () => {
    const section = { ...pending,
      subject_ref: { resource_type: "SOL-05", resource_id: other },
      policy_code: "SOLUTION_SECTION_ALL_V1" };
    const { wrapper } = await page({ list: vi.fn().mockResolvedValue({
      items: [section], next_cursor: null, has_more: false,
    }) });
    expect(wrapper.text()).toContain("评审中 · 方案章节");
    expect(wrapper.get(`a[href="/projects/${project}/reviews/${review}"]`).text()).toContain("打开评审");
    wrapper.unmount();
  });

  it("labels an Outline customer decision as a solution outline", async () => {
    const outline = { ...pending,
      subject_ref: { resource_type: "SOL-03", resource_id: other },
      policy_code: "SOLUTION_OUTLINE_ALL_V1" };
    const { wrapper } = await page({ list: vi.fn().mockResolvedValue({
      items: [outline], next_cursor: null, has_more: false,
    }) });
    expect(wrapper.text()).toContain("评审中 · 方案大纲");
    expect(wrapper.get(`a[href="/projects/${project}/reviews/${review}"]`).text()).toContain("打开评审");
    wrapper.unmount();
  });

  it("refreshes the pending view after a decision and keeps terminal history separate", async () => {
    const list = vi.fn().mockResolvedValueOnce({ items: [pending], next_cursor: null, has_more: false })
      .mockResolvedValueOnce({ items: [], next_cursor: null, has_more: false })
      .mockResolvedValueOnce({ items: [terminal], next_cursor: null, has_more: false });
    const { wrapper } = await page({ list });
    expect(wrapper.text()).toContain("我的待决定");
    await wrapper.findAll("button").find(button => button.text() === "刷新列表")!.trigger("click");
    await flushPromises();
    expect(wrapper.text()).not.toContain("我的待决定");
    expect(wrapper.text()).toContain("当前没有待处理评审");
    await wrapper.findAll("button").find(button => button.text() === "全部可见历史")!.trigger("click");
    await flushPromises();
    expect(list.mock.calls[2]).toEqual([project, "all", 50, null]);
    expect(wrapper.text()).toContain("已批准");
    expect(wrapper.text()).not.toContain("我的待决定"); wrapper.unmount();
  });

  it("clears old results on project switch and on later-page failure", async () => {
    const list = vi.fn().mockResolvedValue({ items: [pending], next_cursor: null, has_more: false });
    const { router, wrapper } = await page({ list });
    expect(wrapper.text()).toContain(review);
    await router.push(`/projects/${other}/reviews`); await flushPromises();
    expect(list).toHaveBeenCalledTimes(1);
    expect(wrapper.text()).toContain("没有此项目的读取权限");
    expect(wrapper.text()).not.toContain(review);
    wrapper.unmount();

    const failing = vi.fn().mockResolvedValueOnce({ items: [pending], next_cursor: "cursor-1",
      has_more: true }).mockRejectedValueOnce(new Error("读取失败"));
    const second = await page({ list: failing });
    expect(second.wrapper.get("[role=alert]").text()).toContain("读取失败");
    expect(second.wrapper.text()).not.toContain(review);
    second.wrapper.unmount();
  });

  it("clears server-discovered pending reviews when the session is revoked", async () => {
    const list = vi.fn().mockResolvedValue({ items: [pending], next_cursor: null, has_more: false });
    const { wrapper, account } = await page({ list });
    expect(wrapper.text()).toContain(review);
    await expect(account.logout("synthetic-logout-0001")).rejects.toThrow();
    await flushPromises();
    expect(wrapper.text()).toContain("请先登录");
    expect(wrapper.text()).not.toContain(review);
    wrapper.unmount();
  });
});
