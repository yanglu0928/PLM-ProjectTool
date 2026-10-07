import { afterEach, describe, expect, it, vi } from "vitest";

import { RequirementReadClient, RequirementReadError, parseRequirement, parseRequirementVersion,
  type RequirementCursor, type RequirementVersionCursor } from "./requirementReadClient";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const requirement = "11234567-89ab-4cde-8123-456789abcdef";
const version = "21234567-89ab-4cde-8123-456789abcdef";
const actor = "31234567-89ab-4cde-8123-456789abcdef";
const source = "41234567-89ab-4cde-8123-456789abcdef";
const evidence = "51234567-89ab-4cde-8123-456789abcdef";
const baseline = "61234567-89ab-4cde-8123-456789abcdef";
const capability = "71234567-89ab-4cde-8123-456789abcdef";
const trace = "81234567-89ab-4cde-8123-456789abcdef";
const now = "2026-10-08T08:00:00.000000Z";
const token = `${"A".repeat(24)}.${"B".repeat(43)}`;
const root = { requirement_id: requirement, project_id: project, requirement_code: "REQ-001", state: "ACTIVE",
  current_approved_version_ref: null, created_by: actor, created_at: now, updated_by: null, updated_at: now, etag: '"v0"' };
const summary = { requirement_version_id: version, requirement_id: requirement, project_id: project, version_no: 1,
  state: "DRAFT", title: "用户主数据同步", domain_name: "PLM", priority: "HIGH", risk: "MEDIUM",
  classification: "STANDARD_FUNCTION", content_fingerprint: "a".repeat(64),
  declared_counts: { sources: 1, acceptance_criteria: 1, capability_assessments: 1,
    assumptions: 1, exclusions: 0, dependencies: 0, ai_tasks: 0 },
  supersedes_version_ref: null, review_ref: null, review_round_ref: null, created_by: actor, created_at: now };
const detail = { ...summary, statement: "系统应同步用户主数据。", rationale: "保证账号主数据一致。",
  sources: [{ ordinal: 0, source_type: "PROJECT_EVIDENCE", source_object_id: evidence,
    source_version_ref: null, evidence_refs: [{ evidence_id: evidence, ordinal: 0 }] }],
  acceptance_criteria: [{ ordinal: 0, observable_result: "目标系统出现用户", verification_method: "比对用户清单",
    required_data: "用户样本", required_environment: "Windows 11 测试环境", evidence_requirement: "签字验收记录" }],
  capability_assessments: [{ ordinal: 0, baseline_version_id: baseline, capability_item_id: capability,
    match_type: "DIRECT", fit_gap: "标准能力直接覆盖", constraints_text: "启用标准接口配置", assessor_kind: "HUMAN",
    assessed_by: actor, assessed_at: now, confirmation_state: "CONFIRMED",
    evidence_refs: [{ evidence_id: evidence, evidence_role: "PROJECT_CONTEXT", ordinal: 0 }] }],
  assumptions: [{ ordinal: 0, text: "客户提供有效用户清单" }], exclusions: [], dependencies: [], ai_tasks: [] };

function response(data: unknown, headerEtag?: string): Response {
  const headers: Record<string, string> = { "Content-Type": "application/json" }; if (headerEtag) headers.ETag = headerEtag;
  return new Response(JSON.stringify({ data, trace_id: trace }), { status: 200, headers });
}
function failure(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: "private" }, trace_id: trace }),
    { status, headers: { "Content-Type": "application/json" } });
}
function client(...values: Response[]) {
  const fetcher = vi.fn(); for (const value of values) fetcher.mockResolvedValueOnce(value);
  return { api: new RequirementReadClient(fetcher as typeof fetch), fetcher };
}

