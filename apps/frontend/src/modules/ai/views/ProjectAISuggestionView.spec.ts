import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import { AIReadClient } from "@/modules/ai/api/aiReadClient";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import ProjectAISuggestionView from "./ProjectAISuggestionView.vue";

const project = "01234567-89ab-4cde-8123-456789abcdef", task = "11234567-89ab-4cde-8123-456789abcdef";
const invocation = "21234567-89ab-4cde-8123-456789abcdef", document = "31234567-89ab-4cde-8123-456789abcdef";
const version = "41234567-89ab-4cde-8123-456789abcdef", trace = "51234567-89ab-4cde-8123-456789abcdef";
const other = "61234567-89ab-4cde-8123-456789abcdef", now = "2026-10-03T12:00:00Z";
const source = { source_ordinal: 1, document_id: document, document_version_id: version, precision: "PARSED_NODE",
  content_url: `/api/v1/projects/${project}/documents/${document}/versions/${version}/content`, locations: [{
    node_id: "line-1", kind: "TEXT_LINE", precision: "PARSED_NODE", display_label: "文本文档 / 字符 0–5",
    locator: { locator_type: "STRUCTURED_NODE", parse_record_id: trace, node_id: "line-1", source_locator: {
      locator_type: "TEXT_RANGE", section_path: "plain-text-root", start_offset: 0, end_offset: 5,
      normalized_fingerprint: "a".repeat(64) } } }] };
const suggestion = { ai_task_id: task, ai_invocation_id: invocation, suggestion_payload_id: other, project_id: project,
  suggestion_state: "AVAILABLE", fact_status: "NOT_FORMAL_FACT", quality_flags: ["REVIEW_REQUIRED"],
  input_versions: [{ resource_type: "DOC-02", resource_id: document, version_id: version }],
  provider: { ai_provider_id: other, provider_config_version_id: trace }, model: { ai_model_id: other, revision: "model-v1" },
  prompt_version_ref: { prompt_template_id: trace, version_no: 2 }, output_schema: { ref: "gap-output.v2", version: 2 },
  context: { content_plan_id: other, content_plan_version: 1, context_policy_ref: "project-documents.v1", mode: "NONE",
    retrieval_run_id: null, context_bundle_id: null }, payload: { schema_ref: "gap-output.v2", schema_version: 2, items: [{
      category: "PENDING_CONFIRMATION", title: "确认范围", summary: "需要确认范围", rationale: "节点依据",
      recommendation: "请维护实际范围", source_citations: [{ source_ordinal: 1, node_ids: ["line-1"] }],
      confirmation: { required: true, question: "实际范围是什么？", required_fields: [{ key: "SCOPE", label: "实际范围",
        prompt: "请填写实际范围", reason: "确定实施边界", required: true }] } }] },
  source_locations: [source], created_at: now, etag: '"v2"' };
function response(data: unknown, etag: string | null = '"v2"') { const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (etag) headers.ETag = etag;
  return new Response(JSON.stringify({ data, trace_id: trace }), { status: 200, headers }); }
function failure(status: number, code: string) { return new Response(JSON.stringify({ error: { code, message: "private detail" }, trace_id: trace }),
  { status, headers: { "Content-Type": "application/json" } }); }
async function session(restricted = false) { const api = new SessionClient(vi.fn().mockResolvedValue(response({
  user: { user_id: other, username_display: "合成用户" }, deployment_role: "NONE", password_change_required: restricted,
  authorized_projects: restricted ? [] : [{ project_id: project, name: "演示项目", role: "PROJECT_MANAGER" }],
  absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "a".repeat(64) }, null)) as typeof fetch);
  await api.login("user", "synthetic-only"); return api; }
async function view(auth: SessionClient, fetcher: typeof fetch) { const router = createAppRouter(createMemoryHistory());
  await router.push(`/projects/${project}/ai/${task}/suggestion`); await router.isReady();
  const wrapper = mount(ProjectAISuggestionView, { props: { session: auth, ai: new AIReadClient(fetcher) }, global: { plugins: [router] } });
  await flushPromises(); return { wrapper, router }; }

describe("ProjectAISuggestionView", () => {
  afterEach(() => vi.restoreAllMocks());
  it("does not read without identity or before password change", async () => { const fetcher = vi.fn();
    const absent = await view(new SessionClient(fetcher as typeof fetch), fetcher as typeof fetch); expect(absent.wrapper.text()).toContain("尚未读取当前身份"); absent.wrapper.unmount();
    const restricted = await view(await session(true), fetcher as typeof fetch); expect(restricted.wrapper.text()).toContain("须先修改密码"); expect(fetcher).not.toHaveBeenCalled(); restricted.wrapper.unmount(); });
  it("shows V2 location action and explicit maintenance guidance without a form", async () => {
    const { wrapper } = await view(await session(), vi.fn().mockResolvedValue(response({ ...suggestion, private_payload: "secret" })) as typeof fetch);
    expect(wrapper.text()).toContain("AI建议，不是正式业务事实"); expect(wrapper.text()).toContain("确认范围");
    expect(wrapper.text()).toContain("文本文档 / 字符 0–5"); expect(wrapper.text()).toContain("填写提示：请填写实际范围");
    expect(wrapper.text()).toContain("为什么需要：确定实施边界"); expect(wrapper.text()).toContain("实际范围（必填）");
    expect(wrapper.get(`a[href="${source.content_url}"]`).attributes("target")).toBe("_blank");
    expect(wrapper.find("form").exists()).toBe(false); expect(wrapper.text()).not.toContain("secret"); wrapper.unmount();
  });
  it("labels V1 as whole-document location", async () => { const v1 = { ...suggestion, output_schema: { ref: "gap-output.v1", version: 1 },
    payload: { schema_ref: "gap-output.v1", schema_version: 1, items: [{ category: "DIFFERENCE", title: "差异", summary: "摘要",
      rationale: "依据", recommendation: "建议", source_ordinals: [1] }] }, source_locations: [{ ...source, precision: "DOCUMENT",
      locations: [{ locator: { locator_type: "DOCUMENT" }, precision: "DOCUMENT", display_label: "整个文档版本" }] }] };
    const { wrapper } = await view(await session(), vi.fn().mockResolvedValue(response(v1)) as typeof fetch);
    expect(wrapper.text()).toContain("整个文档版本"); expect(wrapper.text()).toContain("没有结构化人工补充字段"); wrapper.unmount(); });
  it("clears data and hides private error details on authorization failure", async () => { const { wrapper } = await view(await session(),
    vi.fn().mockResolvedValue(failure(404, "RESOURCE_NOT_FOUND")) as typeof fetch);
    expect(wrapper.get('[role="alert"]').text()).toContain("无权查看"); expect(wrapper.html()).not.toContain("private detail"); wrapper.unmount(); });
  it("discards a late suggestion after route change", async () => { let resolve!: (value: Response) => void;
    const fetcher = vi.fn().mockImplementationOnce(() => new Promise<Response>(done => { resolve = done; }))
      .mockResolvedValueOnce(failure(404, "RESOURCE_NOT_FOUND")); const { wrapper, router } = await view(await session(), fetcher as typeof fetch);
    await router.push(`/projects/${project}/ai/${other}/suggestion`); await flushPromises(); resolve(response(suggestion)); await flushPromises();
    expect(wrapper.text()).not.toContain("确认范围"); expect(wrapper.get('[role="alert"]').text()).toContain("无权查看"); wrapper.unmount(); });
});
