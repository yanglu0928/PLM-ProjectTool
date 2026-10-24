import { describe, expect, it, vi } from "vitest";
import type { DocumentReadClient } from "@/modules/document/api/documentReadClient";
import type { EvidenceListClient } from "@/modules/evidence/api/evidenceListClient";
import type { RequirementReadClient } from "@/modules/requirement/api/requirementReadClient";
import { loadProjectDocumentVersionCandidates, loadProjectSectionVersionCandidates } from "./sectionVersionCandidates";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const other = "11234567-89ab-4cde-8123-456789abcdef";
const document = "21234567-89ab-4cde-8123-456789abcdef";
const version = "31234567-89ab-4cde-8123-456789abcdef";
const requirement = "41234567-89ab-4cde-8123-456789abcdef";
const evidence = "51234567-89ab-4cde-8123-456789abcdef";
const doc = { document_id: document, scope: "PROJECT", state: "ACTIVE", title: "正文" };
const req = { requirement_id: requirement, project_id: project, state: "ACTIVE",
  current_approved_version_ref: version };
const proof = { evidence_id: evidence, document_id: document, document_version_id: version,
  eligibility_state: "ELIGIBLE" };
const availableVersion = { document_version_id: version, version_no: 2, availability_state: "AVAILABLE" };
function ports() {
  return { documents: { list: vi.fn().mockResolvedValue({ items: [doc], next_cursor: null, has_more: false }),
    listVersions: vi.fn().mockResolvedValue({ items: [availableVersion], next_cursor: null, has_more: false }) },
  requirements: { listRequirements: vi.fn().mockResolvedValue({ items: [req], next_cursor: null, has_more: false }) },
  evidence: { list: vi.fn().mockResolvedValue({ items: [proof], next_cursor: null, has_more: false }) } };
}
async function load(p = ports()) {
  return loadProjectSectionVersionCandidates(project, p.documents as unknown as Pick<DocumentReadClient, "list">,
    p.requirements as unknown as Pick<RequirementReadClient, "listRequirements">,
    p.evidence as unknown as Pick<EvidenceListClient, "list">);
}
describe("SectionVersion candidate reads", () => {
  it("filters current PROJECT sources and uses scoped read clients", async () => {
    const p = ports();
    p.documents.list.mockResolvedValue({ items: [doc, { ...doc, document_id: other, state: "ARCHIVED" }],
      next_cursor: null, has_more: false });
    p.evidence.list.mockResolvedValue({ items: [proof, { ...proof, evidence_id: other,
      eligibility_state: "CANDIDATE" }], next_cursor: null, has_more: false });
    const result = await load(p);
    expect(result.documents).toHaveLength(1); expect(result.requirements).toHaveLength(1);
    expect(result.evidence).toHaveLength(1);
    expect(p.documents.list).toHaveBeenCalledWith({ kind: "PROJECT", projectId: project }, null);
    expect(p.evidence.list).toHaveBeenCalledWith({ kind: "PROJECT", projectId: project }, null);
  });
  it("collects every page and fails closed on loops, foreign identity and duplicates", async () => {
    const p = ports();
    p.documents.list.mockResolvedValueOnce({ items: [doc], next_cursor: "next", has_more: true })
      .mockResolvedValueOnce({ items: [], next_cursor: null, has_more: false });
    expect((await load(p)).documents).toHaveLength(1);
    expect(p.documents.list).toHaveBeenCalledTimes(2);
    const loop = ports(); loop.evidence.list.mockResolvedValue({ items: [proof], next_cursor: "loop", has_more: true });
    await expect(load(loop)).rejects.toThrow("无法完整核对");
    const foreign = ports(); foreign.requirements.listRequirements.mockResolvedValue({ items: [{ ...req,
      project_id: other }], next_cursor: null, has_more: false });
    await expect(load(foreign)).rejects.toThrow("无法完整核对");
    const duplicate = ports(); duplicate.documents.list.mockResolvedValue({ items: [doc, doc],
      next_cursor: null, has_more: false });
    await expect(load(duplicate)).rejects.toThrow("无法完整核对");
  });
  it("loads only complete, ordered AVAILABLE versions for the selected document", async () => {
    const p = ports();
    expect((await loadProjectDocumentVersionCandidates(project, document, p.documents)).map(item =>
      item.document_version_id)).toEqual([version]);
    expect(p.documents.listVersions).toHaveBeenCalledWith({ kind: "PROJECT", projectId: project }, document, null);
    p.documents.listVersions.mockResolvedValue({ items: [availableVersion, availableVersion],
      next_cursor: null, has_more: false });
    await expect(loadProjectDocumentVersionCandidates(project, document, p.documents)).rejects.toThrow("无法完整核对");
  });
});
