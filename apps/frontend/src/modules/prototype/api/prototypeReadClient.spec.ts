import { afterEach, describe, expect, it, vi } from "vitest";

import { PrototypeIdentityReadClient, PrototypeLinkReadClient, PrototypePackageReadClient,
  PrototypeReadError, PrototypeTemplateReadClient, PrototypeVersionReadClient,
  parsePrototypeLink, parsePrototypePackage, parsePrototypeTemplate, parsePrototypeVersion,
  type PrototypeCursor } from "./prototypeReadClient";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const packageId = "11234567-89ab-4cde-8123-456789abcdef";
const prototype = "21234567-89ab-4cde-8123-456789abcdef";
const template = "31234567-89ab-4cde-8123-456789abcdef";
const templateVersion = "41234567-89ab-4cde-8123-456789abcdef";
const version = "51234567-89ab-4cde-8123-456789abcdef";
const requirement = "61234567-89ab-4cde-8123-456789abcdef";
const requirementVersion = "71234567-89ab-4cde-8123-456789abcdef";
const actor = "81234567-89ab-4cde-8123-456789abcdef";
const documentId = "91234567-89ab-4cde-8123-456789abcdef";
const documentVersion = "a1234567-89ab-4cde-8123-456789abcdef";
const acceptance = "b1234567-89ab-4cde-8123-456789abcdef";
const link = "c1234567-89ab-4cde-8123-456789abcdef";
const trace = "d1234567-89ab-4cde-8123-456789abcdef";
const now = "2026-10-08T08:00:00.000000Z";
const token = `${"A".repeat(24)}.${"B".repeat(43)}`;

const root = { project_id: project, name: "交互原型", created_by: actor, created_at: now,
  updated_by: null, updated_at: now, etag: '"v0"' };
const packageSummary = { ...root, prototype_package_id: packageId, state: "ACTIVE" };
const prototypeSummary = { ...root, prototype_id: prototype, state: "ACTIVE", current_approved_version_ref: null };
const templateView = { prototype_template_id: template, prototype_template_version_id: templateVersion,
  scope: "PROJECT", project_id: project, name: "桌面原型模板", state: "ACTIVE", version_no: 1,
  version_state: "PUBLISHED", layout_contract: { layout: "two-column" },
  component_contract: { components: [{ kind: "FORM" }] }, applicable_terminals: ["DESKTOP"],
  artifact_refs: [{ artifact_kind: "DOCUMENT_VERSION", target_id: documentVersion, document_id: documentId }],
  content_fingerprint: "a".repeat(64), etag: '"v0"', supersedes_version_id: null,
  is_current: true, updated_at: now, created_at: now };
const versionView = { prototype_version_id: version, prototype_id: prototype, project_id: project, version_no: 1,
  state: "DRAFT", supersedes_version_id: null, template_id: template, template_version_id: templateVersion,
  artifact_refs: [{ artifact_kind: "DOCUMENT_VERSION", target_id: documentVersion, document_id: documentId }],
  requirement_refs: [{ requirement_id: requirement, requirement_version_id: requirementVersion }],
  interaction_spec: { interaction: "guided" }, coverage_summary: { covered: 1 },
  content_fingerprint: "b".repeat(64), created_at: now };
const linkView = { requirement_prototype_link_id: link, project_id: project, requirement_id: requirement,
  requirement_version_id: requirementVersion, prototype_id: prototype, prototype_version_id: version,
  purpose: "VALIDATES", coverage: { covered_acceptance_criterion_refs: [acceptance], uncovered_acceptance_criteria: [] },
  state: "ACTIVE", created_by: actor, created_at: now, superseded_by_ref: null, etag: '"v0"' };

function response(data: unknown, headerEtag?: string): Response {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (headerEtag) headers.ETag = headerEtag;
  return new Response(JSON.stringify({ data, trace_id: trace }), { status: 200, headers });
}
function failure(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: "private" }, trace_id: trace }),
    { status, headers: { "Content-Type": "application/json" } });
}
function fetcher(...values: Response[]) {
  const mock = vi.fn(); for (const value of values) mock.mockResolvedValueOnce(value); return mock as unknown as typeof fetch;
}
function page(item?: unknown, next: string | null = null) {
  return { items: item === undefined ? [] : [item], next_cursor: next, has_more: next !== null };
}

