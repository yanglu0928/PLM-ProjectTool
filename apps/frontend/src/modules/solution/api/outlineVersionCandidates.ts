/** Bounded PROJECT candidate projection. The CREATE Owner must re-prove every selected source. */
import { RequirementReadClient, type RequirementCursor, type RequirementView } from
  "@/modules/requirement/api/requirementReadClient";
import { ReferenceReadClient, type ReferenceSummary } from "./referenceReadClient";
import { SectionReadClient, type SectionSummary } from "./sectionReadClient";

export interface OutlineVersionProjectCandidates {
  readonly sections: readonly SectionSummary[];
  readonly requirements: readonly RequirementView[];
  readonly references: readonly ReferenceSummary[];
}
export class OutlineVersionCandidateError extends Error {
  constructor() { super("候选来源无法完整核对，已停止创建；请刷新后重试。"); this.name = "OutlineVersionCandidateError"; }
}
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
function id(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value) && value !== "00000000-0000-0000-0000-000000000000";
}
interface Page<T> { readonly items: readonly T[]; readonly has_more: boolean; readonly next_cursor: string | null }
async function collect<T>(read: (cursor: string | null) => Promise<Page<T>>, maximum: number): Promise<T[]> {
  const values: T[] = [];
  const seen = new Set<string>();
  let cursor: string | null = null;
  do {
    const page = await read(cursor);
    if (!page || !Array.isArray(page.items) || typeof page.has_more !== "boolean"
      || page.has_more && (typeof page.next_cursor !== "string" || seen.has(page.next_cursor))
      || !page.has_more && page.next_cursor !== null) throw new OutlineVersionCandidateError();
    values.push(...page.items);
    if (values.length > maximum) throw new OutlineVersionCandidateError();
    if (!page.has_more) break;
    cursor = page.next_cursor;
    seen.add(cursor!);
  } while (true);
  return values;
}

export async function loadProjectOutlineVersionCandidates(
  projectId: string, outlineId: string,
  sections: Pick<SectionReadClient, "list">,
  requirements: Pick<RequirementReadClient, "listRequirements">,
  references: Pick<ReferenceReadClient, "list">,
): Promise<OutlineVersionProjectCandidates> {
  if (!id(projectId) || !id(outlineId)) throw new OutlineVersionCandidateError();
  try {
    const [allSections, allRequirements, allReferences] = await Promise.all([
      collect(cursor => sections.list(projectId, 100, cursor), 10_000),
      collect(cursor => requirements.listRequirements(projectId, 200, cursor as RequirementCursor | null), 10_000),
      collect(cursor => references.list(projectId, 100, cursor), 10_000),
    ]);
    if (allSections.some(item => item.project_id !== projectId || !id(item.solution_section_id)
      || !id(item.solution_outline_id))
      || allRequirements.some(item => item.project_id !== projectId || !id(item.requirement_id))
      || allReferences.some(item => item.project_id !== projectId || item.scope !== "PROJECT"
        || !id(item.reference_solution_id) || !id(item.reference_version_id))) {
      throw new OutlineVersionCandidateError();
    }
    const selectedSections = allSections.filter(item => item.solution_outline_id === outlineId
      && item.section_state === "ACTIVE");
    const selectedRequirements = allRequirements.filter(item => item.state === "ACTIVE"
      && item.current_approved_version_ref !== null);
    const selectedReferences = allReferences.filter(item => item.eligibility_state === "ELIGIBLE");
    if (selectedSections.length > 100 || selectedRequirements.length > 500 || selectedReferences.length > 500
      || new Set(allSections.map(item => item.solution_section_id)).size !== allSections.length
      || new Set(allRequirements.map(item => item.requirement_id)).size !== allRequirements.length
      || new Set(allReferences.map(item => item.reference_solution_id)).size !== allReferences.length) {
      throw new OutlineVersionCandidateError();
    }
    return Object.freeze({ sections: Object.freeze(selectedSections),
      requirements: Object.freeze(selectedRequirements), references: Object.freeze(selectedReferences) });
  } catch {
    throw new OutlineVersionCandidateError();
  }
}
