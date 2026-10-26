/** Read-only candidate reconstruction. The PlanVersion Create Owner re-proves the selected graph. */
import { OutlineReadClient } from "@/modules/solution/api/outlineReadClient";
import { OutlineVersionReadClient, type OutlineVersionDetail } from "@/modules/solution/api/outlineVersionReadClient";
import { SectionReadClient } from "@/modules/solution/api/sectionReadClient";
import { SectionVersionReadClient } from "@/modules/solution/api/sectionVersionReadClient";
import { StructuredSpecListClient } from "@/modules/solution/api/structuredSpecListClient";
import { StructuredSpecReadClient } from "@/modules/solution/api/structuredSpecReadClient";
import { RequirementReadClient } from "@/modules/requirement/api/requirementReadClient";

export interface PlanApprovedSolution {
  readonly outline: OutlineVersionDetail;
  readonly refs: readonly PlanSolutionFixedRef[];
  readonly requirements: readonly PlanApprovedRequirement[];
  readonly display: readonly string[];
}
export interface PlanApprovedRequirement {
  readonly requirement_id: string;
  readonly requirement_version_id: string;
  readonly requirement_code: string;
  readonly version_no: number;
  readonly title: string | null;
  readonly statement: string;
}
export interface PlanSolutionFixedRef {
  readonly resource_kind: string; readonly resource_id: string; readonly version_id: string;
  readonly spec_series_id: string | null; readonly spec_type: string | null;
}
export interface PlanApprovedSolutionReaders {
  readonly outlines: Pick<OutlineReadClient, "list" | "current">;
  readonly outlineVersions: Pick<OutlineVersionReadClient, "list" | "detail">;
  readonly sections: Pick<SectionReadClient, "current">;
  readonly sectionVersions: Pick<SectionVersionReadClient, "detail">;
  readonly specs: Pick<StructuredSpecListClient, "list">;
  readonly specDetails: Pick<StructuredSpecReadClient, "detail">;
  readonly requirements: Pick<RequirementReadClient, "getRequirement" | "getVersion">;
}
export class PlanApprovedSolutionError extends Error {
  constructor() { super("已批准方案的固定来源无法完整核对，已停止创建；请刷新后重试。"); this.name = "PlanApprovedSolutionError"; }
}
const id = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
function validId(value: unknown): value is string { return typeof value === "string" && id.test(value) && value !== "00000000-0000-0000-0000-000000000000"; }
async function collect<T>(read: (cursor: string | null) => Promise<{ items: readonly T[]; has_more: boolean; next_cursor: string | null }>, maximum: number): Promise<T[]> {
  const rows: T[] = []; const seen = new Set<string>(); let cursor: string | null = null;
  do { const page = await read(cursor);
    if (!page || !Array.isArray(page.items) || typeof page.has_more !== "boolean"
      || page.has_more && (typeof page.next_cursor !== "string" || seen.has(page.next_cursor))
      || !page.has_more && page.next_cursor !== null) throw new PlanApprovedSolutionError();
    rows.push(...page.items); if (rows.length > maximum) throw new PlanApprovedSolutionError();
    if (!page.has_more) break; cursor = page.next_cursor; seen.add(cursor!);
  } while (true); return rows;
}
async function mapLimited<T, R>(values: readonly T[], limit: number, work: (value: T) => Promise<R>): Promise<R[]> {
  const output = new Array<R>(values.length); let next = 0;
  await Promise.all(Array.from({ length: Math.min(limit, values.length) }, async () => {
    while (next < values.length) { const index = next++; output[index] = await work(values[index]!); }
  })); return output;
}
function ref(kind: string, resource: string, version: string, series: string | null = null, type: string | null = null): PlanSolutionFixedRef {
  if (!validId(resource) || !validId(version) || (series !== null && !validId(series))) throw new PlanApprovedSolutionError();
  return Object.freeze({ resource_kind: kind, resource_id: resource, version_id: version,
    spec_series_id: series, spec_type: type });
}

