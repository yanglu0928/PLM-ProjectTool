import { describe, expect, it, vi } from "vitest";
import { loadPlanApprovedSolutions, PlanApprovedSolutionError } from "./planVersionApprovedSolutions";
const project = "01234567-89ab-4cde-8123-456789abcdef"; const outline = "11234567-89ab-4cde-8123-456789abcdef";
const outlineVersion = "21234567-89ab-4cde-8123-456789abcdef"; const section = "31234567-89ab-4cde-8123-456789abcdef";
const sectionVersion = "41234567-89ab-4cde-8123-456789abcdef"; const user = "51234567-89ab-4cde-8123-456789abcdef";
const stamp = "2026-10-26T00:00:00Z";
const outlineDetail = { solution_outline_version_id: outlineVersion, solution_outline_id: outline, project_id: project,
  version_no: 2, version_state: "APPROVED", content_fingerprint: "a".repeat(64), declared_section_count: 1,
  declared_requirement_count: 0, declared_reference_count: 0, missing_declaration_count: 0, conflict_declaration_count: 0,
  supersedes_version_ref: user, review_ref: user, review_round_ref: user, created_by: user, created_at: stamp,
  section_ids: [section], requirement_refs: [], reference_refs: [], missing_declarations: [], conflict_declarations: [] };
const sectionDetail = { solution_section_version_id: sectionVersion, solution_section_id: section, project_id: project,
  version_no: 1, version_state: "APPROVED", title: "章节", content_fingerprint: "b".repeat(64), declared_requirement_count: 0,
  declared_evidence_count: 0, spec_binding_state: "NONE_REQUIRED", declared_spec_count: 0, assumption_count: 0, exclusion_count: 0,
  supersedes_version_ref: null, review_ref: user, review_round_ref: user, created_by: user, created_at: stamp,
  content_document_version_ref: null, content_artifact_ref: null, requirement_refs: [], evidence_ids: [], spec_not_required_reason: "无需专项",
  structured_spec_refs: [], assumptions: [], exclusions: [] };
function readers(sectionState = "APPROVED") { return {
  outlines: { list: vi.fn().mockResolvedValue({ items: [{ solution_outline_id: outline, project_id: project, name: "方案",
    outline_state: "ACTIVE", current_approved_version_ref: outlineVersion, created_at: stamp, etag: '"v1"' }], has_more: false, next_cursor: null }),
    current: vi.fn().mockResolvedValue({ solution_outline_id: outline, project_id: project, name: "方案", outline_state: "ACTIVE",
      current_approved_version_ref: outlineVersion, created_at: stamp, etag: '"v1"', created_by: user }) },
  outlineVersions: { list: vi.fn(), detail: vi.fn().mockResolvedValue(outlineDetail) },
  sections: { current: vi.fn().mockResolvedValue({ solution_section_id: section, solution_outline_id: outline, project_id: project,
    section_key: "S-1", section_state: "ACTIVE", current_approved_version_ref: sectionVersion, created_at: stamp, etag: '"v1"', created_by: user }) },
  sectionVersions: { detail: vi.fn().mockResolvedValue({ ...sectionDetail, version_state: sectionState }) },
  specs: { list: vi.fn().mockResolvedValue({ items: [], has_more: false, next_cursor: null }) },
  specDetails: { detail: vi.fn() },
}; }
describe("PlanVersion Approved Solution candidate reconstruction", () => {
  it("pins only the current approved outline and its current approved section", async () => {
    const api = readers(); const values = await loadPlanApprovedSolutions(project, api);
    expect(values).toHaveLength(1);
    expect(values[0]?.refs).toEqual([
      { resource_kind: "OUTLINE", resource_id: outline, version_id: outlineVersion, spec_series_id: null, spec_type: null },
      { resource_kind: "SECTION", resource_id: section, version_id: sectionVersion, spec_series_id: null, spec_type: null },
    ]);
  });
  it("fails closed when a fixed section is not approved", async () => {
    await expect(loadPlanApprovedSolutions(project, readers("DRAFT"))).rejects.toBeInstanceOf(PlanApprovedSolutionError);
  });
});
