import { afterEach, describe, expect, it, vi } from "vitest";
import { AIReadClient, AIReadError, parseAISuggestion, parseAITask } from "./aiReadClient";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const task = "11234567-89ab-4cde-8123-456789abcdef";
const invocation = "21234567-89ab-4cde-8123-456789abcdef";
const document = "31234567-89ab-4cde-8123-456789abcdef";
const version = "41234567-89ab-4cde-8123-456789abcdef";
const trace = "51234567-89ab-4cde-8123-456789abcdef";
const other = "61234567-89ab-4cde-8123-456789abcdef";
const now = "2026-10-03T12:00:00.123456Z";

const input = { resource_type: "DOC-02", resource_id: document, version_id: version };
const taskView = {
  ai_task_id: task, project_id: project, task_type: "GAP_ANALYSIS", requested_by: other,
  input_refs: [input], prompt_policy_ref: "gap-analysis.v1", prompt_policy_version: 1,
  prompt_version_ref: { prompt_template_id: other, version_no: 2 }, output_schema_ref: "gap-output.v2",
  context_policy_ref: "project-documents.v1", egress_authorization_ref: other, job_id: other,
  current_invocation_id: invocation, task_state: "SUCCEEDED", suggestion_state: "AVAILABLE",
  trace_id: trace, error_code: null, retryable: null, requested_at: now, started_at: now,
  completed_at: now, etag: '"v2"',
};
const executionContext = { content_plan_id: other, content_plan_version: 1,
  context_policy_ref: "project-documents.v1", mode: "NONE", retrieval_run_id: null, context_bundle_id: null };
const invocationView = {
  ai_invocation_id: invocation, ai_task_id: task, attempt_no: 2,
  provider: { ai_provider_id: other, provider_config_version_id: trace },
  model: { ai_model_id: other, revision: "model-v1" },
  prompt_version_ref: { prompt_template_id: trace, version_no: 2 },
  output_schema: { ref: "gap-output.v2", version: 2 }, context: executionContext,
  invocation_state: "SUCCEEDED", schema_validation_state: "VALID",
  usage: { input_tokens: 100, output_tokens: 20 }, latency_ms: 300, error_code: null,
  retryable: null, created_at: now, started_at: now, completed_at: now,
};
const payload = { schema_ref: "gap-output.v2", schema_version: 2, items: [{
  category: "PENDING_CONFIRMATION", title: "确认范围", summary: "需要确认范围", rationale: "节点依据",
  recommendation: "请维护实际范围", source_citations: [{ source_ordinal: 1, node_ids: ["line-1"] }],
  confirmation: { required: true, question: "实际范围是什么？", required_fields: [{
    key: "SCOPE", label: "实际范围", prompt: "请填写实际范围", reason: "确定实施边界", required: true,
  }] },
}] };
const suggestion = {
  ai_task_id: task, ai_invocation_id: invocation, suggestion_payload_id: other, project_id: project,
  suggestion_state: "AVAILABLE", fact_status: "NOT_FORMAL_FACT", quality_flags: ["REVIEW_REQUIRED"],
  input_versions: [input], provider: invocationView.provider, model: invocationView.model,
  prompt_version_ref: invocationView.prompt_version_ref, output_schema: invocationView.output_schema,
  context: executionContext, payload, source_locations: [{ source_ordinal: 1, document_id: document,
    document_version_id: version, precision: "PARSED_NODE",
    content_url: `/api/v1/projects/${project}/documents/${document}/versions/${version}/content`,
    locations: [{ node_id: "line-1", kind: "TEXT_LINE", precision: "PARSED_NODE",
      display_label: "文本文档 / 字符 0–5", locator: { locator_type: "STRUCTURED_NODE",
        parse_record_id: trace, node_id: "line-1", source_locator: { locator_type: "TEXT_RANGE",
          section_path: "plain-text-root", start_offset: 0, end_offset: 5, normalized_fingerprint: "a".repeat(64) } } }],
  }], created_at: now, etag: '"v2"',
};

function response(data: unknown, etag: string | null = null): Response {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (etag !== null) headers.ETag = etag;
  return new Response(JSON.stringify({ data, trace_id: trace }), { status: 200, headers });
}
function failure(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: "private detail" }, trace_id: trace }),
    { status, headers: { "Content-Type": "application/json" } });
}
function client(...results: Response[]) {
  const fetcher = vi.fn();
  for (const result of results) fetcher.mockResolvedValueOnce(result);
  return { api: new AIReadClient(fetcher as typeof fetch), fetcher };
}

