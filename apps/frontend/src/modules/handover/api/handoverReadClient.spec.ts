import { afterEach, describe, expect, it, vi } from "vitest";
import { HandoverReadClient, HandoverReadError, parseHandoverItem, parseHandoverVersion,
  type HandoverAnalysisCursor, type HandoverItemCursor, type HandoverVersionCursor } from "./handoverReadClient";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const analysis = "11234567-89ab-4cde-8123-456789abcdef";
const version = "21234567-89ab-4cde-8123-456789abcdef";
const actor = "31234567-89ab-4cde-8123-456789abcdef";
const document = "41234567-89ab-4cde-8123-456789abcdef";
const evidence = "51234567-89ab-4cde-8123-456789abcdef";
const capability = "61234567-89ab-4cde-8123-456789abcdef";
const baseline = "71234567-89ab-4cde-8123-456789abcdef";
const trace = "81234567-89ab-4cde-8123-456789abcdef";
const now = "2026-10-05T12:00:00.000000Z";
const analysisView = { handover_analysis_id: analysis, project_id: project, analysis_purpose: "项目交接分析",
  source_set_ref: `sha256:${"a".repeat(64)}`, state: "ACTIVE", current_approved_version_ref: null,
  created_by: actor, created_at: now, updated_at: now, etag: '"v0"' };
const versionView = { handover_analysis_version_id: version, handover_analysis_id: analysis, project_id: project,
  version_no: 1, state: "DRAFT", source_set_ref: `sha256:${"a".repeat(64)}`, capability_baseline_id: baseline,
  capability_baseline_version_ref: capability, content_fingerprint: "b".repeat(64), declared_source_count: 1,
  declared_item_count: 1, declared_evidence_count: 1, declared_capability_ref_count: 1, declared_ai_task_count: 0,
  supersedes_version_ref: null, review_ref: null, review_round_ref: null, created_by: actor, created_at: now,
  source_documents: [{ document_id: document, document_version_id: evidence, ordinal: 0 }], ai_tasks: [] };
const itemView = { analysis_item_id: actor, handover_analysis_version_id: version, handover_analysis_id: analysis,
  project_id: project, ordinal: 0, item_type: "NEED_CONFIRM", title: "确认部署范围", statement: "需要确认部署范围",
  impact: "影响实施边界", severity: "HIGH", priority: "URGENT", recommendation: "按实际范围维护",
  confirmation_question: "实际部署范围是什么？", required_input_spec: { fields: [{ name: "部署范围", format: "文本",
    example: "总部与华东工厂", required: true }] }, source_missing: false, state: "CANDIDATE", evidence_refs: [evidence],
  capability_refs: [{ baseline_version_id: capability, capability_item_id: baseline, ordinal: 0 }],
  options: [{ option_code: "A", label: "总部", description: null, ordinal: 0 },
    { option_code: "B", label: "总部和工厂", description: "覆盖两类组织", ordinal: 1 }] };
const token = `${"A".repeat(24)}.${"B".repeat(43)}`;

function ok(data: unknown, headerEtag?: string): Response {
  const headers: Record<string, string> = { "Content-Type": "application/json" }; if (headerEtag) headers.ETag = headerEtag;
  return new Response(JSON.stringify({ data, trace_id: trace }), { status: 200, headers });
}
function failure(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: "private" }, trace_id: trace }),
    { status, headers: { "Content-Type": "application/json" } });
}
function client(...responses: Response[]) {
  const fetcher = vi.fn(); for (const response of responses) fetcher.mockResolvedValueOnce(response);
  return { api: new HandoverReadClient(fetcher as typeof fetch), fetcher };
}

