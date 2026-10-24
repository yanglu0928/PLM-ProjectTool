import { describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import type { ReferenceCurrent } from "./referenceReadClient";
import type { GlobalReferenceCurrent } from "./globalReferenceReadClient";
import { ReferenceEligibilityClient } from "./referenceEligibilityClient";

const actor = "01234567-89ab-4cde-8123-456789abcdef";
const project = "11234567-89ab-4cde-8123-456789abcdef";
const root = "21234567-89ab-4cde-8123-456789abcdef";
const version = "31234567-89ab-4cde-8123-456789abcdef";
const event = "41234567-89ab-4cde-8123-456789abcdef";
const trace = "51234567-89ab-4cde-8123-456789abcdef";
const current = { reference_solution_id: root, reference_version_id: version,
  scope: "PROJECT", project_id: project, eligibility_state: "REFERENCE_ONLY", etag: '"v0"' } as ReferenceCurrent;
const receipt = { eligibility_event_id: event, reference_solution_id: root,
  reference_version_id: version, scope: "PROJECT", project_id: project,
  eligibility_state: "ELIGIBLE", eligibility_reason: "人工核对当前来源", etag: '"v1"' };
function login(role: string): Response {
  return new Response(JSON.stringify({ data: {
    user: { user_id: actor, username_display: "Synthetic user" },
    deployment_role: role === "DEPLOYMENT_ADMIN" ? role : "NONE",
    password_change_required: false,
    authorized_projects: role === "DEPLOYMENT_ADMIN" ? [] : [{ project_id: project, name: "Synthetic", role }],
    absolute_expires_at: "2030-01-11T00:00:00Z", idle_expires_at: "2030-01-10T01:00:00Z",
    csrf_token: "a".repeat(64),
  }, trace_id: trace }), { status: 200, headers: { "Content-Type": "application/json" } });
}
function envelope(data: unknown = receipt, status = 200, etag = '"v1"'): Response {
  return new Response(JSON.stringify({ data, trace_id: trace }), { status, headers: {
    "Content-Type": "application/json", "Cache-Control": "no-store", "X-Trace-Id": trace, ETag: etag } });
}
async function setup(role = "PROJECT_MANAGER", response?: Response) {
  const fetcher = vi.fn().mockResolvedValueOnce(login(role));
  if (response) fetcher.mockResolvedValueOnce(response);
  const session = new SessionClient(fetcher as typeof fetch);
  await session.login("user", "synthetic-only");
  return { client: new ReferenceEligibilityClient(session), fetcher };
}
describe("ReferenceEligibilityClient", () => {
  it("posts PROJECT decision with private CSRF, strong lock and immutable receipt", async () => {
    const { client, fetcher } = await setup("PROJECT_MANAGER", envelope());
    expect(await client.set(current, "ELIGIBLE", "人工核对当前来源", "k".repeat(16))).toEqual(receipt);
    const [path, options] = fetcher.mock.calls[1] as [string, RequestInit];
    expect(path).toBe(`/api/v1/projects/${project}/reference-solutions/${root}:set-eligibility`);
    expect(options).toEqual(expect.objectContaining({ method: "POST", credentials: "same-origin",
      cache: "no-store", redirect: "error", headers: expect.objectContaining({
        "X-CSRF-Token": "a".repeat(64), "If-Match": '"v0"', "Idempotency-Key": "k".repeat(16) }) }));
    expect(JSON.parse(options.body as string)).toEqual({ eligibility_state: "ELIGIBLE", reason: "人工核对当前来源" });
  });
  it("posts GLOBAL only for DeploymentAdmin", async () => {
    const global = { ...current, scope: "GLOBAL", project_id: null } as GlobalReferenceCurrent;
    const { client, fetcher } = await setup("DEPLOYMENT_ADMIN", envelope({ ...receipt,
      scope: "GLOBAL", project_id: null }));
    expect(await client.set(global, "ELIGIBLE", "人工核对当前来源", "k".repeat(16)))
      .toMatchObject({ scope: "GLOBAL", project_id: null });
    expect(fetcher.mock.calls[1]?.[0]).toBe(`/api/v1/global/reference-solutions/${root}:set-eligibility`);
  });
  it("rejects wrong role, terminal state, invalid reason and key before POST", async () => {
    const { client, fetcher } = await setup();
    for (const [state, reason, key] of [
      ["REVOKED", "已撤销", "k".repeat(16)],
      ["REFERENCE_ONLY", "", "k".repeat(16)],
      ["REFERENCE_ONLY", "甲".repeat(2001), "k".repeat(16)],
      ["REFERENCE_ONLY", "有效理由", "short"],
    ]) await expect(client.set({ ...current, eligibility_state: state } as ReferenceCurrent,
      "ELIGIBLE", reason, key)).rejects.toMatchObject({ code: "REFERENCE_ELIGIBILITY_INVALID" });
    expect(fetcher).toHaveBeenCalledTimes(1);
    const member = await setup("IMPLEMENTATION_MEMBER");
    await expect(member.client.set(current, "ELIGIBLE", "已核对", "k".repeat(16)))
      .rejects.toMatchObject({ code: "REFERENCE_ELIGIBILITY_INVALID" });
    expect(member.fetcher).toHaveBeenCalledTimes(1);
  });
  it("does not retry uncertain network, malformed receipt or stale version", async () => {
    const network = await setup(); network.fetcher.mockRejectedValueOnce(new TypeError("lost"));
    await expect(network.client.set(current, "ELIGIBLE", "人工核对当前来源", "k".repeat(16)))
      .rejects.toMatchObject({ code: "REFERENCE_ELIGIBILITY_UNCERTAIN", uncertain: true });
    expect(network.fetcher).toHaveBeenCalledTimes(2);
    const mismatch = await setup("PROJECT_MANAGER", envelope({ ...receipt, reference_version_id: actor }));
    await expect(mismatch.client.set(current, "ELIGIBLE", "人工核对当前来源", "k".repeat(16)))
      .rejects.toMatchObject({ code: "REFERENCE_ELIGIBILITY_UNCERTAIN" });
    const stale = await setup("PROJECT_MANAGER", envelope({ ...receipt, etag: '"v2"' }, 200, '"v2"'));
    await expect(stale.client.set(current, "ELIGIBLE", "人工核对当前来源", "k".repeat(16)))
      .rejects.toMatchObject({ code: "REFERENCE_ELIGIBILITY_UNCERTAIN" });
  });
});