describe("AIReadClient", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); });

  it("reads frozen Task list/detail by same-origin GET and strips unknown fields", async () => {
    const listed = { ...taskView, private_payload: "secret" };
    const { api, fetcher } = client(response({ items: [listed], next_cursor: "ait1.ABC_def", has_more: true }),
      response(listed, '"v2"'));
    const page = await api.listTasks(project, 20);
    expect(fetcher.mock.calls[0]).toEqual([`/api/v1/projects/${project}/ai-tasks?page_size=20`, expect.objectContaining({
      method: "GET", credentials: "same-origin", cache: "no-store", redirect: "error", headers: { Accept: "application/json" },
    })]);
    expect(page.next_cursor).toBe("ait1.ABC_def");
    expect(JSON.stringify(page)).not.toContain("secret");
    expect(Object.isFrozen(page.items[0])).toBe(true);
    await expect(api.getTask(project, task)).resolves.toMatchObject({ ai_task_id: task, etag: '"v2"' });
  });

  it("passes opaque Task and Invocation cursors without decoding", async () => {
    const { api, fetcher } = client(response({ items: [], next_cursor: null, has_more: false }),
      response({ items: [], next_cursor: null, has_more: false }));
    await api.listTasks(project, 50, "ait1.ABC_def");
    await api.listInvocations(project, task, 25, "aii1.XYZ_123");
    expect(fetcher.mock.calls[0][0]).toContain("cursor=ait1.ABC_def");
    expect(fetcher.mock.calls[1][0]).toContain("cursor=aii1.XYZ_123");
  });

  it("rejects Task page order drift", async () => {
    const older = { ...taskView, ai_task_id: other, requested_at: "2026-10-03T11:00:00Z",
      started_at: "2026-10-03T11:00:00Z", completed_at: "2026-10-03T11:00:00Z" };
    await expect(client(response({ items: [older, taskView], next_cursor: null, has_more: false })).api.listTasks(project))
      .rejects.toMatchObject({ code: "AI_READ_UNAVAILABLE" });
  });

  it("reads minimal Invocation history and rejects order drift", async () => {
    const first = { ...invocationView, private_response: "secret" };
    const older = { ...invocationView, ai_invocation_id: other, attempt_no: 1 };
    const { api } = client(response({ items: [first, older], next_cursor: null, has_more: false }));
    const page = await api.listInvocations(project, task);
    expect(page.items.map(item => item.attempt_no)).toEqual([2, 1]);
    expect(JSON.stringify(page)).not.toContain("secret");
    await expect(client(response({ items: [older, first], next_cursor: null, has_more: false })).api
      .listInvocations(project, task)).rejects.toMatchObject({ code: "AI_READ_UNAVAILABLE" });
  });

  it("reads only NOT_FORMAL_FACT V2 with fixed Document location and required prompts", async () => {
    const { api } = client(response({ ...suggestion, private_response: "secret" }, '"v2"'));
    const value = await api.getSuggestion(project, task);
    expect(value.fact_status).toBe("NOT_FORMAL_FACT");
    expect(value.payload.items[0]).toMatchObject({ confirmation: { required: true,
      required_fields: [{ key: "SCOPE", prompt: "请填写实际范围" }] } });
    expect(value.source_locations[0]).toMatchObject({ precision: "PARSED_NODE",
      locations: [{ node_id: "line-1" }] });
    expect(JSON.stringify(value)).not.toContain("secret");
    expect(Object.isFrozen(value.payload.items[0])).toBe(true);
  });

  it("accepts V1 only as DOCUMENT precision", () => {
    const v1 = { ...suggestion, output_schema: { ref: "gap-output.v1", version: 1 },
      payload: { schema_ref: "gap-output.v1", schema_version: 1, items: [{ category: "DIFFERENCE",
        title: "差异", summary: "摘要", rationale: "依据", recommendation: "建议", source_ordinals: [1] }] },
      source_locations: [{ ...suggestion.source_locations[0], precision: "DOCUMENT",
        locations: [{ locator: { locator_type: "DOCUMENT" }, precision: "DOCUMENT", display_label: "整个文档版本" }] }] };
    expect(parseAISuggestion(v1, project, task).source_locations[0]?.precision).toBe("DOCUMENT");
  });

  it.each([
    { ...suggestion, fact_status: "FORMAL_FACT" },
    { ...suggestion, payload: { ...payload, items: [{ ...payload.items[0], private_text: "secret" }] } },
    { ...suggestion, source_locations: [{ ...suggestion.source_locations[0], content_url: "/api/v1/admin/secrets" }] },
    { ...suggestion, source_locations: [{ ...suggestion.source_locations[0], locations: [{
      ...suggestion.source_locations[0]!.locations[0], node_id: "not-sent" }] }] },
    { ...suggestion, input_versions: [{ ...input, version_id: other }] },
  ])("rejects unsafe Suggestion shape %#", bad => {
    expect(() => parseAISuggestion(bad, project, task)).toThrowError(AIReadError);
  });

  it.each([
    { ...taskView, project_id: other }, { ...taskView, ai_task_id: other },
    { ...taskView, input_refs: [input, input] }, { ...taskView, etag: 'W/"v2"' },
    { ...taskView, started_at: "2026-10-03T11:59:59Z" },
  ])("rejects inconsistent Task shape %#", bad => {
    expect(() => parseAITask(bad, project, task)).toThrowError(AIReadError);
  });

  it.each(["../admin", project.toUpperCase(), "00000000-0000-0000-0000-000000000000"])(
    "rejects unsafe identifiers before network: %s", async bad => {
      const { api, fetcher } = client(response({ items: [], next_cursor: null, has_more: false }));
      await expect(api.listTasks(bad)).rejects.toMatchObject({ code: "AI_READ_INVALID_INPUT" });
      await expect(api.getSuggestion(project, bad)).rejects.toMatchObject({ code: "AI_READ_INVALID_INPUT" });
      expect(fetcher).not.toHaveBeenCalled();
    });

  it.each([0, 101, 1.5, Number.NaN])("rejects invalid page size %s", async size => {
    const { api, fetcher } = client(response({ items: [], next_cursor: null, has_more: false }));
    await expect(api.listTasks(project, size)).rejects.toMatchObject({ code: "AI_READ_INVALID_INPUT" });
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("rejects malformed or wrong-family cursors before network", async () => {
    const { api, fetcher } = client(response({ items: [], next_cursor: null, has_more: false }));
    await expect(api.listTasks(project, 50, "aii1.wrong")).rejects.toMatchObject({ code: "AI_READ_INVALID_INPUT" });
    await expect(api.listInvocations(project, task, 50, "ait1.wrong")).rejects.toMatchObject({ code: "AI_READ_INVALID_INPUT" });
    expect(fetcher).not.toHaveBeenCalled();
  });

  it.each([[401, "AUTH_SESSION_EXPIRED"], [403, "LICENSE_OPERATION_DENIED"], [404, "RESOURCE_NOT_FOUND"]] as const)(
    "maps only matching safe error %s %s", async (status, code) => {
      const error = await client(failure(status, code)).api.getSuggestion(project, task).catch(value => value);
      expect(error).toMatchObject({ code });
      expect(String(error)).not.toContain("private");
    });

  it("rejects mismatched status, non-JSON and ETag mismatch", async () => {
    await expect(client(failure(403, "RESOURCE_NOT_FOUND")).api.getTask(project, task))
      .rejects.toMatchObject({ code: "AI_READ_UNAVAILABLE" });
    await expect(client(new Response("private", { headers: { "Content-Type": "text/html" } })).api.getTask(project, task))
      .rejects.toMatchObject({ code: "AI_READ_UNAVAILABLE" });
    await expect(client(response(taskView, '"v3"')).api.getTask(project, task))
      .rejects.toMatchObject({ code: "AI_READ_UNAVAILABLE" });
  });

  it("aborts timeout once without retry or private detail", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn().mockImplementation((_path: string, options: RequestInit) => new Promise((_resolve, reject) => {
      options.signal?.addEventListener("abort", () => reject(new Error("private timeout")));
    }));
    const pending = expect(new AIReadClient(fetcher as typeof fetch, 100).getTask(project, task))
      .rejects.toMatchObject({ code: "AI_READ_UNAVAILABLE" });
    await vi.advanceTimersByTimeAsync(101); await pending;
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});