describe("HandoverReadClient", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); });

  it("reads Analysis page/detail with no-store and strong ETag", async () => {
    const { api, fetcher } = client(ok({ items: [analysisView], next_cursor: token, has_more: true }), ok(analysisView, '"v0"'));
    const page = await api.listAnalyses(project, 25);
    expect(fetcher.mock.calls[0]).toEqual([`/api/v1/projects/${project}/handover-analyses?page_size=25`, expect.objectContaining({
      method: "GET", credentials: "same-origin", cache: "no-store", redirect: "error", headers: { Accept: "application/json" },
    })]);
    expect(page.next_cursor).toBe(token); expect(Object.isFrozen(page.items[0])).toBe(true);
    await expect(api.getAnalysis(project, analysis)).resolves.toMatchObject({ etag: '"v0"' });
  });

  it("passes each opaque cursor without decoding and keeps parent paths", async () => {
    const { api, fetcher } = client(ok({ items: [], next_cursor: null, has_more: false }),
      ok({ items: [], next_cursor: null, has_more: false }), ok({ items: [], next_cursor: null, has_more: false }));
    await api.listAnalyses(project, 50, token as HandoverAnalysisCursor);
    await api.listVersions(project, analysis, 50, token as HandoverVersionCursor);
    await api.listItems(project, analysis, version, 50, token as HandoverItemCursor);
    expect(fetcher.mock.calls.map(call => call[0])).toEqual([
      `/api/v1/projects/${project}/handover-analyses?page_size=50&cursor=${token}`,
      `/api/v1/projects/${project}/handover-analyses/${analysis}/versions?page_size=50&cursor=${token}`,
      `/api/v1/projects/${project}/handover-analyses/${analysis}/versions/${version}/items?page_size=50&cursor=${token}`,
    ]);
  });

  it("reads fixed Version detail and verifies counts, ordering and parent identities", async () => {
    const { api } = client(ok(versionView)); const value = await api.getVersion(project, analysis, version);
    expect(value.source_documents).toEqual([{ document_id: document, document_version_id: evidence, ordinal: 0 }]);
    expect(Object.isFrozen(value.source_documents)).toBe(true);
  });

  it("accepts Version list summaries only when fixed-source details stay collapsed", async () => {
    const summary = { ...versionView, source_documents: [], ai_tasks: [] };
    const { api } = client(ok({ items: [summary], next_cursor: null, has_more: false }));
    await expect(api.listVersions(project, analysis)).resolves.toMatchObject({
      items: [{ declared_source_count: 1, source_documents: [] }],
    });
    expect(() => parseHandoverVersion(versionView, project, analysis)).toThrowError(HandoverReadError);
  });

  it("reads NEED_CONFIRM item fields as explicit maintenance prompts", async () => {
    const { api } = client(ok({ items: [itemView], next_cursor: null, has_more: false }));
    const page = await api.listItems(project, analysis, version);
    expect(page.items[0]).toMatchObject({ confirmation_question: "实际部署范围是什么？",
      required_input_spec: { fields: [{ name: "部署范围", format: "文本", example: "总部与华东工厂", required: true }] },
      evidence_refs: [evidence] });
    expect(Object.isFrozen(page.items[0]!.required_input_spec)).toBe(true);
  });

  it.each([
    { ...itemView, private_text: "secret" },
    { ...itemView, required_input_spec: {} },
    { ...itemView, evidence_refs: [] },
    { ...itemView, options: [itemView.options[1], itemView.options[0]] },
    { ...itemView, capability_refs: [{ ...itemView.capability_refs[0], ordinal: 3 }] },
  ])("rejects unsafe Item projection %#", bad => {
    expect(() => parseHandoverItem(bad, project, analysis, version)).toThrowError(HandoverReadError);
  });

  it.each([
    { ...versionView, project_id: actor }, { ...versionView, declared_source_count: 2 },
    { ...versionView, review_ref: actor, review_round_ref: null },
    { ...versionView, source_documents: [{ ...versionView.source_documents[0], ordinal: 1 }] },
  ])("rejects inconsistent Version projection %#", bad => {
    expect(() => parseHandoverVersion(bad, project, analysis, version)).toThrowError(HandoverReadError);
  });

  it("rejects page order, duplicate identities and cursor replay", async () => {
    const older = { ...analysisView, handover_analysis_id: actor, updated_at: "2026-10-05T11:00:00Z" };
    await expect(client(ok({ items: [older, analysisView], next_cursor: null, has_more: false })).api.listAnalyses(project))
      .rejects.toMatchObject({ code: "HANDOVER_READ_UNAVAILABLE" });
    await expect(client(ok({ items: [versionView, versionView], next_cursor: null, has_more: false })).api
      .listVersions(project, analysis)).rejects.toMatchObject({ code: "HANDOVER_READ_UNAVAILABLE" });
    await expect(client(ok({ items: [itemView], next_cursor: token, has_more: true })).api
      .listItems(project, analysis, version, 50, token as HandoverItemCursor))
      .rejects.toMatchObject({ code: "HANDOVER_READ_UNAVAILABLE" });
  });

  it.each(["../admin", project.toUpperCase(), "00000000-0000-0000-0000-000000000000"])(
    "rejects unsafe ids before network: %s", async bad => {
      const { api, fetcher } = client(ok({ items: [], next_cursor: null, has_more: false }));
      await expect(api.listAnalyses(bad)).rejects.toMatchObject({ code: "HANDOVER_READ_INVALID_INPUT" });
      await expect(api.getVersion(project, analysis, bad)).rejects.toMatchObject({ code: "HANDOVER_READ_INVALID_INPUT" });
      expect(fetcher).not.toHaveBeenCalled();
    });

  it.each([0, 201, 1.5, Number.NaN])("rejects invalid page size %s", async size => {
    const { api, fetcher } = client(ok({ items: [], next_cursor: null, has_more: false }));
    await expect(api.listVersions(project, analysis, size)).rejects.toMatchObject({ code: "HANDOVER_READ_INVALID_INPUT" });
    expect(fetcher).not.toHaveBeenCalled();
  });

  it.each([[401, "AUTH_SESSION_EXPIRED"], [403, "LICENSE_OPERATION_DENIED"], [404, "RESOURCE_NOT_FOUND"],
    [409, "PROJECT_ARCHIVED"]] as const)("maps only matching safe error %s %s", async (status, code) => {
    await expect(client(failure(status, code)).api.getAnalysis(project, analysis)).rejects.toMatchObject({ code });
  });

  it("fails closed on wrong ETag, private error, content type and timeout", async () => {
    await expect(client(ok(analysisView, '"v9"')).api.getAnalysis(project, analysis))
      .rejects.toMatchObject({ code: "HANDOVER_READ_UNAVAILABLE" });
    await expect(client(failure(403, "RESOURCE_NOT_FOUND")).api.getAnalysis(project, analysis))
      .rejects.toMatchObject({ code: "HANDOVER_READ_UNAVAILABLE" });
    const html = new Response("x", { status: 200, headers: { "Content-Type": "text/html" } });
    await expect(client(html).api.getAnalysis(project, analysis)).rejects.toMatchObject({ code: "HANDOVER_READ_UNAVAILABLE" });
    vi.useFakeTimers(); const api = new HandoverReadClient(vi.fn((_path, init) => new Promise((_resolve, reject) => {
      init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
    })) as typeof fetch, 5);
    const pending = api.getAnalysis(project, analysis);
    const assertion = expect(pending).rejects.toMatchObject({ code: "HANDOVER_READ_UNAVAILABLE" });
    await vi.advanceTimersByTimeAsync(5); await assertion;
  });
});
