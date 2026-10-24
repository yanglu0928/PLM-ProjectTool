import { describe, expect, it, vi } from "vitest";
import type { RequirementReadClient } from "@/modules/requirement/api/requirementReadClient";
import type { ReferenceReadClient } from "./referenceReadClient";
import type { SectionReadClient } from "./sectionReadClient";
import { loadProjectOutlineVersionCandidates } from "./outlineVersionCandidates";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const outline = "11234567-89ab-4cde-8123-456789abcdef";
const otherOutline = "21234567-89ab-4cde-8123-456789abcdef";
const section = "31234567-89ab-4cde-8123-456789abcdef";
const requirement = "41234567-89ab-4cde-8123-456789abcdef";
const version = "51234567-89ab-4cde-8123-456789abcdef";
const reference = "61234567-89ab-4cde-8123-456789abcdef";
const sectionItem = { solution_section_id: section, solution_outline_id: outline, project_id: project,
  section_key: "S1", section_state: "ACTIVE", current_approved_version_ref: null,
  created_at: "2026-10-09T00:00:00Z", etag: '"v0"' };
const requirementItem = { requirement_id: requirement, project_id: project,
  requirement_code: "REQ-1", state: "ACTIVE", current_approved_version_ref: version,
  created_by: project, created_at: "2026-10-09T00:00:00Z", updated_by: null,
  updated_at: "2026-10-09T00:00:00Z", etag: '"v0"' };
const referenceItem = { reference_solution_id: reference, reference_version_id: version,
  scope: "PROJECT", project_id: project, name: "参考方案", eligibility_state: "ELIGIBLE",
  version_no: 1, version_state: "DRAFT", created_at: "2026-10-09T00:00:00Z", etag: '"v0"' };
function ports() {
  const sections = { list: vi.fn().mockResolvedValue({ items: [sectionItem], next_cursor: null, has_more: false }) };
  const requirements = { listRequirements: vi.fn().mockResolvedValue({ items: [requirementItem],
    next_cursor: null, has_more: false }) };
  const references = { list: vi.fn().mockResolvedValue({ items: [referenceItem],
    next_cursor: null, has_more: false }) };
  return { sections, requirements, references };
}
async function load(p = ports()) {
  return loadProjectOutlineVersionCandidates(project, outline,
    p.sections as unknown as Pick<SectionReadClient, "list">,
    p.requirements as unknown as Pick<RequirementReadClient, "listRequirements">,
    p.references as unknown as Pick<ReferenceReadClient, "list">);
}
describe("OutlineVersion PROJECT candidates", () => {
  it("keeps only current active, approved-pointer and ELIGIBLE project candidates", async () => {
    const p = ports();
    p.sections.list.mockResolvedValue({ items: [sectionItem, { ...sectionItem,
      solution_section_id: otherOutline, solution_outline_id: otherOutline }], next_cursor: null, has_more: false });
    const result = await load(p);
    expect(result.sections.map(item => item.solution_section_id)).toEqual([section]);
    expect(result.requirements.map(item => item.current_approved_version_ref)).toEqual([version]);
    expect(result.references.map(item => item.reference_solution_id)).toEqual([reference]);
  });
  it("reads all pages and refuses repeated cursor or foreign project", async () => {
    const p = ports();
    p.sections.list.mockResolvedValueOnce({ items: [sectionItem], next_cursor: "cursor", has_more: true })
      .mockResolvedValueOnce({ items: [], next_cursor: null, has_more: false });
    expect((await load(p)).sections).toHaveLength(1);
    expect(p.sections.list).toHaveBeenCalledTimes(2);
    const q = ports();
    q.references.list.mockResolvedValue({ items: [{ ...referenceItem, project_id: otherOutline }],
      next_cursor: null, has_more: false });
    await expect(load(q)).rejects.toThrow("候选来源无法完整核对");
    const loop = ports();
    loop.sections.list.mockResolvedValue({ items: [sectionItem], next_cursor: "same", has_more: true });
    await expect(load(loop)).rejects.toThrow("候选来源无法完整核对");
  });
  it("refuses duplicate identities and incomplete reader failure", async () => {
    const p = ports();
    p.requirements.listRequirements.mockResolvedValue({ items: [requirementItem, requirementItem],
      next_cursor: null, has_more: false });
    await expect(load(p)).rejects.toThrow("候选来源无法完整核对");
    const q = ports(); q.sections.list.mockRejectedValue(new Error("disconnect"));
    await expect(load(q)).rejects.toThrow("候选来源无法完整核对");
  });
});
