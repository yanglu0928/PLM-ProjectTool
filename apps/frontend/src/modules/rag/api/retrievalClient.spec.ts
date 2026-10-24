import { describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { RAGRetrievalClient, RAGRetrievalError } from "./retrievalClient";

const actor = "01234567-89ab-4cde-8123-456789abcdef", project = "11234567-89ab-4cde-8123-456789abcdef";
const index = "21234567-89ab-4cde-8123-456789abcdef", runId = "31234567-89ab-4cde-8123-456789abcdef";
const job = "41234567-89ab-4cde-8123-456789abcdef", trace = "51234567-89ab-4cde-8123-456789abcdef";
const candidate = "61234567-89ab-4cde-8123-456789abcdef", chunk = "71234567-89ab-4cde-8123-456789abcdef";
const version = "81234567-89ab-4cde-8123-456789abcdef", parse = "91234567-89ab-4cde-8123-456789abcdef";
const bundle = "a1234567-89ab-4cde-8123-456789abcdef"; const now = "2026-10-04T12:00:00Z";
function json(data: unknown, status = 200, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify({ data, trace_id: trace }), { status,
    headers: { "Content-Type": "application/json", ...headers } });
}
function failure(status: number, code: string) {
  return new Response(JSON.stringify({ error: { code, message: "private" }, trace_id: trace }),
    { status, headers: { "Content-Type": "application/json" } });
}
const identity = { user: { user_id: actor, username_display: "检索用户" }, deployment_role: "NONE",
  password_change_required: false, authorized_projects: [{ project_id: project, name: "项目", role: "PROJECT_MANAGER" }],
  absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: "c".repeat(64) };
const run = { retrieval_run_id: runId, project_id: project, requested_by: actor, global_index_ref: null,
  project_index_ref: index, retrieval_policy_ref: "fts.project.v1", rerank_policy_ref: "none.v1", top_k: 5,
  rerank_state: "NOT_APPLICABLE", egress_state: "NOT_APPLICABLE", retrieval_state: "SUCCEEDED",
  quality_flags: ["CANDIDATE_SHORTFALL"], degraded: false, error_code: null, job_id: job, trace_id: trace,
  created_at: now, completed_at: now, etag: '"v1"' };
const result = { retrieval_run_id: runId, project_id: project, quality_flags: ["CANDIDATE_SHORTFALL"],
  degraded: false, completed_at: now, candidates: [{ candidate_id: candidate, rank: 0, chunk_id: chunk,
    document_version_ref: version, parse_result_ref: parse, source_type: "PROJECT_RECORD",
    source_locator: { locator_type: "PAGE", page: 2 }, retrieval_channel: "FTS", final_score_micros: 900000,
    score_parts: [{ score_kind: "FINAL", score_ordinal: 1, raw_score_micros: 900000,
      normalized_score_micros: 900000, weight_micros: 1000000, weighted_score_micros: 900000,
      score_policy_ref: "fts.project.v1" }], snippet: "最小上下文" }] };
const context = { context_bundle_id: bundle, retrieval_run_id: runId, project_id: project,
  context_policy_ref: "project-documents.v1", bundle_fingerprint: "b".repeat(64), token_budget: 100,
  token_count: 5, created_at: now, items: [{ ordinal: 0, chunk_id: chunk, document_version_ref: version,
    source_locator: { locator_type: "PAGE", page: 2 }, snippet_start: 0, snippet_end: 5,
    token_count: 5, snippet: "最小上下文" }] };
async function client(fetcher: ReturnType<typeof vi.fn>) {
  const session = new SessionClient(fetcher as typeof fetch); await session.login("user", "synthetic-only");
  return new RAGRetrievalClient(session, fetcher as typeof fetch);
}

