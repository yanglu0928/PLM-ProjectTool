import { describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { ReferenceReviseClient, type ReferenceReviseInput } from "./referenceReviseClient";

const actor = "01234567-89ab-4cde-8123-456789abcdef";
const project = "11234567-89ab-4cde-8123-456789abcdef";
const root = "21234567-89ab-4cde-8123-456789abcdef";
const version = "31234567-89ab-4cde-8123-456789abcdef";
const prior = "41234567-89ab-4cde-8123-456789abcdef";
const document = "51234567-89ab-4cde-8123-456789abcdef";
const trace = "61234567-89ab-4cde-8123-456789abcdef";
const input: ReferenceReviseInput = { document_version_ids: [document], evidence_ids: [],
  source_project_class: "PLM", deidentification_class: "PROJECT_INTERNAL",
  applicability: { industry: "synthetic" } };
const result = { reference_solution_id: root, reference_version_id: version,
  scope: "PROJECT", project_id: project, version_no: 3, version_state: "DRAFT",
  supersedes_version_ref: prior, created_at: "2026-10-09T00:00:00Z", etag: '"v6"' };
function sessionResponse(role: string): Response {
  return new Response(JSON.stringify({ data: {
    user: { user_id: actor, username_display: "Synthetic user" },
    deployment_role: role === "DEPLOYMENT_ADMIN" ? role : "NONE",
    password_change_required: false,
    authorized_projects: role === "DEPLOYMENT_ADMIN" ? [] : [{ project_id: project, name: "Synthetic", role }],
    absolute_expires_at: "2030-01-11T00:00:00Z", idle_expires_at: "2030-01-10T01:00:00Z",
    csrf_token: "a".repeat(64),
  }, trace_id: trace }), { status: 200, headers: { "Content-Type": "application/json" } });
}
function envelope(data: unknown = result, status = 201): Response {
  return new Response(JSON.stringify({ data, trace_id: trace }), { status, headers: {
    "Content-Type": "application/json", "Cache-Control": "no-store",
    "X-Trace-Id": trace, "ETag": '"v6"' } });
}
async function setup(role = "PROJECT_MANAGER", response?: Response) {
  const fetcher = vi.fn().mockResolvedValueOnce(sessionResponse(role));
  if (response) fetcher.mockResolvedValueOnce(response);
  const session = new SessionClient(fetcher as typeof fetch);
  await session.login("user", "synthetic-only");
  return { client: new ReferenceReviseClient(session), fetcher };
}
describe("ReferenceReviseClient", () => {
  it("posts PROJECT five fields with private CSRF and unrelated current/result ETags", async () => {
    const { client, fetcher } = await setup("PROJECT_MANAGER", envelope());
    expect(await client.revise("PROJECT", root, project, input, '"v5"', "k".repeat(16))).toEqual(result);
    const [path, options] = fetcher.mock.calls[1] as [string, RequestInit];
    expect(path).toBe(`/api/v1/projects/${project}/reference-solutions/${root}:revise`);
    expect(options).toEqual(expect.objectContaining({ method: "POST", credentials: "same-origin",
      cache: "no-store", redirect: "error", headers: expect.objectContaining({
        "X-CSRF-Token": "a".repeat(64), "If-Match": '"v5"', "Idempotency-Key": "k".repeat(16) }) }));
    expect(JSON.parse(options.body as string)).toEqual(input);
  });
  it("posts GLOBAL only for DeploymentAdmin", async () => {
    const global = { ...result, scope: "GLOBAL", project_id: null };
    const { client, fetcher } = await setup("DEPLOYMENT_ADMIN", envelope(global));
    expect(await client.revise("GLOBAL", root, null, input, '"v5"', "k".repeat(16))).toEqual(global);
    expect(fetcher.mock.calls[1]?.[0]).toBe(`/api/v1/global/reference-solutions/${root}:revise`);
  });
  it("rejects invalid target, key, shape and role before POST", async () => {
    const { client, fetcher } = await setup();
    await expect(client.revise("PROJECT", root, null, input, '"v5"', "k".repeat(16)))
      .rejects.toMatchObject({ code: "REFERENCE_REVISE_INVALID" });
    await expect(client.revise("PROJECT", root, project, { ...input, extra: 1 } as ReferenceReviseInput,
      '"v5"', "k".repeat(16))).rejects.toMatchObject({ code: "REFERENCE_REVISE_INVALID" });
    await expect(client.revise("PROJECT", root, project, input, 'W/"v5"', "k".repeat(16)))
      .rejects.toMatchObject({ code: "REFERENCE_REVISE_INVALID" });
    expect(fetcher).toHaveBeenCalledTimes(1);
    const denied = await setup("CUSTOMER_MEMBER");
    await expect(denied.client.revise("PROJECT", root, project, input, '"v5"', "k".repeat(16)))
      .rejects.toMatchObject({ code: "REFERENCE_REVISE_INVALID" });
    expect(denied.fetcher).toHaveBeenCalledTimes(1);
  });
  it("does not retry uncertain network or trust malformed success", async () => {
    const network = await setup();
    network.fetcher.mockRejectedValueOnce(new TypeError("lost"));
    await expect(network.client.revise("PROJECT", root, project, input, '"v5"', "k".repeat(16)))
      .rejects.toMatchObject({ code: "REFERENCE_REVISE_UNCERTAIN", uncertain: true });
    expect(network.fetcher).toHaveBeenCalledTimes(2);
    const malformed = await setup("PROJECT_MANAGER", envelope({ ...result, extra: 1 }));
    await expect(malformed.client.revise("PROJECT", root, project, input, '"v5"', "k".repeat(16)))
      .rejects.toMatchObject({ code: "REFERENCE_REVISE_UNCERTAIN" });
  });
});
