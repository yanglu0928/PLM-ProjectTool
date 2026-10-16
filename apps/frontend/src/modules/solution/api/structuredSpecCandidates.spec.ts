import { describe, expect, it, vi } from "vitest";
import type { RequirementReadClient } from "@/modules/requirement/api/requirementReadClient";
import type { EvidenceListClient } from "@/modules/evidence/api/evidenceListClient";
import type { SectionReadClient } from "./sectionReadClient";
import type { SectionVersionReadClient } from "./sectionVersionReadClient";
import { loadStructuredSpecCandidates } from "./structuredSpecCandidates";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const requirement = "11234567-89ab-4cde-8123-456789abcdef";
const approved = "21234567-89ab-4cde-8123-456789abcdef";
const section = "31234567-89ab-4cde-8123-456789abcdef";
const version = "41234567-89ab-4cde-8123-456789abcdef";
const evidence = "51234567-89ab-4cde-8123-456789abcdef";
const empty = { items: [], has_more: false, next_cursor: null };
const req = { requirement_id: requirement, project_id: project, state: "ACTIVE",
  requirement_code: "REQ-1", current_approved_version_ref: approved };
const root = { solution_section_id: section, project_id: project, section_state: "ACTIVE",
  section_key: "SECTION-1", current_approved_version_ref: null };
const latest = { solution_section_version_id: version, solution_section_id: section,
  project_id: project, version_state: "DRAFT", version_no: 1, title: "Synthetic section" };
const proof = { evidence_id: evidence, document_version_id: approved,
  eligibility_state: "ELIGIBLE", display_label: "Synthetic evidence" };

function ports(options: { requirement?: object; section?: object; version?: object;
                  evidence?: object } = {}) {
  const requirements = { listRequirements: vi.fn().mockResolvedValue({
    ...empty, items: [options.requirement ?? req] }) } as unknown as Pick<RequirementReadClient, "listRequirements">;
  const sections = { list: vi.fn().mockResolvedValue({
    ...empty, items: [options.section ?? root] }) } as unknown as Pick<SectionReadClient, "list">;
  const versions = { list: vi.fn().mockResolvedValue({
    ...empty, items: [options.version ?? latest] }), detail: vi.fn().mockResolvedValue({
      ...latest, solution_section_version_id: approved, version_state: "APPROVED" })
  } as unknown as Pick<SectionVersionReadClient, "list" | "detail">;
  const proofs = { list: vi.fn().mockResolvedValue({
    ...empty, items: [options.evidence ?? proof] }) } as unknown as Pick<EvidenceListClient, "list">;
  return { requirements, sections, versions, proofs };
}
async function load(value = ports()) {
  return loadStructuredSpecCandidates(project, value.requirements, value.sections,
    value.versions, value.proofs);
}

describe("StructuredSpecCandidates", () => {
  it("uses current approved requirement, latest Section DRAFT and eligible project Evidence", async () => {
    const value = ports();
    const result = await load(value);
    expect(result.requirements[0]?.current_approved_version_ref).toBe(approved);
    expect(result.sections[0]?.version.solution_section_version_id).toBe(version);
    expect(result.evidence[0]?.evidence_id).toBe(evidence);
    expect(value.versions.list).toHaveBeenCalledWith(project, section, 1);
  });
  it("does not offer unapproved, archived, stale or ineligible sources", async () => {
    expect((await load(ports({ requirement: { ...req, current_approved_version_ref: null },
      section: { ...root, section_state: "ARCHIVED" },
      evidence: { ...proof, eligibility_state: "REVOKED" } }))).requirements).toEqual([]);
    expect((await load(ports({ version: { ...latest, version_state: "RETURNED" } }))).sections).toEqual([]);
    expect((await load(ports({ version: { ...latest, version_state: "APPROVED" } }))).sections).toEqual([]);
    expect((await load(ports({ section: { ...root, current_approved_version_ref: version },
      version: { ...latest, version_state: "APPROVED" } }))).sections).toHaveLength(1);
    const fallback = await load(ports({ section: { ...root, current_approved_version_ref: approved },
      version: { ...latest, version_state: "RETURNED" } }));
    expect(fallback.sections[0]?.version.solution_section_version_id).toBe(approved);
  });
  it("fails closed on cross-project and duplicate source identities", async () => {
    await expect(load(ports({ requirement: { ...req, project_id: section } }))).rejects.toThrow();
    await expect(load(ports({ version: { ...latest, project_id: section } }))).rejects.toThrow();
    const value = ports();
    vi.mocked(value.sections.list).mockResolvedValueOnce({ ...empty,
      items: [root, root] } as never);
    await expect(load(value)).rejects.toThrow();
  });
});
