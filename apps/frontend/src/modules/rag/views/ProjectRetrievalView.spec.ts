import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory, createRouter } from "vue-router";
import { describe, expect, it, vi } from "vitest";

import { SessionClient } from "@/modules/auth/api/sessionClient";
import { RAGRetrievalClient, RAGRetrievalError, type RAGContextView,
  type RAGRetrievalResult, type RAGRetrievalRun } from "@/modules/rag/api/retrievalClient";
import ProjectRetrievalView from "./ProjectRetrievalView.vue";

const actor = "01234567-89ab-4cde-8123-456789abcdef", project = "11234567-89ab-4cde-8123-456789abcdef";
const index = "21234567-89ab-4cde-8123-456789abcdef", runId = "31234567-89ab-4cde-8123-456789abcdef";
const job = "41234567-89ab-4cde-8123-456789abcdef", trace = "51234567-89ab-4cde-8123-456789abcdef";
const now = "2026-10-04T12:00:00Z";
const current: RAGRetrievalRun = Object.freeze({ retrieval_run_id: runId, project_id: project, requested_by: actor,
  project_index_ref: index, retrieval_policy_ref: "fts.project.v1", rerank_policy_ref: "none.v1", top_k: 5,
  rerank_state: "NOT_APPLICABLE", egress_state: "NOT_APPLICABLE", retrieval_state: "SUCCEEDED",
  quality_flags: Object.freeze(["CANDIDATE_SHORTFALL"]), degraded: false, error_code: null, job_id: job,
  created_at: now, completed_at: now, etag: '"v1"' });
const result: RAGRetrievalResult = Object.freeze({ retrieval_run_id: runId, project_id: project,
  quality_flags: Object.freeze(["CANDIDATE_SHORTFALL"]), degraded: false, completed_at: now,
  candidates: Object.freeze([{ candidate_id: "61234567-89ab-4cde-8123-456789abcdef", rank: 0,
    chunk_id: "71234567-89ab-4cde-8123-456789abcdef", document_version_ref: "81234567-89ab-4cde-8123-456789abcdef",
    parse_result_ref: "91234567-89ab-4cde-8123-456789abcdef", source_type: "PROJECT_RECORD" as const,
    source_locator: Object.freeze({ locator_type: "PAGE", page: 2 }), retrieval_channel: "FTS" as const,
    final_score_micros: 900000, score_parts: Object.freeze([{ score_kind: "FINAL" as const, score_ordinal: 1,
      raw_score_micros: 900000, normalized_score_micros: 900000, weight_micros: 1000000,
      weighted_score_micros: 900000, score_policy_ref: "fts.project.v1" }]), snippet: "最小上下文" }]) });
const context: RAGContextView = Object.freeze({ context_bundle_id: "a1234567-89ab-4cde-8123-456789abcdef",
  retrieval_run_id: runId, project_id: project, context_policy_ref: "project-documents.v1", token_budget: 100,
  token_count: 5, created_at: now, items: Object.freeze([{ ordinal: 0,
    chunk_id: "71234567-89ab-4cde-8123-456789abcdef", document_version_ref: "81234567-89ab-4cde-8123-456789abcdef",
    source_locator: Object.freeze({ locator_type: "PAGE", page: 2 }), snippet_start: 0, snippet_end: 5,
    token_count: 5, snippet: "最小上下文" }]) });
function json(data: unknown) { return new Response(JSON.stringify({ data, trace_id: trace }),
  { status: 200, headers: { "Content-Type": "application/json" } }); }
async function session(role = "PROJECT_MANAGER") {
  const fetcher = vi.fn().mockResolvedValueOnce(json({ user: { user_id: actor, username_display: "用户" },
    deployment_role: "NONE", password_change_required: false,
    authorized_projects: [{ project_id: project, name: "项目", role }],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "c".repeat(64) }));
  const value = new SessionClient(fetcher as typeof fetch); await value.login("user", "synthetic-only"); return value;
}
async function view(path: string, auth: SessionClient, api: RAGRetrievalClient) {
  const router = createRouter({ history: createMemoryHistory(), routes: [
    { path: "/projects/:projectId/retrievals/new", name: "project-retrieval-new", component: ProjectRetrievalView },
    { path: "/projects/:projectId/retrievals/:runId", name: "project-retrieval-detail", component: ProjectRetrievalView },
    { path: "/projects/:projectId", name: "project-detail", component: { template: "<p>project</p>" } },
    { path: "/projects/:projectId/jobs/:jobId", name: "project-job-detail", component: { template: "<p>job</p>" } },
    { path: "/login", name: "login", component: { template: "<p>login</p>" } },
  ] });
  await router.push(path); await router.isReady();
  const wrapper = mount(ProjectRetrievalView, { props: { session: auth, retrievals: api }, global: { plugins: [router] } });
  await flushPromises(); return { wrapper, router };
}

