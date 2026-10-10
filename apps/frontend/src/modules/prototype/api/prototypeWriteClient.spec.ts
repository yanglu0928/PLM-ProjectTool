import { beforeEach, describe, expect, it, vi } from "vitest";

import { SessionClient } from "@/modules/auth/api/sessionClient";
import { PrototypeWriteClient, PrototypeWriteError, type PrototypeLinkInput,
  type PrototypeTemplateContentInput, type PrototypeVersionCreateInput } from "./prototypeWriteClient";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const packageId = "11234567-89ab-4cde-8123-456789abcdef";
const prototype = "21234567-89ab-4cde-8123-456789abcdef";
const template = "31234567-89ab-4cde-8123-456789abcdef";
const templateVersion = "41234567-89ab-4cde-8123-456789abcdef";
const version = "51234567-89ab-4cde-8123-456789abcdef";
const requirement = "61234567-89ab-4cde-8123-456789abcdef";
const requirementVersion = "71234567-89ab-4cde-8123-456789abcdef";
const actor = "81234567-89ab-4cde-8123-456789abcdef";
const documentVersion = "91234567-89ab-4cde-8123-456789abcdef";
const acceptance = "a1234567-89ab-4cde-8123-456789abcdef";
const link = "b1234567-89ab-4cde-8123-456789abcdef";
const replacement = "c1234567-89ab-4cde-8123-456789abcdef";
const trace = "d1234567-89ab-4cde-8123-456789abcdef";
const review = "e1234567-89ab-4cde-8123-456789abcdef";
const round = "f1234567-89ab-4cde-8123-456789abcdef";
const now = "2026-10-08T12:00:00Z", key = "prototype-write-0001", csrf = "a".repeat(64);

