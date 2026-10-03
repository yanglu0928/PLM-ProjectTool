import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory } from "vue-router";
import { describe, expect, it, vi } from "vitest";
import { createAppRouter } from "@/app/router";
import type { AISubmissionClient } from "@/modules/ai/api/aiSubmissionClient";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import type { DocumentReadClient } from "@/modules/document/api/documentReadClient";
import ProjectAISubmitView from "./ProjectAISubmitView.vue";

const project = "01234567-89ab-4cde-8123-456789abcdef", provider = "11234567-89ab-4cde-8123-456789abcdef";
const model = "21234567-89ab-4cde-8123-456789abcdef", document = "31234567-89ab-4cde-8123-456789abcdef";
const version = "41234567-89ab-4cde-8123-456789abcdef", previewId = "51234567-89ab-4cde-8123-456789abcdef";
const authorizationId = "61234567-89ab-4cde-8123-456789abcdef", task = "71234567-89ab-4cde-8123-456789abcdef";
const job = "81234567-89ab-4cde-8123-456789abcdef", actor = "91234567-89ab-4cde-8123-456789abcdef";
const trace = "a1234567-89ab-4cde-8123-456789abcdef", now = "2026-10-03T12:00:00Z", expires = "2026-10-03T12:30:00Z";
const choices = { task_policies: [{ reference: "gap-analysis.v1", policy_version: 1, task_type: "GAP_ANALYSIS",
  purpose_ref: "project-gap-analysis.v1", output_schema_ref: "gap-output.v2", context_policy_ref: "no-retrieval.v1",
  parameter_fields: [{ name: "language", value_type: "STRING", required: true, max_length: 16, minimum: null,
    maximum: null, allowed_values: ["zh-CN"] }] }], egress_policies: [{ reference: "minimal-document-text.v1",
  allowed_data_categories: ["DOCUMENT_TEXT"], max_record_count: 50, max_payload_bytes: 1048576,
  max_input_tokens: 32768, max_retry_attempts: 2, risk_codes: ["EXTERNAL_PROCESSING"], ttl_seconds: 1800 }],
  routes: [{ provider_id: provider, model_id: model, provider_display_name: "合成服务", data_region: "cn-beijing",
    provider_model_key: "business-chat", model_revision: "v1" }] } as const;
const preview = { preview_id: previewId, project_id: project, purpose_ref: "project-gap-analysis.v1",
  provider_id: provider, model_id: model, provider_config_version_id: trace, data_region: "cn-beijing",
  source_refs: [{ resource_type: "DOC-02" as const, resource_id: document, version_id: version }],
  allowed_data_categories: ["DOCUMENT_TEXT"], minimal_payload_policy_ref: "minimal-document-text.v1",
  max_payload_bytes: 1048576, max_input_tokens: 32768, max_retry_attempts: 2,
  ai_task_plan: { task_type: "GAP_ANALYSIS", prompt_policy_ref: "gap-analysis.v1", output_schema_ref: "gap-output.v2",
    context_policy_ref: "no-retrieval.v1", task_parameters: { language: "zh-CN" } }, estimated_record_count: 1,
  payload_fingerprint: "a".repeat(64), source_refs_fingerprint: "b".repeat(64), preview_fingerprint: "c".repeat(64),
  risk_codes: ["EXTERNAL_PROCESSING"], created_at: now, expires_at: expires } as const;
const authorization = { authorization_id: authorizationId, preview_id: previewId, project_id: project,
  preview_fingerprint: preview.preview_fingerprint, approved_by: actor, approved_role: "PROJECT_MANAGER",
  approved_at: now, valid_until: expires, state: "AUTHORIZED" as const, etag: '"v0"' };
function response(data: unknown) { return new Response(JSON.stringify({ data, trace_id: trace }),
  { status: 200, headers: { "Content-Type": "application/json" } }); }
async function auth(role: string) { const session = new SessionClient(vi.fn().mockResolvedValue(response({
  user: { user_id: actor, username_display: "用户" }, deployment_role: "NONE", password_change_required: false,
  authorized_projects: [{ project_id: project, name: "项目", role }], absolute_expires_at: "2030-01-01T12:00:00Z",
  idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "d".repeat(64) })) as typeof fetch);
  await session.login("user", "synthetic-only"); return session; }
