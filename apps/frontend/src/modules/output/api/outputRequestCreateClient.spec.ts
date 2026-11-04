import { describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { OutputRequestCreateClient, OutputRequestCreateError } from "./outputRequestCreateClient";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const version = "11234567-89ab-4cde-8123-456789abcdef";
const request = "21234567-89ab-4cde-8123-456789abcdef";
const job = "31234567-89ab-4cde-8123-456789abcdef";
const trace = "41234567-89ab-4cde-8123-456789abcdef";
function json(data: unknown, status = 200) {
  return new Response(JSON.stringify({ data, trace_id: trace }),
    { status, headers: { "Content-Type": "application/json" } });
}
async function authorized(role = "PROJECT_MANAGER") {
  const fetcher = vi.fn().mockResolvedValueOnce(json({ user: { user_id: project, username_display: "合成用户" },
    deployment_role: "NONE", password_change_required: false,
    authorized_projects: [{ project_id: project, name: "合成项目", role }],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: "a".repeat(64) }));
  const session = new SessionClient(fetcher as typeof fetch); await session.login("user", "synthetic-only");
  return { session, fetcher };
}
describe("OutputRequestCreateClient", () => {
  it("posts only the fixed DOCX policy and returns a minimal accepted receipt", async () => {
    const { session, fetcher } = await authorized();
    const key = "synthetic-output-request-0001";
    const response = json({ output_request_id: request, job_id: job, state: "QUEUED" }, 202);
    fetcher.mockResolvedValueOnce(response);
    const client = new OutputRequestCreateClient(session);
    await expect(client.create(project, version, key)).resolves.toEqual({ output_request_id: request, state: "QUEUED" });
    const [url, options] = fetcher.mock.calls[1]!;
    expect(url).toBe("/api/v1/projects/" + project + "/output-requests");
    expect(JSON.parse((options as RequestInit).body as string)).toEqual({ output_type: "DOCX",
      template_version_ref: "a1272ce0-01f0-5e6c-9706-000000000001", source_version_refs: [version],
      output_policy_ref: "output.policy.requirement-docx.v1", plugin_operation: "word.generate" });
    expect((options as RequestInit).headers).toMatchObject({ "X-CSRF-Token": "a".repeat(64), "Idempotency-Key": key });
  });
  it("rejects callers outside the create role before any POST", async () => {
    const { session, fetcher } = await authorized("CUSTOMER_MEMBER");
    const client = new OutputRequestCreateClient(session);
    await expect(client.create(project, version, "synthetic-output-request-0001"))
      .rejects.toMatchObject({ code: "OUTPUT_CREATE_INVALID" });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it("maps safe server rejection and treats an unknown outcome as uncertain", async () => {
    const { session, fetcher } = await authorized();
    const client = new OutputRequestCreateClient(session);
    fetcher.mockResolvedValueOnce(new Response(JSON.stringify({ error: { code: "LICENSE_OPERATION_DENIED" }, trace_id: trace }),
      { status: 403, headers: { "Content-Type": "application/json" } }));
    await expect(client.create(project, version, "synthetic-output-request-0001"))
      .rejects.toMatchObject({ code: "LICENSE_OPERATION_DENIED" });
    fetcher.mockRejectedValueOnce(new Error("network interrupted"));
    await expect(client.create(project, version, "synthetic-output-request-0002"))
      .rejects.toMatchObject({ code: "OUTPUT_CREATE_UNCERTAIN", uncertain: true });
  });
});