describe("Prototype five-family read clients", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); });

  it("uses the nine frozen GET paths with no-store and family-specific cursors", async () => {
    const mock = fetcher(
      response(page(packageSummary, token)), response({ ...packageSummary, prototype_ids: [prototype] }, '"v0"'),
      response(page(prototypeSummary)), response(prototypeSummary, '"v0"'),
      response(page(templateView)), response(page({ ...templateView, scope: "GLOBAL", project_id: null })),
      response(page(versionView)), response(versionView), response(page(linkView)),
    );
    await new PrototypePackageReadClient(mock).list(project, 25);
    await new PrototypePackageReadClient(mock).get(project, packageId);
    await new PrototypeIdentityReadClient(mock).list(project);
    await new PrototypeIdentityReadClient(mock).get(project, prototype);
    await new PrototypeTemplateReadClient(mock).listProject(project);
    await new PrototypeTemplateReadClient(mock).listGlobal();
    await new PrototypeVersionReadClient(mock).list(project, prototype);
    await new PrototypeVersionReadClient(mock).get(project, prototype, version);
    await new PrototypeLinkReadClient(mock).list(project);
    expect((mock as unknown as ReturnType<typeof vi.fn>).mock.calls.map(call => call[0])).toEqual([
      `/api/v1/projects/${project}/prototype-packages?page_size=25`,
      `/api/v1/projects/${project}/prototype-packages/${packageId}`,
      `/api/v1/projects/${project}/prototypes?page_size=50`,
      `/api/v1/projects/${project}/prototypes/${prototype}`,
      `/api/v1/projects/${project}/prototype-templates?page_size=50`,
      "/api/v1/global/prototype-templates?page_size=50",
      `/api/v1/projects/${project}/prototypes/${prototype}/versions?page_size=50`,
      `/api/v1/projects/${project}/prototypes/${prototype}/versions/${version}`,
      `/api/v1/projects/${project}/prototype-requirement-links?page_size=50`,
    ]);
    expect((mock as unknown as ReturnType<typeof vi.fn>).mock.calls[0]![1]).toEqual(expect.objectContaining({
      method: "GET", credentials: "same-origin", cache: "no-store", redirect: "error", headers: { Accept: "application/json" },
    }));
  });

  it("invokes native-style fetch without binding a client receiver", async () => {
    let receiver: unknown = "unset";
    const native = function(this: unknown) { receiver = this; return Promise.resolve(response(page(packageSummary))); } as typeof fetch;
    await new PrototypePackageReadClient(native).list(project);
    expect(receiver).toBeUndefined();
  });

  it("normalizes legacy DocumentVersion references to unavailable locators", () => {
    const legacyTemplate = { ...templateView,
      artifact_refs: [{ artifact_kind: "DOCUMENT_VERSION", target_id: documentVersion }] };
    const legacyVersion = { ...versionView,
      artifact_refs: [{ artifact_kind: "DOCUMENT_VERSION", target_id: documentVersion }] };
    expect(parsePrototypeTemplate(legacyTemplate, "PROJECT", project).artifact_refs[0]!.document_id).toBeNull();
    expect(parsePrototypeVersion(legacyVersion, project, prototype, version).artifact_refs[0]!.document_id).toBeNull();
  });

  it("keeps projected document roots immutable and scoped", () => {
    const parsed = parsePrototypeTemplate(templateView, "PROJECT", project);
    expect(parsed.artifact_refs[0]).toMatchObject({ target_id: documentVersion, document_id: documentId });
    expect(Object.isFrozen(parsed.component_contract)).toBe(true);
    expect(Object.isFrozen((parsed.component_contract.components as readonly unknown[]))).toBe(true);
    expect(() => parsePrototypeTemplate({ ...templateView, project_id: actor }, "PROJECT", project))
      .toThrowError(PrototypeReadError);
  });

  it.each([
    { ...templateView, private_path: "D:/secret" },
    { ...templateView, artifact_refs: [{ artifact_kind: "OUTPUT_ARTIFACT", target_id: documentVersion, document_id: documentId }] },
    { ...templateView, component_contract: { onclick: "doWork" } },
    { ...templateView, component_contract: { help: "javascript:alert(1)" } },
    { ...templateView, applicable_terminals: ["WEB", "DESKTOP"] },
  ])("rejects unsafe Template projection %#", bad => {
    expect(() => parsePrototypeTemplate(bad, "PROJECT", project)).toThrowError(PrototypeReadError);
  });

  it.each([
    { ...versionView, private_body: "copied source" },
    { ...versionView, prototype_id: actor },
    { ...versionView, supersedes_version_id: actor },
    { ...versionView, requirement_refs: [versionView.requirement_refs[0], versionView.requirement_refs[0]] },
    { ...versionView, interaction_spec: { src: "https://example.invalid" } },
  ])("rejects inconsistent Version projection %#", bad => {
    expect(() => parsePrototypeVersion(bad, project, prototype, version)).toThrowError(PrototypeReadError);
  });

  it("enforces complete, disjoint and sorted AcceptanceCriterion coverage", () => {
    expect(parsePrototypeLink(linkView, project).coverage.covered_acceptance_criterion_refs).toEqual([acceptance]);
    expect(() => parsePrototypeLink({ ...linkView, coverage: {
      covered_acceptance_criterion_refs: [acceptance],
      uncovered_acceptance_criteria: [{ acceptance_criterion_ref: acceptance, reason: "暂缓" }],
    } }, project)).toThrowError(PrototypeReadError);
    expect(() => parsePrototypeLink({ ...linkView, coverage: {
      covered_acceptance_criterion_refs: [], uncovered_acceptance_criteria: [],
    } }, project)).toThrowError(PrototypeReadError);
  });

  it("requires matching strong ETag on package and prototype details", async () => {
    await expect(new PrototypePackageReadClient(fetcher(
      response({ ...packageSummary, prototype_ids: [] }, '"v9"'))).get(project, packageId))
      .rejects.toMatchObject({ code: "PROTOTYPE_READ_UNAVAILABLE" });
    await expect(new PrototypeIdentityReadClient(fetcher(response(prototypeSummary))).get(project, prototype))
      .rejects.toMatchObject({ code: "PROTOTYPE_READ_UNAVAILABLE" });
  });

  it("rejects page order, duplicates and cursor replay", async () => {
    const newerId = "f1234567-89ab-4cde-8123-456789abcdef";
    const wrong = { ...packageSummary, prototype_package_id: newerId, updated_at: "2026-10-08T09:00:00Z" };
    await expect(new PrototypePackageReadClient(fetcher(response({ items: [packageSummary, wrong], next_cursor: null, has_more: false })))
      .list(project)).rejects.toMatchObject({ code: "PROTOTYPE_READ_UNAVAILABLE" });
    await expect(new PrototypeVersionReadClient(fetcher(response({ items: [versionView, versionView], next_cursor: null, has_more: false })))
      .list(project, prototype)).rejects.toMatchObject({ code: "PROTOTYPE_READ_UNAVAILABLE" });
    await expect(new PrototypeIdentityReadClient(fetcher(response(page(prototypeSummary, token))))
      .list(project, 50, token as PrototypeCursor)).rejects.toMatchObject({ code: "PROTOTYPE_READ_UNAVAILABLE" });
  });

  it.each(["../admin", project.toUpperCase(), "00000000-0000-0000-0000-000000000000"])(
    "rejects unsafe identifiers before network: %s", async bad => {
      const mock = fetcher(response(page()));
      await expect(new PrototypeVersionReadClient(mock).get(project, prototype, bad))
        .rejects.toMatchObject({ code: "PROTOTYPE_READ_INVALID_INPUT" });
      await expect(new PrototypePackageReadClient(mock).list(bad))
        .rejects.toMatchObject({ code: "PROTOTYPE_READ_INVALID_INPUT" });
      expect(mock).not.toHaveBeenCalled();
    });

  it.each([0, 101, 1.5, Number.NaN])("enforces Version page size before network: %s", async size => {
    const mock = fetcher(response(page()));
    await expect(new PrototypeVersionReadClient(mock).list(project, prototype, size))
      .rejects.toMatchObject({ code: "PROTOTYPE_READ_INVALID_INPUT" });
    expect(mock).not.toHaveBeenCalled();
  });

  it.each([[401, "AUTH_SESSION_EXPIRED"], [403, "LICENSE_OPERATION_DENIED"], [404, "RESOURCE_NOT_FOUND"],
    [409, "PROJECT_ARCHIVED"]] as const)("maps only matching safe error %s %s", async (status, code) => {
    await expect(new PrototypeLinkReadClient(fetcher(failure(status, code))).list(project)).rejects.toMatchObject({ code });
  });

  it("fails closed on private errors, extra envelope data, HTML and timeout", async () => {
    await expect(new PrototypeLinkReadClient(fetcher(failure(403, "RESOURCE_NOT_FOUND"))).list(project))
      .rejects.toMatchObject({ code: "PROTOTYPE_READ_UNAVAILABLE" });
    const extra = new Response(JSON.stringify({ data: page(), trace_id: trace, private: true }),
      { status: 200, headers: { "Content-Type": "application/json" } });
    await expect(new PrototypeLinkReadClient(fetcher(extra)).list(project))
      .rejects.toMatchObject({ code: "PROTOTYPE_READ_UNAVAILABLE" });
    await expect(new PrototypeLinkReadClient(fetcher(new Response("x", {
      status: 200, headers: { "Content-Type": "text/html" },
    }))).list(project)).rejects.toMatchObject({ code: "PROTOTYPE_READ_UNAVAILABLE" });
    vi.useFakeTimers();
    const api = new PrototypeLinkReadClient(vi.fn((_path, init) => new Promise((_resolve, reject) => {
      init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
    })) as typeof fetch, 5);
    const pending = api.list(project); const assertion = expect(pending).rejects.toMatchObject({ code: "PROTOTYPE_READ_UNAVAILABLE" });
    await vi.advanceTimersByTimeAsync(5); await assertion;
  });

  it("rejects malformed package members instead of exposing hidden identifiers", () => {
    expect(() => parsePrototypePackage({ ...packageSummary, prototype_ids: [prototype, prototype] }, project, packageId, true))
      .toThrowError(PrototypeReadError);
  });
});