function services(withRoutes = true) { const submission = { options: vi.fn().mockResolvedValue({ ...choices, routes: withRoutes ? choices.routes : [] }),
  createPreview: vi.fn().mockResolvedValue(preview), authorize: vi.fn().mockResolvedValue(authorization),
  createTask: vi.fn().mockResolvedValue({ ai_task_id: task, job_id: job }), revoke: vi.fn().mockResolvedValue(undefined) };
  const documents = { list: vi.fn().mockResolvedValue({ items: [{ document_id: document, scope: "PROJECT", category: "PROJECT_RECORD",
    subtype: null, title: "调研记录", display_name: "record.docx", state: "ACTIVE", latest_version_ref: version,
    effective_version_ref: version, created_at: now, etag: '"v0"' }], next_cursor: null, has_more: false }) };
  return { submission, documents }; }
async function view(role = "PROJECT_MANAGER", withRoutes = true) { const router = createAppRouter(createMemoryHistory());
  await router.push(`/projects/${project}/ai/new`); await router.isReady(); const svc = services(withRoutes);
  const wrapper = mount(ProjectAISubmitView, { props: { session: await auth(role), submission: svc.submission as unknown as AISubmissionClient,
    documents: svc.documents as unknown as DocumentReadClient, keyFactory: (() => { let i = 0; return () => `operation-key-${++i}`.padEnd(16, "0"); })() },
    global: { plugins: [router] } }); await flushPromises(); return { wrapper, ...svc }; }
function button(wrapper: Awaited<ReturnType<typeof view>>["wrapper"], text: string) { return wrapper.findAll("button").find(item => item.text().includes(text))!; }

describe("ProjectAISubmitView", () => {
  it("keeps preview, authorization and task creation as three explicit actions", async () => { const { wrapper, submission } = await view();
    expect(wrapper.text()).toContain("三个独立步骤"); expect(submission.createPreview).not.toHaveBeenCalled();
    await wrapper.get(`input[value="${document}"]`).setValue(true); await button(wrapper, "生成外发预览").trigger("click"); await flushPromises();
    expect(submission.createPreview).toHaveBeenCalledTimes(1); expect(submission.authorize).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("EXTERNAL_PROCESSING"); await wrapper.get("label.approval input").setValue(true);
    await button(wrapper, "明确授权本轮外发").trigger("click"); await flushPromises(); expect(submission.authorize).toHaveBeenCalledTimes(1);
    expect(submission.createTask).not.toHaveBeenCalled(); await button(wrapper, "创建AI任务").trigger("click"); await flushPromises();
    expect(submission.createTask).toHaveBeenCalledTimes(1); expect(wrapper.text()).toContain(task); wrapper.unmount(); });
  it("shows only fixed metadata and closes when no route is allowlisted", async () => { const { wrapper } = await view("PROJECT_MANAGER", false);
    expect(wrapper.text()).toContain("record.docx"); expect(wrapper.text()).toContain(version); expect(wrapper.text()).not.toContain("客户正文");
    expect(wrapper.text()).toContain("提交入口已关闭"); expect(button(wrapper, "生成外发预览").attributes("disabled")).toBeDefined(); wrapper.unmount(); });
  it("lets an implementation member preview but not self-authorize", async () => { const { wrapper, submission } = await view("IMPLEMENTATION_MEMBER");
    await wrapper.get(`input[value="${document}"]`).setValue(true); await button(wrapper, "生成外发预览").trigger("click"); await flushPromises();
    expect(wrapper.text()).toContain("不能批准外发"); expect(button(wrapper, "明确授权本轮外发")).toBeUndefined(); expect(submission.authorize).not.toHaveBeenCalled(); wrapper.unmount(); });
  it("does not load protected choices for an unauthorized role", async () => { const { wrapper, submission, documents } = await view("CUSTOMER_MEMBER");
    expect(wrapper.text()).toContain("不能创建AI任务"); expect(submission.options).not.toHaveBeenCalled(); expect(documents.list).not.toHaveBeenCalled(); wrapper.unmount(); });
  it("can revoke an authorization before task creation", async () => { const { wrapper, submission } = await view();
    await wrapper.get(`input[value="${document}"]`).setValue(true); await button(wrapper, "生成外发预览").trigger("click"); await flushPromises();
    await wrapper.get("label.approval input").setValue(true); await button(wrapper, "明确授权本轮外发").trigger("click"); await flushPromises();
    await button(wrapper, "创建前撤销授权").trigger("click"); await flushPromises(); expect(submission.revoke).toHaveBeenCalledTimes(1);
    expect(wrapper.text()).toContain("核对并明确授权"); wrapper.unmount(); });
});