describe("ProjectRetrievalView", () => {
  it("keeps the query out of URL and storage, requires explicit scope confirmation, then clears it after create", async () => {
    const auth = await session(); const api = new RAGRetrievalClient(auth);
    const create = vi.spyOn(api, "create").mockResolvedValue({ retrieval_run_id: runId, job_id: job });
    vi.spyOn(api, "getRun").mockResolvedValue({ ...current, retrieval_state: "RUNNING", completed_at: null, etag: '"v0"' });
    const storage = vi.spyOn(Storage.prototype, "setItem");
    const { wrapper, router } = await view(`/projects/${project}/retrievals/new`, auth, api);
    await wrapper.get("textarea").setValue("机密查询正文");
    await wrapper.get('input[autocomplete="off"]').setValue(index);
    expect(wrapper.get('button[type="submit"]').attributes("disabled")).toBeDefined();
    await wrapper.get('.confirm input[type="checkbox"]').setValue(true);
    await wrapper.get("form").trigger("submit"); await flushPromises();
    expect(create).toHaveBeenCalledWith(project, expect.objectContaining({ query: "机密查询正文", project_index_ref: index, top_k: 5 }),
      expect.stringMatching(/^[0-9a-f-]{36}$/));
    expect(router.currentRoute.value.name).toBe("project-retrieval-detail");
    expect(router.currentRoute.value.fullPath).not.toContain("机密查询正文");
    expect(wrapper.text()).not.toContain("机密查询正文"); expect(storage).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it("shows only current server projections, score details and minimum context", async () => {
    const auth = await session(); const api = new RAGRetrievalClient(auth);
    vi.spyOn(api, "getRun").mockResolvedValue(current); vi.spyOn(api, "getResult").mockResolvedValue(result);
    vi.spyOn(api, "getContext").mockResolvedValue(context);
    const { wrapper } = await view(`/projects/${project}/retrievals/${runId}`, auth, api);
    expect(wrapper.text()).toContain("已完成"); expect(wrapper.text()).toContain("最小上下文");
    expect(wrapper.text()).toContain("PROJECT_RECORD"); expect(wrapper.text()).toContain("page=2");
    expect(wrapper.text()).not.toContain("bundle_fingerprint");
    expect(wrapper.findAll("textarea")).toHaveLength(0);
    wrapper.unmount();
  });

  it("clears all prior result/context when one current-authority read fails", async () => {
    const auth = await session(); const api = new RAGRetrievalClient(auth);
    vi.spyOn(api, "getRun").mockResolvedValue(current); vi.spyOn(api, "getResult").mockResolvedValue(result);
    vi.spyOn(api, "getContext").mockRejectedValue(new RAGRetrievalError("RESOURCE_NOT_FOUND"));
    const { wrapper } = await view(`/projects/${project}/retrievals/${runId}`, auth, api);
    expect(wrapper.get('[role="alert"]').text()).toContain("无权访问");
    expect(wrapper.find("#retrieval-results").exists()).toBe(false); expect(wrapper.find("#retrieval-context").exists()).toBe(false);
    expect(wrapper.find("dl").exists()).toBe(false); wrapper.unmount();
  });

  it("uses one in-memory cancellation key again after an uncertain outcome", async () => {
    const auth = await session(); const api = new RAGRetrievalClient(auth);
    const running = { ...current, retrieval_state: "RUNNING" as const, completed_at: null, etag: '"v0"' };
    vi.spyOn(api, "getRun").mockResolvedValue(running);
    const cancel = vi.spyOn(api, "cancel").mockRejectedValue(new RAGRetrievalError("RAG_RETRIEVAL_UNCERTAIN"));
    const { wrapper } = await view(`/projects/${project}/retrievals/${runId}`, auth, api);
    const form = wrapper.findAll("form").find(item => item.text().includes("申请取消当前检索"))!;
    await form.get("textarea").setValue("不再需要"); await form.get('input[type="checkbox"]').setValue(true);
    await form.trigger("submit"); await flushPromises();
    expect(wrapper.get('[role="alert"]').text()).toContain("原操作号仍保留");
    await form.trigger("submit"); await flushPromises();
    expect(cancel).toHaveBeenCalledTimes(2); expect(cancel.mock.calls[1]?.[2]).toBe(cancel.mock.calls[0]?.[2]);
    wrapper.unmount();
  });

  it("does not expose create controls to customer members", async () => {
    const auth = await session("CUSTOMER_MEMBER"); const api = new RAGRetrievalClient(auth);
    const { wrapper } = await view(`/projects/${project}/retrievals/new`, auth, api);
    expect(wrapper.text()).toContain("不能创建检索"); expect(wrapper.find("form").exists()).toBe(false);
    wrapper.unmount();
  });
});