function envelope(data: unknown, status = 200, etag?: string, location?: string): Response {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (etag) headers.ETag = etag; if (location) headers.Location = location;
  return new Response(JSON.stringify({ data, trace_id: trace }), { status, headers });
}
function failure(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: "private" }, trace_id: trace }),
    { status, headers: { "Content-Type": "application/json" } });
}
function login(): Response {
  return envelope({ user: { user_id: actor, username_display: "项目经理" }, deployment_role: "DEPLOYMENT_ADMIN",
    password_change_required: false, authorized_projects: [{ project_id: project, name: "PLM项目", role: "PROJECT_MANAGER" }],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z", csrf_token: csrf });
}
async function writer(...responses: Response[]) {
  const fetcher = vi.fn().mockResolvedValueOnce(login());
  for (const response of responses) fetcher.mockResolvedValueOnce(response);
  const session = new SessionClient(fetcher as typeof fetch); await session.login("manager", "synthetic");
  return { api: new PrototypeWriteClient(session), fetcher };
}

const packageMutation = { prototype_package_id: packageId, project_id: project, name: "原型包", state: "ACTIVE",
  prototype_ids: [prototype], etag: '"v1"' };
const identityMutation = { prototype_id: prototype, project_id: project, name: "交互原型", state: "ACTIVE",
  current_approved_version_ref: null, etag: '"v1"' };
const content: PrototypeTemplateContentInput = { layout_contract: { layout: "two-column" },
  component_contract: { components: [{ kind: "FORM" }] }, applicable_terminals: ["DESKTOP"],
  artifact_refs: [{ artifact_kind: "DOCUMENT_VERSION", target_id: documentVersion }] };
const versionInput: PrototypeVersionCreateInput = { template_id: template, template_version_id: templateVersion,
  artifact_refs: content.artifact_refs, requirement_refs: [{ requirement_id: requirement, requirement_version_id: requirementVersion }],
  interaction_spec: { flow: "guided" }, coverage_summary: { covered: 1 } };
const versionView = { prototype_version_id: version, prototype_id: prototype, project_id: project, version_no: 1,
  state: "DRAFT", supersedes_version_id: null, template_id: template, template_version_id: templateVersion,
  artifact_refs: content.artifact_refs, requirement_refs: versionInput.requirement_refs,
  interaction_spec: versionInput.interaction_spec, coverage_summary: versionInput.coverage_summary,
  content_fingerprint: "b".repeat(64), created_at: now, prototype_etag: '"v1"' };
const linkInput: PrototypeLinkInput = { requirement_id: requirement, requirement_version_id: requirementVersion,
  prototype_id: prototype, prototype_version_id: version, purpose: "VALIDATES",
  coverage: { covered_acceptance_criterion_refs: [acceptance], uncovered_acceptance_criteria: [] } };
function linkView(id: string, state: "ACTIVE" | "REVOKED", etag: string) {
  return { requirement_prototype_link_id: id, project_id: project, ...linkInput, state, created_by: actor,
    created_at: now, superseded_by_ref: null, etag };
}
function templateView(scope: "PROJECT" | "GLOBAL", versionNo: number, revised = false) {
  return { prototype_template_id: template, prototype_template_version_id: revised ? version : templateVersion,
    scope, project_id: scope === "PROJECT" ? project : null, name: "桌面模板", state: "ACTIVE", version_no: versionNo,
    version_state: "PUBLISHED", ...content, content_fingerprint: "a".repeat(64), etag: revised ? '"v1"' : '"v0"',
    ...(revised ? { supersedes_version_id: templateVersion } : {}), created_at: now };
}

describe("PrototypeWriteClient", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("sends all 17 frozen writes with exact method, path, ETag, key and body policy", async () => {
    const packageCreated = { prototype_package_id: packageId, project_id: project, name: "原型包", state: "ACTIVE",
      created_at: now, etag: '"v0"' };
    const prototypeCreated = { prototype_id: prototype, project_id: project, name: "交互原型", state: "ACTIVE",
      current_approved_version_ref: null, created_at: now, etag: '"v0"' };
    const decision = { prototype_id: prototype, project_id: project, name: "交互原型", state: "NOT_REQUIRED",
      scope_decision_id: round, reason: "无需交互原型", impact: "使用标准页面", confirmed_by: actor,
      review_id: null, review_round_id: null, affected_requirement_version_refs: [requirementVersion], decided_at: now, etag: '"v2"' };
    const validation = { audit_event_id: trace, prototype_version_id: version, state: "DRAFT", valid: true,
      blocking_issues: [], warnings: [], coverage_summary: { template_available: true, requirements_available: true,
        artifacts_available: true }, checked_at: now };
    const submission = { review_id: review, review_round_id: round, subject_type: "PRT-03", project_id: project,
      prototype_id: prototype, prototype_version_id: version, policy_ref: "PROTOTYPE_ALL_V1", reviewer_ids: [actor],
      state: "IN_REVIEW", round_no: 1, review_etag: '"v1"', submitted_by: actor, submitted_at: now };
    const { api, fetcher } = await writer(
      envelope(packageCreated, 201, '"v0"', `/api/v1/projects/${project}/prototype-packages/${packageId}`),
      envelope(packageMutation, 200, '"v1"'), envelope(packageMutation, 200, '"v1"'),
      envelope(prototypeCreated, 201, '"v0"', `/api/v1/projects/${project}/prototypes/${prototype}`),
      envelope(identityMutation, 200, '"v1"'), envelope(decision, 200, '"v2"'),
      envelope({ ...identityMutation, state: "ARCHIVED", etag: '"v2"' }, 200, '"v2"'),
      envelope(versionView, 201, '"v1"', `/api/v1/projects/${project}/prototypes/${prototype}/versions/${version}`),
      envelope(validation), envelope(submission, 201, '"v1"'),
      envelope(templateView("PROJECT", 1), 201, '"v0"'), envelope(templateView("GLOBAL", 1), 201, '"v0"'),
      envelope(templateView("PROJECT", 2, true), 201, '"v1"'), envelope(templateView("GLOBAL", 2, true), 201, '"v1"'),
      envelope(linkView(link, "ACTIVE", '"v0"'), 201, '"v0"'), envelope(linkView(link, "REVOKED", '"v1"'), 200, '"v1"'),
      envelope(linkView(replacement, "ACTIVE", '"v0"'), 201, '"v0"'),
    );
    await api.createPackage(project, "原型包", key);
    await api.patchPackage(project, packageId, '"v0"', "原型包");
    await api.setPackageMembers(project, packageId, '"v0"', [prototype], key);
    await api.createPrototype(project, "交互原型", key);
    await api.patchPrototype(project, prototype, '"v0"', "交互原型");
    await api.markNotRequired(project, prototype, '"v1"', { affected_requirement_version_refs: [requirementVersion],
      reason: "无需交互原型", impact: "使用标准页面", review_id: null, review_round_id: null }, key);
    await api.archivePrototype(project, prototype, '"v1"', key);
    await api.createVersion(project, prototype, '"v0"', versionInput, key);
    await api.validateVersion(project, prototype, version, key);
    await api.submitVersionReview(project, prototype, version, [actor], key);
    await api.createProjectTemplate(project, "桌面模板", content, key);
    await api.createGlobalTemplate("桌面模板", content, key);
    await api.reviseProjectTemplate(project, template, '"v0"', content, key);
    await api.reviseGlobalTemplate(template, '"v0"', content, key);
    await api.createLink(project, linkInput, key);
    await api.revokeLink(project, link, key);
    await api.supersedeLink(project, link, linkInput, key);

    expect(fetcher.mock.calls.slice(1).map(call => call[0])).toEqual([
      `/api/v1/projects/${project}/prototype-packages`, `/api/v1/projects/${project}/prototype-packages/${packageId}`,
      `/api/v1/projects/${project}/prototype-packages/${packageId}:set-members`, `/api/v1/projects/${project}/prototypes`,
      `/api/v1/projects/${project}/prototypes/${prototype}`, `/api/v1/projects/${project}/prototypes/${prototype}:mark-not-required`,
      `/api/v1/projects/${project}/prototypes/${prototype}:archive`, `/api/v1/projects/${project}/prototypes/${prototype}/versions`,
      `/api/v1/projects/${project}/prototypes/${prototype}/versions/${version}:validate`,
      `/api/v1/projects/${project}/prototypes/${prototype}/versions/${version}:submit-review`,
      `/api/v1/projects/${project}/prototype-templates`, "/api/v1/global/prototype-templates",
      `/api/v1/projects/${project}/prototype-templates/${template}:revise`, `/api/v1/global/prototype-templates/${template}:revise`,
      `/api/v1/projects/${project}/prototype-requirement-links`,
      `/api/v1/projects/${project}/prototype-requirement-links/${link}:revoke`,
      `/api/v1/projects/${project}/prototype-requirement-links/${link}:supersede`,
    ]);
    const calls = fetcher.mock.calls.slice(1).map(call => call[1] as RequestInit);
    expect(calls[1]).toMatchObject({ method: "PATCH", headers: expect.objectContaining({ "If-Match": '"v0"' }) });
    expect(calls[1]!.headers).not.toHaveProperty("Idempotency-Key");
    expect(calls[5]).toMatchObject({ headers: expect.objectContaining({ "If-Match": '"v1"', "Idempotency-Key": key }) });
    expect(calls[6]).not.toHaveProperty("body"); expect(calls[8]).not.toHaveProperty("body"); expect(calls[15]).not.toHaveProperty("body");
    expect(calls[7]).toMatchObject({ headers: expect.objectContaining({ "If-Match": '"v0"', "Idempotency-Key": key }) });
    expect(JSON.parse(calls[9]!.body as string)).toEqual({ reviewer_ids: [actor], policy_ref: "PROTOTYPE_ALL_V1",
      due_at: null, submission_note: null });
  });

  it("does not retry an uncertain idempotent write and permits caller replay with the same key", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(login())
      .mockRejectedValueOnce(new TypeError("connection reset"))
      .mockResolvedValueOnce(envelope({ prototype_package_id: packageId, project_id: project, name: "原型包",
        state: "ACTIVE", created_at: now, etag: '"v0"' }, 201, '"v0"',
      `/api/v1/projects/${project}/prototype-packages/${packageId}`));
    const session = new SessionClient(fetcher as typeof fetch); await session.login("manager", "synthetic");
    const api = new PrototypeWriteClient(session);
    await expect(api.createPackage(project, "原型包", key)).rejects.toMatchObject({
      code: "PROTOTYPE_WRITE_UNAVAILABLE", uncertain: true,
    });
    expect(fetcher).toHaveBeenCalledTimes(2);
    await expect(api.createPackage(project, "原型包", key)).resolves.toMatchObject({ prototype_package_id: packageId });
    expect((fetcher.mock.calls[1]![1] as RequestInit).body).toBe((fetcher.mock.calls[2]![1] as RequestInit).body);
    expect((fetcher.mock.calls[1]![1] as RequestInit).headers).toEqual((fetcher.mock.calls[2]![1] as RequestInit).headers);
  });

  it("marks non-idempotent PATCH uncertainty for GET reconciliation and sends no key", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(login()).mockRejectedValueOnce(new TypeError("lost response"));
    const session = new SessionClient(fetcher as typeof fetch); await session.login("manager", "synthetic");
    await expect(new PrototypeWriteClient(session).patchPrototype(project, prototype, '"v0"', "新名称"))
      .rejects.toMatchObject({ code: "PROTOTYPE_WRITE_UNAVAILABLE", uncertain: true });
    const init = fetcher.mock.calls[1]![1] as RequestInit;
    expect(init.headers).not.toHaveProperty("Idempotency-Key"); expect(init.headers).toMatchObject({ "If-Match": '"v0"' });
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it.each([
    { ...content, artifact_refs: [{ ...content.artifact_refs[0]!, document_id: project }] },
    { ...content, component_contract: { onclick: "run" } },
    { ...content, applicable_terminals: ["WEB", "DESKTOP"] },
  ])("rejects unsafe structured template input before transport %#", async bad => {
    const { api, fetcher } = await writer();
    await expect(api.createProjectTemplate(project, "模板", bad as PrototypeTemplateContentInput, key))
      .rejects.toMatchObject({ code: "PROTOTYPE_WRITE_INVALID_INPUT" });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("rejects incomplete or overlapping coverage before transport", async () => {
    const { api, fetcher } = await writer();
    await expect(api.createLink(project, { ...linkInput, coverage: { covered_acceptance_criterion_refs: [acceptance],
      uncovered_acceptance_criteria: [{ acceptance_criterion_ref: acceptance, reason: "暂缓" }] } }, key))
      .rejects.toMatchObject({ code: "PROTOTYPE_WRITE_INVALID_INPUT" });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it.each([[409, "CONFLICT_VERSION"], [409, "CONFLICT_IDEMPOTENCY"], [403, "LICENSE_OPERATION_DENIED"],
    [404, "RESOURCE_NOT_FOUND"]] as const)("maps only status-matched public failure %s %s", async (status, code) => {
    const { api } = await writer(failure(status, code));
    await expect(api.createPackage(project, "原型包", key)).rejects.toMatchObject({ code });
  });

  it("fails closed on status/code mismatch and malformed success", async () => {
    let setup = await writer(failure(403, "RESOURCE_NOT_FOUND"));
    await expect(setup.api.createPackage(project, "原型包", key))
      .rejects.toMatchObject({ code: "PROTOTYPE_WRITE_UNAVAILABLE" });
    setup = await writer(envelope({ ...packageMutation, private_note: "hidden" }, 201, '"v1"'));
    await expect(setup.api.createPackage(project, "原型包", key))
      .rejects.toBeInstanceOf(PrototypeWriteError);
  });
});
