import { afterEach, describe, expect, it, vi } from "vitest";
import { SectionVersionReadClient, SectionVersionReadError } from "./sectionVersionReadClient";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const section = "11234567-89ab-4cde-8123-456789abcdef";
const version = "21234567-89ab-4cde-8123-456789abcdef";
const older = "31234567-89ab-4cde-8123-456789abcdef";
const requirement = "41234567-89ab-4cde-8123-456789abcdef";
const evidence = "51234567-89ab-4cde-8123-456789abcdef";
const spec = "71234567-89ab-4cde-8123-456789abcdef";
const trace = "61234567-89ab-4cde-8123-456789abcdef";
const cursor = `${"a".repeat(100)}.${"b".repeat(43)}`;
const item = { solution_section_version_id: version, solution_section_id: section,
  project_id: project, version_no: 2, version_state: "DRAFT", title: "正文草案",
  content_fingerprint: "a".repeat(64), declared_requirement_count: 1,
  declared_evidence_count: 1, spec_binding_state: "FIXED_REFS", declared_spec_count: 1,
  assumption_count: 1, exclusion_count: 0,
  supersedes_version_ref: older, review_ref: null, review_round_ref: null,
  created_by: project, created_at: "2026-10-12T00:00:00Z" };
const detail = { ...item, content_document_version_ref: older, content_artifact_ref: null,
  requirement_refs: [{ requirement_id: requirement, requirement_version_id: older }],
  evidence_ids: [evidence], assumptions: [{ note: "待补充" }], exclusions: [],
  spec_not_required_reason: null,
  structured_spec_refs: [{ spec_series_id: spec, structured_solution_spec_id: older,
    fit_rationale: "固定章节需求适配依据" }] };
function response(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(status === 200 ? { data, trace_id: trace }
    : { error: { code: data, message: "synthetic" }, trace_id: trace }), { status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store",
      "X-Trace-Id": trace } });
}

describe("SectionVersion history read client", () => {
  afterEach(() => vi.restoreAllMocks());

  it("reads minimal ordered pages and fixed detail without inventing source eligibility", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response({ items: [item], next_cursor: cursor,
      has_more: true })).mockResolvedValueOnce(response({ items: [{ ...item,
      solution_section_version_id: older, version_no: 1, supersedes_version_ref: null }],
      next_cursor: null, has_more: false })).mockResolvedValueOnce(response(detail));
    const client = new SectionVersionReadClient(fetcher as typeof fetch);
    const first = await client.list(project, section, 1);
    expect(first.items[0]?.version_no).toBe(2);
    expect("evidence_ids" in first.items[0]!).toBe(false);
    expect((await client.list(project, section, 1, first.next_cursor)).items[0]?.version_no).toBe(1);
    const fixed = await client.detail(project, section, version);
    expect(fixed.evidence_ids).toEqual([evidence]);
    expect(fixed.structured_spec_refs).toHaveLength(1);
    expect(fetcher.mock.calls[0]?.[0]).toBe(
      `/api/v1/projects/${project}/solution-sections/${section}/versions?page_size=1`);
    expect(fetcher.mock.calls[1]?.[0]).toContain(`cursor=${cursor}`);
    expect(fetcher.mock.calls[2]?.[1]).toMatchObject({ method: "GET", credentials: "same-origin",
      cache: "no-store", redirect: "error" });
  });

  it("fails closed on cross-project identity, count, order, repeated cursor and bogus content refs", async () => {
    const invalid = [
      { items: [{ ...item, project_id: older }], next_cursor: null, has_more: false },
      { items: [{ ...item, version_no: 1 }, item], next_cursor: null, has_more: false },
      { items: [item], next_cursor: cursor, has_more: true },
    ];
    for (const data of invalid) {
      const client = new SectionVersionReadClient(vi.fn().mockResolvedValue(response(data)) as typeof fetch);
      await expect(client.list(project, section, 2, data.next_cursor === cursor ? cursor : null))
        .rejects.toMatchObject({ code: "SECTION_VERSION_UNAVAILABLE" });
    }
    for (const broken of [{ ...detail, declared_evidence_count: 2 },
      { ...detail, content_artifact_ref: evidence },
      { ...detail, declared_spec_count: 2 },
      { ...detail, spec_binding_state: "NONE_REQUIRED" },
      { ...detail, structured_spec_refs: [{ ...detail.structured_spec_refs[0], fit_rationale: " bad " }] },
      { ...detail, requirement_refs: [{ requirement_id: "bad", requirement_version_id: older }] }]) {
      await expect(new SectionVersionReadClient(vi.fn().mockResolvedValue(response(broken)) as typeof fetch)
        .detail(project, section, version)).rejects.toMatchObject({ code: "SECTION_VERSION_UNAVAILABLE" });
    }
  });

  it("accepts explicit no-spec declarations and rejects inconsistent fixed-spec payloads", async () => {
    const none = { ...detail, spec_binding_state: "NONE_REQUIRED", declared_spec_count: 0,
      spec_not_required_reason: "合成项目声明无需专项", structured_spec_refs: [] };
    const accepted = new SectionVersionReadClient(vi.fn().mockResolvedValue(response(none)) as typeof fetch);
    expect((await accepted.detail(project, section, version)).spec_not_required_reason)
      .toBe("合成项目声明无需专项");
    for (const broken of [
      { ...none, spec_not_required_reason: " 无效空格 " },
      { ...none, structured_spec_refs: detail.structured_spec_refs },
      { ...detail, structured_spec_refs: [{ ...detail.structured_spec_refs[0], unknown: true }] },
      { ...detail, structured_spec_refs: [detail.structured_spec_refs[0], detail.structured_spec_refs[0]],
        declared_spec_count: 2 },
    ]) {
      const client = new SectionVersionReadClient(vi.fn().mockResolvedValue(response(broken)) as typeof fetch);
      await expect(client.detail(project, section, version)).rejects.toMatchObject({
        code: "SECTION_VERSION_UNAVAILABLE" });
    }
  });

  it("maps only safe error codes and rejects transport anomalies", async () => {
    const missing = new SectionVersionReadClient(vi.fn().mockResolvedValue(
      response("RESOURCE_NOT_FOUND", 404)) as typeof fetch);
    await expect(missing.detail(project, section, version)).rejects.toMatchObject({
      code: "RESOURCE_NOT_FOUND" });
    const unknown = new SectionVersionReadClient(vi.fn().mockResolvedValue(
      response("OTHER", 500)) as typeof fetch);
    await expect(unknown.list(project, section)).rejects.toMatchObject({
      code: "SECTION_VERSION_UNAVAILABLE" });
    const noStore = new Response(JSON.stringify({ data: { items: [], next_cursor: null,
      has_more: false }, trace_id: trace }), { headers: { "Content-Type": "application/json",
      "X-Trace-Id": trace } });
    await expect(new SectionVersionReadClient(vi.fn().mockResolvedValue(noStore) as typeof fetch)
      .list(project, section)).rejects.toMatchObject({ code: "SECTION_VERSION_UNAVAILABLE" });
  });

  it("rejects invalid route inputs before network access", async () => {
    const fetcher = vi.fn();
    const client = new SectionVersionReadClient(fetcher as typeof fetch);
    await expect(client.list("bad", section)).rejects.toBeInstanceOf(SectionVersionReadError);
    await expect(client.list(project, section, 0)).rejects.toBeInstanceOf(SectionVersionReadError);
    await expect(client.detail(project, section, "bad")).rejects.toBeInstanceOf(SectionVersionReadError);
    expect(fetcher).not.toHaveBeenCalled();
  });
});
