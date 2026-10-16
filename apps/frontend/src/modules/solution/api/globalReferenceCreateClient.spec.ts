import { describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { GlobalReferenceCreateClient, type GlobalReferenceCreateInput } from "./globalReferenceCreateClient";

const actor = "01234567-89ab-4cde-8123-456789abcdef";
const document = "11234567-89ab-4cde-8123-456789abcdef";
const evidence = "21234567-89ab-4cde-8123-456789abcdef";
const root = "31234567-89ab-4cde-8123-456789abcdef";
const version = "41234567-89ab-4cde-8123-456789abcdef";
const trace = "51234567-89ab-4cde-8123-456789abcdef";
const input: GlobalReferenceCreateInput = { name: "Synthetic reference",
  document_version_ids: [document], evidence_ids: [evidence],
  source_project_class: "PLM", deidentification_class: "DEIDENTIFIED",
  applicability: { industry: "synthetic" } };
const created = { reference_solution_id: root, reference_version_id: version,
  scope: "GLOBAL", project_id: null, name: input.name, eligibility_state: "REFERENCE_ONLY",
  version_state: "DRAFT", created_by: actor, created_at: "2026-10-09T00:00:00Z", etag: '"v0"' };
function envelope(data: unknown, status = 201, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify({ data, trace_id: trace }), { status, headers: {
    "Content-Type": "application/json", "ETag": '"v0"',
    "Location": `/api/v1/global/reference-solutions/${root}`, "X-Trace-Id": trace, ...headers } });
}
function failure(code: string, status: number): Response {
  return new Response(JSON.stringify({ error: { code }, trace_id: trace }), { status,
    headers: { "Content-Type": "application/json" } });
}
function sessionResponse(role = "DEPLOYMENT_ADMIN"): Response {
  return new Response(JSON.stringify({ data: {
    user: { user_id: actor, username_display: "Synthetic admin" },
    deployment_role: role, password_change_required: false, authorized_projects: [],
    absolute_expires_at: "2030-01-11T00:00:00Z", idle_expires_at: "2030-01-10T01:00:00Z",
    csrf_token: "a".repeat(64),
  }, trace_id: trace }), { status: 200, headers: { "Content-Type": "application/json" } });
}
async function setup(response?: Response, role = "DEPLOYMENT_ADMIN") {
  const fetcher = vi.fn().mockResolvedValueOnce(sessionResponse(role));
  if (response) fetcher.mockResolvedValueOnce(response);
  const session = new SessionClient(fetcher as typeof fetch);
  await session.login("admin", "synthetic-only");
  return { client: new GlobalReferenceCreateClient(session), fetcher };
}

describe("GlobalReferenceCreateClient", () => {
  it("posts only frozen fields with private CSRF and verifies minimal 201", async () => {
    const { client, fetcher } = await setup(envelope(created));
    expect(await client.create(input, "k".repeat(16))).toEqual(created);
    const [path, options] = fetcher.mock.calls[1] as [string, RequestInit];
    expect(path).toBe("/api/v1/global/reference-solutions");
    expect(options).toEqual(expect.objectContaining({ method: "POST", credentials: "same-origin",
      cache: "no-store", redirect: "error", headers: expect.objectContaining({
        "X-CSRF-Token": "a".repeat(64), "Idempotency-Key": "k".repeat(16) }) }));
    expect(JSON.parse(options.body as string)).toEqual(input);
    expect(options.body).not.toContain("confirmation_id");
  });
  it("does not bind native fetch to SessionClient", async () => {
    let calls = 0;
    const nativeLike = function (this: unknown): Promise<Response> {
      expect(this).toBeUndefined(); calls += 1;
      return Promise.resolve(calls === 1 ? sessionResponse() : envelope(created));
    } as typeof fetch;
    const session = new SessionClient(nativeLike);
    await session.login("admin", "synthetic-only");
    expect(await new GlobalReferenceCreateClient(session).create(input, "k".repeat(16)))
      .toEqual(created);
    expect(calls).toBe(2);
  });
  it("rejects malformed inputs and non-admin before POST", async () => {
    const { client, fetcher } = await setup();
    await expect(client.create({ ...input, document_version_ids: [] }, "k".repeat(16)))
      .rejects.toMatchObject({ code: "REFERENCE_CREATE_INVALID" });
    await expect(client.create({ ...input, confirmation_id: actor } as GlobalReferenceCreateInput,
      "k".repeat(16))).rejects.toMatchObject({ code: "REFERENCE_CREATE_INVALID" });
    expect(fetcher).toHaveBeenCalledTimes(1);
    const other = await setup(undefined, "NONE");
    await expect(other.client.create(input, "k".repeat(16)))
      .rejects.toMatchObject({ code: "REFERENCE_CREATE_INVALID" });
    expect(other.fetcher).toHaveBeenCalledTimes(1);
  });
  it("surfaces known denial, treats malformed success and network loss as uncertain without retry", async () => {
    const denied = await setup(failure("RESOURCE_NOT_FOUND", 404));
    await expect(denied.client.create(input, "k".repeat(16)))
      .rejects.toMatchObject({ code: "RESOURCE_NOT_FOUND" });
    const malformed = await setup(envelope({ ...created, confirmation_id: actor }));
    await expect(malformed.client.create(input, "k".repeat(16)))
      .rejects.toMatchObject({ code: "REFERENCE_CREATE_UNCERTAIN" });
    const network = await setup();
    network.fetcher.mockRejectedValueOnce(new TypeError("network lost"));
    await expect(network.client.create(input, "k".repeat(16)))
      .rejects.toMatchObject({ code: "REFERENCE_CREATE_UNCERTAIN" });
    expect(network.fetcher).toHaveBeenCalledTimes(2);
  });
});
