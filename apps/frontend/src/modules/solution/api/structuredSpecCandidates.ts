/** Metadata candidates only; SOL-06 Owner re-proves all current sources at write time. */
import { RequirementReadClient, type RequirementCursor, type RequirementView } from
  "@/modules/requirement/api/requirementReadClient";
import { EvidenceListClient, type EvidenceSummary } from
  "@/modules/evidence/api/evidenceListClient";
import { SectionReadClient, type SectionSummary } from "./sectionReadClient";
import { SectionVersionReadClient, type SectionVersionSummary } from "./sectionVersionReadClient";

export interface StructuredSpecSectionCandidate {
  readonly section: SectionSummary;
  readonly version: SectionVersionSummary;
}
export interface StructuredSpecCandidates {
  readonly requirements: readonly RequirementView[];
  readonly sections: readonly StructuredSpecSectionCandidate[];
  readonly evidence: readonly EvidenceSummary[];
}
export class StructuredSpecCandidateError extends Error {
  constructor() { super("来源候选无法完整核对，已停止创建；请刷新后重试。"); this.name = "StructuredSpecCandidateError"; }
}
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
function id(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value)
    && value !== "00000000-0000-0000-0000-000000000000";
}
interface Page<T> { readonly items: readonly T[]; readonly has_more: boolean; readonly next_cursor: string | null }
async function collect<T>(read: (cursor: string | null) => Promise<Page<T>>, maximum: number): Promise<T[]> {
  const all: T[] = []; const cursors = new Set<string>(); let cursor: string | null = null;
  do {
    const page = await read(cursor);
    if (!page || !Array.isArray(page.items) || typeof page.has_more !== "boolean"
      || page.has_more && (!page.items.length || typeof page.next_cursor !== "string"
        || !page.next_cursor || cursors.has(page.next_cursor))
      || !page.has_more && page.next_cursor !== null) throw new StructuredSpecCandidateError();
    all.push(...page.items);
    if (all.length > maximum) throw new StructuredSpecCandidateError();
    if (!page.has_more) return all;
    cursor = page.next_cursor;
    cursors.add(cursor!);
  } while (true);
}
export async function loadStructuredSpecCandidates(
  project: string,
  requirements: Pick<RequirementReadClient, "listRequirements">,
  sections: Pick<SectionReadClient, "list">,
  versions: Pick<SectionVersionReadClient, "list" | "detail">,
  evidence: Pick<EvidenceListClient, "list">,
): Promise<StructuredSpecCandidates> {
  if (!id(project)) throw new StructuredSpecCandidateError();
  try {
    const [reqs, roots, proofs] = await Promise.all([
      collect(cursor => requirements.listRequirements(project, 200,
        cursor as RequirementCursor | null), 10_000),
      collect(cursor => sections.list(project, 100, cursor), 10_000),
      collect(cursor => evidence.list({ kind: "PROJECT", projectId: project }, cursor), 10_000),
    ]);
    if (reqs.some(item => item.project_id !== project || !id(item.requirement_id)
        || item.current_approved_version_ref !== null && !id(item.current_approved_version_ref))
      || roots.some(item => item.project_id !== project || !id(item.solution_section_id))
      || proofs.some(item => !id(item.evidence_id) || !id(item.document_version_id))
      || new Set(reqs.map(item => item.requirement_id)).size !== reqs.length
      || new Set(roots.map(item => item.solution_section_id)).size !== roots.length
      || new Set(proofs.map(item => item.evidence_id)).size !== proofs.length) {
      throw new StructuredSpecCandidateError();
    }
    const active = roots.filter(item => item.section_state === "ACTIVE");
    const sectionVersions: (StructuredSpecSectionCandidate | null)[] = [];
    for (let offset = 0; offset < active.length; offset += 20) {
      sectionVersions.push(...await Promise.all(active.slice(offset, offset + 20).map(async section => {
      const page = await versions.list(project, section.solution_section_id, 1);
      if (page.has_more && (!page.next_cursor || page.items.length !== 1)) {
        throw new StructuredSpecCandidateError();
      }
      const current = page.items[0];
      if (!current) return null;
      if (current.project_id !== project || current.solution_section_id !== section.solution_section_id
        || !id(current.solution_section_version_id)) throw new StructuredSpecCandidateError();
      if (["DRAFT", "IN_REVIEW", "APPROVED"].includes(current.version_state)
        && (current.version_state !== "APPROVED"
          || section.current_approved_version_ref === current.solution_section_version_id)) {
        return Object.freeze({ section, version: current });
      }
      if (section.current_approved_version_ref) {
        const approved = await versions.detail(project, section.solution_section_id,
          section.current_approved_version_ref);
        if (approved.project_id !== project || approved.solution_section_id !== section.solution_section_id
          || approved.solution_section_version_id !== section.current_approved_version_ref
          || approved.version_state !== "APPROVED") throw new StructuredSpecCandidateError();
        return Object.freeze({ section, version: approved });
      }
      return null;
      })));
    }
    return Object.freeze({
      requirements: Object.freeze(reqs.filter(item => item.state === "ACTIVE"
        && item.current_approved_version_ref)),
      sections: Object.freeze(sectionVersions.filter(
        (item): item is StructuredSpecSectionCandidate => item !== null)),
      evidence: Object.freeze(proofs.filter(item => item.eligibility_state === "ELIGIBLE")),
    });
  } catch { throw new StructuredSpecCandidateError(); }
}