export async function loadPlanApprovedSolutions(project: string,
  readers: PlanApprovedSolutionReaders = {
    outlines: new OutlineReadClient(), outlineVersions: new OutlineVersionReadClient(),
    sections: new SectionReadClient(), sectionVersions: new SectionVersionReadClient(),
    specs: new StructuredSpecListClient(), specDetails: new StructuredSpecReadClient(),
    requirements: new RequirementReadClient(),
  }): Promise<readonly PlanApprovedSolution[]> {
  if (!validId(project)) throw new PlanApprovedSolutionError();
  try {
    const [outlines, specs] = await Promise.all([
      collect(cursor => readers.outlines.list(project, 100, cursor), 200),
      collect(cursor => readers.specs.list(project, 100, cursor), 500),
    ]);
    const active = outlines.filter(item => item.project_id === project && item.outline_state === "ACTIVE"
      && item.current_approved_version_ref !== null);
    const candidates: (PlanApprovedSolution | null)[] = await mapLimited(active, 4, async outline => {
      if (!validId(outline.solution_outline_id) || !validId(outline.current_approved_version_ref)) throw new PlanApprovedSolutionError();
      const current = await readers.outlines.current(project, outline.solution_outline_id);
      if (current.project_id !== project || current.solution_outline_id !== outline.solution_outline_id
        || current.outline_state !== "ACTIVE" || current.current_approved_version_ref !== outline.current_approved_version_ref) return null;
      const version = await readers.outlineVersions.detail(project, current.solution_outline_id, current.current_approved_version_ref);
      if (version.version_state !== "APPROVED") return null;
      const requirements = await mapLimited(version.requirement_refs, 4, async fixedRef => {
        const root = await readers.requirements.getRequirement(project, fixedRef.requirement_id);
        if (root.project_id !== project || root.requirement_id !== fixedRef.requirement_id
          || root.state !== "ACTIVE" || root.current_approved_version_ref !== fixedRef.requirement_version_id) {
          throw new PlanApprovedSolutionError();
        }
        const detail = await readers.requirements.getVersion(project, fixedRef.requirement_id, fixedRef.requirement_version_id);
        if (detail.project_id !== project || detail.requirement_id !== fixedRef.requirement_id
          || detail.requirement_version_id !== fixedRef.requirement_version_id || detail.state !== "APPROVED") {
          throw new PlanApprovedSolutionError();
        }
        return Object.freeze({ requirement_id: fixedRef.requirement_id,
          requirement_version_id: fixedRef.requirement_version_id, requirement_code: root.requirement_code,
          version_no: detail.version_no, title: detail.title, statement: detail.statement });
      });
      if (new Set(requirements.map(item => `${item.requirement_id}|${item.requirement_version_id}`)).size !== requirements.length) {
        throw new PlanApprovedSolutionError();
      }
      const sectionRefs = await mapLimited(version.section_ids, 4, async sectionId => {
        const section = await readers.sections.current(project, sectionId);
        if (section.project_id !== project || section.solution_outline_id !== current.solution_outline_id
          || section.section_state !== "ACTIVE" || !validId(section.current_approved_version_ref)) throw new PlanApprovedSolutionError();
        const fixed = await readers.sectionVersions.detail(project, sectionId, section.current_approved_version_ref);
        if (fixed.version_state !== "APPROVED" || fixed.spec_binding_state === "UNDECLARED") throw new PlanApprovedSolutionError();
        const refs = [ref("SECTION", sectionId, fixed.solution_section_version_id)];
        for (const specRef of fixed.structured_spec_refs) {
          const matches = specs.filter(item => item.project_id === project && item.spec_series_id === specRef.spec_series_id
            && item.structured_solution_spec_id === specRef.structured_solution_spec_id && item.version_state === "APPROVED");
          if (matches.length !== 1) throw new PlanApprovedSolutionError();
          const spec = matches[0]!;
          const detail = await readers.specDetails.detail(project, spec.structured_solution_spec_id);
          if (detail.version_state !== "APPROVED" || detail.spec_series_id !== spec.spec_series_id
            || detail.structured_solution_spec_id !== spec.structured_solution_spec_id) throw new PlanApprovedSolutionError();
          refs.push(ref("STRUCTURED_SPEC", detail.spec_series_id, detail.structured_solution_spec_id,
            detail.spec_series_id, detail.spec_type));
        }
        return { refs, display: [`章节 ${section.section_key} · v${fixed.version_no}`,
          ...fixed.structured_spec_refs.map(s => `专项 ${s.structured_solution_spec_id}`)] };
      });
      const refs = [ref("OUTLINE", current.solution_outline_id, version.solution_outline_version_id),
        ...sectionRefs.flatMap(item => item.refs)];
      return Object.freeze({ outline: version, refs: Object.freeze(refs), requirements: Object.freeze(requirements),
        display: Object.freeze([`方案 ${current.name} · v${version.version_no}`,
          ...sectionRefs.flatMap(item => item.display)]) });
    });
    return Object.freeze(candidates.filter(item => item !== null) as PlanApprovedSolution[]);
  } catch { throw new PlanApprovedSolutionError(); }
}