describe("RequirementReadClient", () => {
  it("invokes a supplied browser fetch without a RequirementReadClient receiver", async () => {
    let receiver: unknown = "unset";
    const fetcher = function(this: unknown) { receiver = this; return Promise.resolve(response({ items: [root], next_cursor: null, has_more: false })); } as typeof fetch;
    await new RequirementReadClient(fetcher).listRequirements(project);
    expect(receiver).toBeUndefined();
  });
  afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); });

  it("reads Requirement page/detail with no-store, opaque cursor and strong ETag", async () => {
    const { api, fetcher } = client(response({ items: [root], next_cursor: token, has_more: true }), response(root, '"v0"'));
    const page = await api.listRequirements(project, 25);
    expect(page.next_cursor).toBe(token); expect(Object.isFrozen(page.items[0])).toBe(true);
    expect(fetcher.mock.calls[0]).toEqual([`/api/v1/projects/${project}/requirements?page_size=25`, expect.objectContaining({
      method: "GET", credentials: "same-origin", cache: "no-store", redirect: "error", headers: { Accept: "application/json" },
    })]);
    await expect(api.getRequirement(project, requirement)).resolves.toMatchObject({ etag: '"v0"' });
  });

  it("keeps Requirement and Version cursor families on their exact parent paths", async () => {
    const { api, fetcher } = client(response({ items: [], next_cursor: null, has_more: false }),
      response({ items: [], next_cursor: null, has_more: false }));
    await api.listRequirements(project, 50, token as RequirementCursor);
    await api.listVersions(project, requirement, 50, token as RequirementVersionCursor);
    expect(fetcher.mock.calls.map(call => call[0])).toEqual([
      `/api/v1/projects/${project}/requirements?page_size=50&cursor=${token}`,
      `/api/v1/projects/${project}/requirements/${requirement}/versions?page_size=50&cursor=${token}`,
    ]);
  });

  it("reads a complete fixed Version and freezes source evidence", async () => {
    const value = await client(response(detail)).api.getVersion(project, requirement, version);
    expect(value.sources[0]).toMatchObject({ source_type: "PROJECT_EVIDENCE", source_object_id: evidence });
    expect(Object.isFrozen(value.sources[0]!.evidence_refs)).toBe(true);
    expect(value.acceptance_criteria[0]!.required_environment).toContain("Windows 11");
  });

  it.each([
    { ...root, private_note: "secret" }, { ...root, project_id: actor }, { ...root, etag: "v0" },
    { ...root, updated_at: "2026-10-08T07:59:59Z" },
  ])("rejects unsafe Requirement projection %#", bad => {
    expect(() => parseRequirement(bad, project, requirement)).toThrowError(RequirementReadError);
  });

  it.each([
    { ...detail, private_body: "copied source" },
    { ...detail, declared_counts: { ...detail.declared_counts, sources: 2 } },
    { ...detail, sources: [{ ...detail.sources[0], ordinal: 1 }] },
    { ...detail, sources: [{ ...detail.sources[0], evidence_refs: [{ evidence_id: evidence, ordinal: 1 }] }] },
    { ...detail, review_ref: actor, review_round_ref: null },
    { ...detail, capability_assessments: [{ ...detail.capability_assessments[0], assessor_kind: "AI" }] },
  ])("rejects inconsistent Version detail %#", bad => {
    expect(() => parseRequirementVersion(bad, project, requirement, version)).toThrowError(RequirementReadError);
  });

  it("rejects page ordering, duplicate identities and cursor replay", async () => {
    const older = { ...root, requirement_id: actor, updated_at: "2026-10-08T07:00:00Z" };
    await expect(client(response({ items: [older, root], next_cursor: null, has_more: false })).api.listRequirements(project))
      .rejects.toMatchObject({ code: "REQUIREMENT_READ_UNAVAILABLE" });
    await expect(client(response({ items: [summary, summary], next_cursor: null, has_more: false })).api
      .listVersions(project, requirement)).rejects.toMatchObject({ code: "REQUIREMENT_READ_UNAVAILABLE" });
    await expect(client(response({ items: [summary], next_cursor: token, has_more: true })).api
      .listVersions(project, requirement, 50, token as RequirementVersionCursor))
      .rejects.toMatchObject({ code: "REQUIREMENT_READ_UNAVAILABLE" });
  });

  it.each(["../admin", project.toUpperCase(), "00000000-0000-0000-0000-000000000000"])(
    "rejects unsafe ids before network: %s", async bad => {
      const { api, fetcher } = client(response({ items: [], next_cursor: null, has_more: false }));
      await expect(api.listRequirements(bad)).rejects.toMatchObject({ code: "REQUIREMENT_READ_INVALID_INPUT" });
      await expect(api.getVersion(project, requirement, bad)).rejects.toMatchObject({ code: "REQUIREMENT_READ_INVALID_INPUT" });
      expect(fetcher).not.toHaveBeenCalled();
    });

  it.each([0, 201, 1.5, Number.NaN])("rejects invalid page size %s", async size => {
    const { api, fetcher } = client(response({ items: [], next_cursor: null, has_more: false }));
    await expect(api.listVersions(project, requirement, size)).rejects.toMatchObject({ code: "REQUIREMENT_READ_INVALID_INPUT" });
    expect(fetcher).not.toHaveBeenCalled();
  });

  it.each([[401, "AUTH_SESSION_EXPIRED"], [403, "LICENSE_OPERATION_DENIED"], [404, "RESOURCE_NOT_FOUND"],
    [409, "PROJECT_ARCHIVED"]] as const)("maps only matching safe error %s %s", async (status, code) => {
    await expect(client(failure(status, code)).api.getRequirement(project, requirement)).rejects.toMatchObject({ code });
  });

  it("fails closed on wrong ETag, private error, content type and timeout", async () => {
    await expect(client(response(root, '"v9"')).api.getRequirement(project, requirement))
      .rejects.toMatchObject({ code: "REQUIREMENT_READ_UNAVAILABLE" });
    await expect(client(failure(403, "RESOURCE_NOT_FOUND")).api.getRequirement(project, requirement))
      .rejects.toMatchObject({ code: "REQUIREMENT_READ_UNAVAILABLE" });
    const html = new Response("x", { status: 200, headers: { "Content-Type": "text/html" } });
    await expect(client(html).api.getRequirement(project, requirement))
      .rejects.toMatchObject({ code: "REQUIREMENT_READ_UNAVAILABLE" });
    vi.useFakeTimers(); const api = new RequirementReadClient(vi.fn((_path, init) => new Promise((_resolve, reject) => {
      init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
    })) as typeof fetch, 5);
    const pending = api.getRequirement(project, requirement);
    const assertion = expect(pending).rejects.toMatchObject({ code: "REQUIREMENT_READ_UNAVAILABLE" });
    await vi.advanceTimersByTimeAsync(5); await assertion;
  });
});
