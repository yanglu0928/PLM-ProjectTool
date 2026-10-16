import { describe, expect, it, vi } from "vitest";
import { StructuredSpecReadClient, StructuredSpecReadError,
  parseStructuredSpecDetail } from "./structuredSpecReadClient";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const spec = "11234567-89ab-4cde-8123-456789abcdef";
const series = "21234567-89ab-4cde-8123-456789abcdef";
const requirement = "31234567-89ab-4cde-8123-456789abcdef";
const section = "41234567-89ab-4cde-8123-456789abcdef";
const evidence = "51234567-89ab-4cde-8123-456789abcdef";
const detail = {
  structured_solution_spec_id: spec, spec_series_id: series, project_id: project,
  spec_type: "MIGRATION_SPEC", version_no: 1, version_state: "DRAFT",
  content_fingerprint: "a".repeat(64), payload_fingerprint: "b".repeat(64),
  payload: { assumptions: [], exclusions: [], source_system: "旧", target_system: "新",
    scope: "零件", cleansing_rules: ["去重"],
    field_mappings: [{ source: "old_id", target: "part_id" }], trial_plan: "试点",
    reconciliation_plan: "核对", rollback_plan: "恢复", acceptance_criteria: "零差异" },
  requirement_refs: [{ requirement_id: requirement, requirement_version_id: requirement }],
  section_refs: [{ solution_section_id: section, solution_section_version_id: section }],
  evidence_ids: [evidence], artifact_ids: [], declared_requirement_count: 1,
  declared_section_count: 1, declared_evidence_count: 1, supersedes_version_ref: null,
  review_ref: null, review_round_ref: null, created_by: project,
  created_at: "2026-10-16T00:00:00Z",
};
function response(data: unknown, status = 200, extra: Record<string, string> = {}): Response {
  return new Response(JSON.stringify({ data, trace_id: project }), { status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store",
      "X-Trace-Id": project, ...extra } });
}

describe("StructuredSpecReadClient", () => {
  it("requests same-origin fixed GET and validates the complete detail", async () => {
    const fetcher = vi.fn().mockResolvedValue(response(detail));
    const item = await new StructuredSpecReadClient(fetcher).detail(project, spec);
    expect(item.payload).toEqual(detail.payload);
    expect(item.requirement_refs).toEqual(detail.requirement_refs);
    expect(fetcher.mock.calls[0]?.[0]).toBe(
      `/api/v1/projects/${project}/structured-solution-specs/${spec}`);
    expect(fetcher.mock.calls[0]?.[1]).toMatchObject({ method: "GET",
      credentials: "same-origin", cache: "no-store", redirect: "error" });
  });

  it("rejects mismatched project, counts, refs, fingerprints and envelope", async () => {
    for (const broken of [
      { ...detail, project_id: series },
      { ...detail, declared_section_count: 2 },
      { ...detail, requirement_refs: [] },
      { ...detail, payload_fingerprint: "bad" },
      { ...detail, artifact_ids: [evidence] },
    ]) expect(() => parseStructuredSpecDetail(broken, project, spec))
      .toThrowError(StructuredSpecReadError);
    await expect(new StructuredSpecReadClient(vi.fn().mockResolvedValue(
      response(detail, 200, { "Cache-Control": "public" }))).detail(project, spec))
      .rejects.toMatchObject({ code: "STRUCTURED_SPEC_READ_UNAVAILABLE" });
    await expect(new StructuredSpecReadClient(vi.fn().mockResolvedValue(
      response(detail, 200, { "X-Trace-Id": series }))).detail(project, spec))
      .rejects.toMatchObject({ code: "STRUCTURED_SPEC_READ_UNAVAILABLE" });
  });

  it("maps exact auth/license/not-found errors; unknown network result fails closed", async () => {
    for (const [code, status] of [["AUTH_SESSION_EXPIRED", 401],
      ["LICENSE_OPERATION_DENIED", 403], ["RESOURCE_NOT_FOUND", 404]] as const) {
      const fetcher = vi.fn().mockResolvedValue(response({ error: { code } }, status));
      // Errors use the same trace envelope but have error instead of data.
      fetcher.mockResolvedValue(new Response(JSON.stringify({ error: { code, message: "denied" },
        trace_id: project }), { status, headers: { "Content-Type": "application/json",
        "Cache-Control": "no-store", "X-Trace-Id": project } }));
      await expect(new StructuredSpecReadClient(fetcher).detail(project, spec))
        .rejects.toMatchObject({ code });
    }
    await expect(new StructuredSpecReadClient(vi.fn().mockRejectedValue(
      new TypeError("offline"))).detail(project, spec))
      .rejects.toMatchObject({ code: "STRUCTURED_SPEC_READ_UNAVAILABLE" });
    await expect(new StructuredSpecReadClient().detail("bad", spec))
      .rejects.toMatchObject({ code: "STRUCTURED_SPEC_READ_INVALID" });
  });
});
