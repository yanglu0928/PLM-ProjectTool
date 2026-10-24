import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { ProjectEvidenceCreateClient } from "./projectEvidenceCreateClient";

const actor = "01234567-89ab-4cde-8123-456789abcdef";
const project = "11234567-89ab-4cde-8123-456789abcdef";
const other = "21234567-89ab-4cde-8123-456789abcdef";
const document = "31234567-89ab-4cde-8123-456789abcdef";
const version = "41234567-89ab-4cde-8123-456789abcdef";
const evidence = "51234567-89ab-4cde-8123-456789abcdef";
const key = "synthetic-project-evidence-0001";
const input = { document_id: document, document_version_id: version,
  locator: { locator_type: "DOCUMENT" as const }, display_label: "项目调研记录整文档", display_excerpt: null };
const receipt = { evidence_id: evidence, ...input, content_fingerprint: "a".repeat(64),
  eligibility_state: "CANDIDATE", created_at: "2026-10-25T01:00:00Z", etag: '"v0"' };
function response(data: unknown, status = 201, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify({ data, trace_id: actor }), { status, headers: {
    "Content-Type": "application/json", "Cache-Control": "no-store", ETag: '"v0"',
    Location: `/api/v1/projects/${project}/evidence/${evidence}`, ...headers } });
}
function auth(role: string, projectId = project): Response { return response({
  user: { user_id: actor, username_display: "合成用户" }, deployment_role: "NONE",
  password_change_required: false,
  authorized_projects: [{ project_id: projectId, name: "合成项目", role }],
  absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
  csrf_token: "a".repeat(64) }, 200); }
function harness(role: string, ...results: Response[]) {
  const fetcher = vi.fn(); [auth(role), ...results].forEach(value => fetcher.mockResolvedValueOnce(value));
  const session = new SessionClient(fetcher as typeof fetch);
  return { session, client: new ProjectEvidenceCreateClient(session), fetcher };
}
describe("ProjectEvidenceCreateClient", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });
  it.each(["PROJECT_MANAGER", "IMPLEMENTATION_MEMBER"])("creates a CANDIDATE with private CSRF as %s", async role => {
    const result = harness(role, response(receipt)); await result.session.login("synthetic", "synthetic-only");
    await expect(result.client.create(project, input, key)).resolves.toEqual(receipt);
    expect(result.fetcher.mock.calls[1][0]).toBe(`/api/v1/projects/${project}/evidence`);
    expect(result.fetcher.mock.calls[1][1].headers["X-CSRF-Token"]).toBe("a".repeat(64));
    expect(result.fetcher.mock.calls[1][1].headers["Idempotency-Key"]).toBe(key);
    expect(JSON.parse(result.fetcher.mock.calls[1][1].body)).toEqual(input);
  });
  it("rejects invalid input, wrong project and unauthorized role before write", async () => {
    const result = harness("CUSTOMER_MANAGER"); await result.session.login("synthetic", "synthetic-only");
    await expect(result.client.create(project, input, key)).rejects.toMatchObject({ code: "RESOURCE_NOT_FOUND" });
    const allowed = harness("PROJECT_MANAGER"); await allowed.session.login("synthetic", "synthetic-only");
    await expect(allowed.client.create(other, input, key)).rejects.toMatchObject({ code: "RESOURCE_NOT_FOUND" });
    await expect(allowed.client.create(project, { ...input, locator: { locator_type: "SECTION" } } as never, key))
      .rejects.toMatchObject({ code: "EVIDENCE_CREATE_INVALID" });
    await expect(allowed.client.create(project, input, "short")).rejects.toMatchObject({ code: "EVIDENCE_CREATE_INVALID" });
    expect(result.fetcher).toHaveBeenCalledTimes(1); expect(allowed.fetcher).toHaveBeenCalledTimes(1);
  });
  it("maps refusal and rejects forged approval or mismatched receipt", async () => {
    const refusal = harness("PROJECT_MANAGER", new Response(JSON.stringify({ error: {
      code: "PROJECT_ARCHIVED", message: "private" }, trace_id: actor }), { status: 409,
      headers: { "Content-Type": "application/json" } }));
    await refusal.session.login("synthetic", "synthetic-only");
    await expect(refusal.client.create(project, input, key)).rejects.toMatchObject({ code: "PROJECT_ARCHIVED" });
    for (const bad of [response({ ...receipt, eligibility_state: "ELIGIBLE" }),
      response(receipt, 201, { Location: `/api/v1/projects/${other}/evidence/${evidence}` }),
      response(receipt, 201, { "Cache-Control": "public" }), response({ ...receipt, internal_path: "hidden" })]) {
      const result = harness("PROJECT_MANAGER", bad); await result.session.login("synthetic", "synthetic-only");
      await expect(result.client.create(project, input, key)).rejects.toMatchObject({ code: "EVIDENCE_CREATE_UNCERTAIN" });
    }
  });
});
