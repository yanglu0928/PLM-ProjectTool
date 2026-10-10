import { describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { AISubmissionClient, AISubmissionError, type AIEgressPreviewInput } from "./aiSubmissionClient";

const project = "01234567-89ab-4cde-8123-456789abcdef", provider = "11234567-89ab-4cde-8123-456789abcdef";
const model = "21234567-89ab-4cde-8123-456789abcdef", document = "31234567-89ab-4cde-8123-456789abcdef";
const version = "41234567-89ab-4cde-8123-456789abcdef", previewId = "51234567-89ab-4cde-8123-456789abcdef";
const authorizationId = "61234567-89ab-4cde-8123-456789abcdef", task = "71234567-89ab-4cde-8123-456789abcdef";
const job = "81234567-89ab-4cde-8123-456789abcdef", trace = "91234567-89ab-4cde-8123-456789abcdef";
const config = "a1234567-89ab-4cde-8123-456789abcdef", actor = "b1234567-89ab-4cde-8123-456789abcdef";
const now = "2026-10-03T12:00:00Z", expires = "2026-10-03T12:30:00Z", valid = "2026-10-03T12:20:00Z";
const policy = { reference: "gap-analysis.v1", policy_version: 1, task_type: "GAP_ANALYSIS",
  purpose_ref: "project-gap-analysis.v1", output_schema_ref: "gap-output.v2", context_policy_ref: "no-retrieval.v1",
  parameter_fields: [{ name: "language", value_type: "STRING", required: true, max_length: 16,
    minimum: null, maximum: null, allowed_values: ["zh-CN"] }] };
const egress = { reference: "minimal-document-text.v1", allowed_data_categories: ["DOCUMENT_TEXT"],
  max_record_count: 50, max_payload_bytes: 1048576, max_input_tokens: 32768, max_retry_attempts: 2,
  risk_codes: ["EXTERNAL_PROCESSING"], ttl_seconds: 1800 };
const route = { provider_id: provider, model_id: model, provider_display_name: "合成服务", data_region: "cn-beijing",
  provider_model_key: "business-chat", model_revision: "v1" };
const plan = { task_type: policy.task_type, prompt_policy_ref: policy.reference, output_schema_ref: policy.output_schema_ref,
  context_policy_ref: policy.context_policy_ref, task_parameters: { language: "zh-CN" } };
const input: AIEgressPreviewInput = { purpose_ref: policy.purpose_ref, provider_id: provider, model_id: model,
  source_refs: [{ resource_type: "DOC-02", resource_id: document, version_id: version }],
  allowed_data_categories: egress.allowed_data_categories, minimal_payload_policy_ref: egress.reference,
  max_payload_bytes: egress.max_payload_bytes, max_input_tokens: egress.max_input_tokens,
  max_retry_attempts: egress.max_retry_attempts, ai_task_plan: plan };
const preview = { ...input, preview_id: previewId, project_id: project, operation_type: "AI_TASK",
  provider_config_version_id: config, data_region: "cn-beijing", estimated_record_count: 1,
  payload_fingerprint: "a".repeat(64), source_refs_fingerprint: "b".repeat(64), preview_fingerprint: "c".repeat(64),
  risk_codes: ["EXTERNAL_PROCESSING"], created_at: now, expires_at: expires };
const authorization = { authorization_id: authorizationId, preview_id: previewId, project_id: project,
  preview_fingerprint: preview.preview_fingerprint, purpose_ref: policy.purpose_ref, operation_type: "AI_TASK",
  provider_id: provider, provider_config_version_id: config, model_id: model, data_region: "cn-beijing",
  allowed_data_categories: ["DOCUMENT_TEXT"], minimal_payload_policy_ref: egress.reference,
  max_record_count: 1, max_payload_bytes: egress.max_payload_bytes, max_input_tokens: egress.max_input_tokens,
  max_retry_attempts: egress.max_retry_attempts, payload_fingerprint: "a".repeat(64),
  source_refs_fingerprint: "b".repeat(64), approved_by: actor, approved_role: "PROJECT_MANAGER",
  approved_at: now, valid_until: valid, state: "AUTHORIZED", etag: '"v0"' };
function json(data: unknown, status = 200, headers: Record<string, string> = {}) { return new Response(JSON.stringify({ data, trace_id: trace }),
  { status, headers: { "Content-Type": "application/json", ...headers } }); }
function error(status: number, code: string) { return new Response(JSON.stringify({ error: { code, message: "private" }, trace_id: trace }),
  { status, headers: { "Content-Type": "application/json" } }); }
function login() { return json({ user: { user_id: actor, username_display: "合成用户" }, deployment_role: "NONE",
  password_change_required: false, authorized_projects: [{ project_id: project, name: "项目", role: "PROJECT_MANAGER" }],
  absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "d".repeat(64) }); }

describe("AISubmissionClient", () => {
  it("executes options, preview, explicit authorization, task create and revoke with distinct keys", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(login())
      .mockResolvedValueOnce(json({ task_policies: [policy], egress_policies: [egress], routes: [route] }))
      .mockResolvedValueOnce(json(preview, 201, { Location: `/api/v1/projects/${project}/egress-previews/${previewId}` }))
      .mockResolvedValueOnce(json(authorization, 201, { ETag: '"v0"' }))
      .mockResolvedValueOnce(json({ ai_task_id: task, job_id: job }, 202, { Location: `/api/v1/projects/${project}/ai-tasks/${task}` }))
      .mockResolvedValueOnce(json({ authorization_id: authorizationId, revocation_id: config, state: "REVOKED",
        revoked_at: now, etag: '"v1"' }, 200, { ETag: '"v1"' }));
    const session = new SessionClient(fetcher as typeof fetch); await session.login("user", "synthetic-only");
    const client = new AISubmissionClient(session, fetcher as typeof fetch);
    const options = await client.options(project); expect(options.routes[0]).toEqual(route);
    const first = await client.createPreview(project, input, "preview-key-0000001");
    const approved = await client.authorize(project, first, valid, "authorize-key-00001");
    const created = await client.createTask(project, plan, input.source_refs, approved, "task-create-key-001");
    expect(created).toEqual({ ai_task_id: task, job_id: job });
    await client.revoke(project, approved, "不再需要", "revoke-key-0000001");
    expect(fetcher.mock.calls.slice(2).map(call => call[1].headers["Idempotency-Key"]))
      .toEqual(["preview-key-0000001", "authorize-key-00001", "task-create-key-001", "revoke-key-0000001"]);
    expect(fetcher.mock.calls[3][1].headers).toMatchObject({ "If-Match": '"v0"', "X-CSRF-Token": "d".repeat(64) });
    expect(fetcher.mock.calls[4][0]).toBe(`/api/v1/projects/${project}/ai-tasks`);
    expect(JSON.parse(fetcher.mock.calls[4][1].body)).not.toHaveProperty("provider_id");
  });
  it("strictly rejects malformed or duplicate options", async () => { const fetcher = vi.fn().mockResolvedValueOnce(login())
    .mockResolvedValueOnce(json({ task_policies: [policy, policy], egress_policies: [egress], routes: [] }));
    const session = new SessionClient(fetcher as typeof fetch); await session.login("user", "synthetic-only");
    await expect(new AISubmissionClient(session, fetcher as typeof fetch).options(project)).rejects.toMatchObject({ code: "AI_SUBMISSION_UNCERTAIN" }); });
  it("maps safe errors without exposing server messages", async () => { const fetcher = vi.fn().mockResolvedValueOnce(login()).mockResolvedValueOnce(error(503, "AI_PROVIDER_UNAVAILABLE"));
    const session = new SessionClient(fetcher as typeof fetch); await session.login("user", "synthetic-only");
    await expect(new AISubmissionClient(session, fetcher as typeof fetch).options(project)).rejects.toMatchObject({ code: "AI_PROVIDER_UNAVAILABLE" }); });
  it("invokes the native-style options transport without a class receiver", async () => {
    const calls: unknown[] = [];
    const fetcher = function(this: unknown, ...args: Parameters<typeof fetch>) {
      if (this !== undefined) throw new TypeError("Illegal invocation");
      calls.push(args);
      return Promise.resolve(json({ task_policies: [policy], egress_policies: [egress], routes: [route] }));
    } as typeof fetch;
    const client = new AISubmissionClient(new SessionClient(vi.fn() as typeof fetch), fetcher);
    await expect(client.options(project)).resolves.toMatchObject({ routes: [route] });
    expect(calls).toHaveLength(1);
  });
  it("marks transport failures uncertain and never retries", async () => { const fetcher = vi.fn().mockResolvedValueOnce(login()).mockRejectedValueOnce(new TypeError("network private"));
    const session = new SessionClient(fetcher as typeof fetch); await session.login("user", "synthetic-only");
    await expect(new AISubmissionClient(session, fetcher as typeof fetch).createPreview(project, input, "preview-key-0000001"))
      .rejects.toMatchObject({ code: "AI_SUBMISSION_UNCERTAIN", uncertain: true }); expect(fetcher).toHaveBeenCalledTimes(2); });
  it("rejects duplicate fixed inputs before transport", async () => { const fetcher = vi.fn().mockResolvedValueOnce(login()); const session = new SessionClient(fetcher as typeof fetch);
    await session.login("user", "synthetic-only"); const client = new AISubmissionClient(session, fetcher as typeof fetch);
    await expect(client.createPreview(project, { ...input, source_refs: [input.source_refs[0]!, input.source_refs[0]!] }, "preview-key-0000001"))
      .rejects.toBeInstanceOf(AISubmissionError); expect(fetcher).toHaveBeenCalledTimes(1); });
  it("refuses authorization past preview expiry", async () => { const fetcher = vi.fn().mockResolvedValueOnce(login()); const session = new SessionClient(fetcher as typeof fetch);
    await session.login("user", "synthetic-only"); const client = new AISubmissionClient(session, fetcher as typeof fetch);
    await expect(client.authorize(project, preview, "2026-10-03T12:31:00Z", "authorize-key-00001"))
      .rejects.toMatchObject({ code: "AI_SUBMISSION_INVALID_INPUT" }); expect(fetcher).toHaveBeenCalledTimes(1); });
});