describe("RAGRetrievalClient", () => {
  it("sends a normalized query only in one bounded POST body and validates the 202 binding", async () => {
    const storage = vi.spyOn(Storage.prototype, "setItem");
    const fetcher = vi.fn().mockResolvedValueOnce(json(identity)).mockResolvedValueOnce(
      json({ retrieval_run_id: runId, job_id: job }, 202,
        { Location: `/api/v1/projects/${project}/retrieval-runs/${runId}` }));
    const api = await client(fetcher);
    await expect(api.create(project, { query: "  PLM\n实施范围  ", metadata_filter: { source_type: ["PROJECT_RECORD"] },
      project_index_ref: index, top_k: 5 }, "retrieval-key-0001")).resolves.toEqual({ retrieval_run_id: runId, job_id: job });
    expect(fetcher).toHaveBeenCalledTimes(2);
    const [url, init] = fetcher.mock.calls[1]!;
    expect(url).toBe(`/api/v1/projects/${project}/retrieval-runs`);
    expect(String(url)).not.toContain("PLM");
    expect(init.headers).toMatchObject({ "X-CSRF-Token": "c".repeat(64), "Idempotency-Key": "retrieval-key-0001" });
    expect(JSON.parse(init.body)).toEqual({ query: "PLM 实施范围", metadata_filter: { source_type: ["PROJECT_RECORD"] },
      project_index_ref: index, global_index_ref: null, retrieval_policy_ref: "fts.project.v1",
      rerank_policy_ref: "none.v1", top_k: 5 });
    expect(storage).not.toHaveBeenCalled();
  });

  it("strictly reads run, result and context while dropping internal fingerprints and extra fields", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(json(identity))
      .mockResolvedValueOnce(json({ ...run, internal: "hidden" }, 200, { ETag: '"v1"' }))
      .mockResolvedValueOnce(json({ ...result, query_fingerprint: "hidden" }))
      .mockResolvedValueOnce(json({ ...context, internal: "hidden" }));
    const api = await client(fetcher);
    const current = await api.getRun(project, runId); const candidates = await api.getResult(project, runId);
    const bundleView = await api.getContext(project, runId);
    expect(current).toMatchObject({ retrieval_state: "SUCCEEDED", etag: '"v1"' });
    expect(candidates.candidates[0]?.snippet).toBe("最小上下文");
    expect(bundleView.items[0]?.snippet).toBe("最小上下文");
    expect(bundleView).not.toHaveProperty("bundle_fingerprint");
    expect(JSON.stringify([current, candidates, bundleView])).not.toContain("hidden");
    expect(fetcher.mock.calls.slice(1).map(call => call[0])).toEqual([
      `/api/v1/projects/${project}/retrieval-runs/${runId}`,
      `/api/v1/projects/${project}/retrieval-runs/${runId}/result`,
      `/api/v1/projects/${project}/retrieval-runs/${runId}/context`,
    ]);
  });

  it("fails closed on identity, rank, locator, ETag or context-total drift", async () => {
    for (const [data, headers] of [
      [{ ...run, project_id: actor }, { ETag: '"v1"' }],
      [{ ...run, etag: '"v2"' }, { ETag: '"v1"' }],
      [{ ...result, candidates: [{ ...result.candidates[0], rank: 1 }] }, {}],
      [{ ...result, candidates: [{ ...result.candidates[0], source_locator: { page: 2 } }] }, {}],
      [{ ...context, token_count: 6 }, {}],
    ] as const) {
      const fetcher = vi.fn().mockResolvedValueOnce(json(identity)).mockResolvedValueOnce(json(data, 200, headers));
      const api = await client(fetcher);
      const action = data === context || Object.hasOwn(data, "context_bundle_id") ? api.getContext(project, runId)
        : Object.hasOwn(data, "candidates") ? api.getResult(project, runId) : api.getRun(project, runId);
      await expect(action).rejects.toMatchObject({ code: "RAG_RETRIEVAL_UNCERTAIN" });
    }
  });

  it("maps safe read errors and never exposes server messages", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(json(identity)).mockResolvedValueOnce(failure(409, "CONFLICT_STATE"));
    const api = await client(fetcher);
    const caught = await api.getResult(project, runId).catch((value: unknown) => value);
    expect(caught).toBeInstanceOf(RAGRetrievalError); expect(caught).toMatchObject({ code: "CONFLICT_STATE", uncertain: false });
    expect(String(caught)).not.toContain("private"); expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("uses the exact Run version and original key for one cancellation", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(json(identity)).mockResolvedValueOnce(json({ retrieval_run_id: runId,
      job_id: job, state: "CANCEL_REQUESTED", changed: true, etag: '"v2"',
      status_url: `/api/v1/projects/${project}/retrieval-runs/${runId}` }, 200, { ETag: '"v2"' }));
    const api = await client(fetcher); const receipt = await api.cancel(project, run as never, "cancel-key-0000001", "用户取消");
    expect(receipt).toMatchObject({ first_result: { state: "CANCEL_REQUESTED", etag: '"v2"' }, is_current_state_proof: false });
    expect(fetcher.mock.calls[1]).toEqual([`/api/v1/projects/${project}/retrieval-runs/${runId}:cancel`,
      expect.objectContaining({ method: "POST", body: JSON.stringify({ reason: "用户取消" }),
        headers: expect.objectContaining({ "If-Match": '"v1"', "Idempotency-Key": "cancel-key-0000001" }) })]);
  });

  it("rejects malformed input before transport and marks a network create outcome uncertain without retry", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(json(identity)).mockRejectedValueOnce(new TypeError("network private"));
    const api = await client(fetcher);
    await expect(api.create(project, { query: "PLM", metadata_filter: { source_type: ["PROJECT_RECORD"] },
      project_index_ref: index, top_k: 5 }, "retrieval-key-0001"))
      .rejects.toMatchObject({ code: "RAG_RETRIEVAL_UNCERTAIN", uncertain: true });
    expect(fetcher).toHaveBeenCalledTimes(2);
    await expect(api.create(project, { query: "\0secret", metadata_filter: {}, project_index_ref: index, top_k: 5 },
      "retrieval-key-0002")).rejects.toMatchObject({ code: "RAG_RETRIEVAL_INVALID_INPUT" });
    await expect(api.create(project, { query: "PLM", metadata_filter: { effective_from: "2026-10-04" } as never,
      project_index_ref: index, top_k: 5 }, "retrieval-key-0003"))
      .rejects.toMatchObject({ code: "RAG_RETRIEVAL_INVALID_INPUT" });
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
});
