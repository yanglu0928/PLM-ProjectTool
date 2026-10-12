/** Bounded metadata-only candidate reads. CREATE Owner revalidates current eligibility. */
import { DocumentReadClient, type DocumentView, type DocumentVersionView } from
  "@/modules/document/api/documentReadClient";
import { EvidenceListClient, type EvidenceSummary } from "@/modules/evidence/api/evidenceListClient";
import { RequirementReadClient, type RequirementCursor, type RequirementView } from
  "@/modules/requirement/api/requirementReadClient";

export interface SectionVersionCandidates {
  readonly documents: readonly DocumentView[];
  readonly requirements: readonly RequirementView[];
  readonly evidence: readonly EvidenceSummary[];
}
export class SectionVersionCandidateError extends Error {
  constructor() { super("来源候选无法完整核对，已停止创建；请刷新后重试。"); this.name = "SectionVersionCandidateError"; }
}
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
function id(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value) && value !== "00000000-0000-0000-0000-000000000000";
}
interface Page<T> { readonly items: readonly T[]; readonly has_more: boolean; readonly next_cursor: string | null }
async function collect<T>(read: (cursor: string | null) => Promise<Page<T>>, maximum: number): Promise<T[]> {
  const all: T[] = []; const cursors = new Set<string>(); let cursor: string | null = null;
  do {
    const page = await read(cursor);
    if (!page || !Array.isArray(page.items) || typeof page.has_more !== "boolean"
      || page.has_more && (!page.items.length || typeof page.next_cursor !== "string"
        || !page.next_cursor || cursors.has(page.next_cursor))
      || !page.has_more && page.next_cursor !== null) throw new SectionVersionCandidateError();
    all.push(...page.items);
    if (all.length > maximum) throw new SectionVersionCandidateError();
    if (!page.has_more) return all;
    cursor = page.next_cursor;
    cursors.add(cursor!);
  } while (true);
}
export async function loadProjectSectionVersionCandidates(project: string,
  documents: Pick<DocumentReadClient, "list">, requirements: Pick<RequirementReadClient, "listRequirements">,
  evidence: Pick<EvidenceListClient, "list">): Promise<SectionVersionCandidates> {
  if (!id(project)) throw new SectionVersionCandidateError();
  try {
    const [docs, reqs, proofs] = await Promise.all([
      collect(cursor => documents.list({ kind: "PROJECT", projectId: project }, cursor), 10_000),
      collect(cursor => requirements.listRequirements(project, 200, cursor as RequirementCursor | null), 10_000),
      collect(cursor => evidence.list({ kind: "PROJECT", projectId: project }, cursor), 10_000),
    ]);
    if (docs.some(item => item.scope !== "PROJECT" || !id(item.document_id))
      || reqs.some(item => item.project_id !== project || !id(item.requirement_id)
        || item.current_approved_version_ref !== null && !id(item.current_approved_version_ref))
      || proofs.some(item => !id(item.evidence_id) || !id(item.document_id) || !id(item.document_version_id))
      || new Set(docs.map(item => item.document_id)).size !== docs.length
      || new Set(reqs.map(item => item.requirement_id)).size !== reqs.length
      || new Set(proofs.map(item => item.evidence_id)).size !== proofs.length) throw new SectionVersionCandidateError();
    return Object.freeze({
      documents: Object.freeze(docs.filter(item => item.state === "ACTIVE")),
      requirements: Object.freeze(reqs.filter(item => item.state === "ACTIVE" && item.current_approved_version_ref)),
      evidence: Object.freeze(proofs.filter(item => item.eligibility_state === "ELIGIBLE")),
    });
  } catch { throw new SectionVersionCandidateError(); }
}
export async function loadProjectDocumentVersionCandidates(project: string, document: string,
  reader: Pick<DocumentReadClient, "listVersions">): Promise<readonly DocumentVersionView[]> {
  if (!id(project) || !id(document)) throw new SectionVersionCandidateError();
  try {
    const versions = await collect(cursor => reader.listVersions({ kind: "PROJECT", projectId: project },
      document, cursor), 500);
    if (versions.some(item => !id(item.document_version_id) || item.availability_state !== "AVAILABLE")
      || new Set(versions.map(item => item.document_version_id)).size !== versions.length
      || versions.some((item, index) => index > 0 && item.version_no >= versions[index - 1]!.version_no)) {
      throw new SectionVersionCandidateError();
    }
    return Object.freeze(versions);
  } catch { throw new SectionVersionCandidateError(); }
}
