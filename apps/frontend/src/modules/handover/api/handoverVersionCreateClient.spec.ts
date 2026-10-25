import { describe, expect, it, vi } from "vitest";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { HandoverVersionCreateClient, HandoverVersionCreateError,
  normalizeHandoverVersionItems, type HandoverVersionCreateInput } from "./handoverVersionCreateClient";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const document = "11234567-89ab-4cde-8123-456789abcdef";
const documentVersion = "21234567-89ab-4cde-8123-456789abcdef";
const analysis = "31234567-89ab-4cde-8123-456789abcdef";
const itemId = "41234567-89ab-4cde-8123-456789abcdef";
const evidence = "51234567-89ab-4cde-8123-456789abcdef";
const baseline = "61234567-89ab-4cde-8123-456789abcdef";
const baselineVersion = "71234567-89ab-4cde-8123-456789abcdef";
const version = "81234567-89ab-4cde-8123-456789abcdef";
const actor = "91234567-89ab-4cde-8123-456789abcdef";
const trace = "a1234567-89ab-4cde-8123-456789abcdef";
const token = "a".repeat(64);
const path = `/api/v1/projects/${project}/handover-analyses/${analysis}/versions`;
const key = "handover-version-key-001";
const input: HandoverVersionCreateInput = {
  source_documents: [{ document_id: document, document_version_id: documentVersion }],
  capability_baseline_id: baseline, capability_baseline_version_id: baselineVersion,
  items: [{ analysis_item_id: itemId, item_type: "GAP", title: "接口差异候选",
    statement: "经人工核对的合成差异", impact: "需评估数据映射", severity: "MEDIUM",
    priority: "HIGH", recommendation: null, confirmation_question: null,
    required_input_spec: {}, source_missing: false, evidence_refs: [evidence],
    capability_refs: [], options: [] }], ai_task_refs: [],
};
function json(data: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify({ data, trace_id: trace }), { status,
    headers: { "Content-Type": "application/json", ...headers } });
}
function failure(status: number, code: string): Response {
  return new Response(JSON.stringify({ error: { code, message: "private" }, trace_id: trace }),
    { status, headers: { "Content-Type": "application/json" } });
}
function receipt(overrides: Record<string, unknown> = {}) {
  return { handover_analysis_version_id: version, handover_analysis_id: analysis, project_id: project,
    version_no: 1, state: "DRAFT", source_set_ref: `sha256:${"b".repeat(64)}`,
    capability_baseline_id: baseline, capability_baseline_version_ref: baselineVersion,
    content_fingerprint: "a".repeat(64), supersedes_version_ref: null,
    created_at: "2026-10-25T12:00:00Z", analysis_etag: '"v1"', ...overrides };
}
async function fixture(result: Response | Error, role = "PROJECT_MANAGER") {
  const sessionView = { user: { user_id: actor, username_display: "合成负责人" },
    deployment_role: "NONE", password_change_required: false,
    authorized_projects: [{ project_id: project, name: "合成项目", role }],
    absolute_expires_at: "2030-01-01T12:00:00Z", idle_expires_at: "2030-01-01T11:00:00Z",
    csrf_token: token };
  const fetcher = vi.fn().mockResolvedValueOnce(json(sessionView));
  if (result instanceof Error) fetcher.mockRejectedValueOnce(result);
  else fetcher.mockResolvedValueOnce(result);
  const session = new SessionClient(fetcher as typeof fetch);
  await session.login("synthetic", "synthetic-only");
  return { client: new HandoverVersionCreateClient(session), fetcher };
}

describe("HandoverVersionCreateClient", () => {
  it("posts only fixed source and user-confirmed item with private CSRF, Key and ETag", async () => {
    const { client, fetcher } = await fixture(json(receipt(), 201,
      { ETag: '"v1"', Location: `${path}/${version}`, "Cache-Control": "no-store" }));
    await expect(client.create(project, analysis, '"v0"', input, key))
      .resolves.toMatchObject({ handover_analysis_version_id: version, state: "DRAFT" });
    expect(fetcher.mock.calls[1]).toEqual([path, expect.objectContaining({
      method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error",
      body: JSON.stringify(input), headers: { Accept: "application/json", "Content-Type": "application/json",
        "X-CSRF-Token": token, "Idempotency-Key": key, "If-Match": '"v0"' },
    })]);
  });

  it("rejects malformed and ungrounded issue content before network mutation", async () => {
    const { client, fetcher } = await fixture(json(receipt(), 201,
      { ETag: '"v1"', Location: `${path}/${version}`, "Cache-Control": "no-store" }));
    const missing = { ...input.items[0], evidence_refs: [] };
    expect(() => normalizeHandoverVersionItems([missing])).toThrow(HandoverVersionCreateError);
    await expect(client.create(project, analysis, '"v0"', { ...input, items: [missing] }, key))
      .rejects.toMatchObject({ code: "HANDOVER_VERSION_INVALID" });
    await expect(client.create(project, analysis, '"v0"', { ...input, source_documents: [] }, key))
      .rejects.toMatchObject({ code: "HANDOVER_VERSION_INVALID" });
    await expect(client.create(project, analysis, "invalid", input, key))
      .rejects.toMatchObject({ code: "HANDOVER_VERSION_INVALID" });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("requires authorized project role and maps source conflict without new operation", async () => {
    const outsider = await fixture(failure(422, "HANDOVER_SOURCE_REQUIRED"), "CUSTOMER_MEMBER");
    await expect(outsider.client.create(project, analysis, '"v0"', input, key))
      .rejects.toMatchObject({ code: "RESOURCE_NOT_FOUND" });
    expect(outsider.fetcher).toHaveBeenCalledTimes(1);
    const mismatch = await fixture(failure(422, "HANDOVER_SOURCE_REQUIRED"));
    await expect(mismatch.client.create(project, analysis, '"v0"', input, key))
      .rejects.toMatchObject({ code: "HANDOVER_SOURCE_REQUIRED", uncertain: false });
  });

  it("keeps uncertainty when transport fails or receipt is inconsistent", async () => {
    const timedOut = await fixture(new Error("private transport"));
    await expect(timedOut.client.create(project, analysis, '"v0"', input, key))
      .rejects.toMatchObject({ code: "HANDOVER_VERSION_UNCERTAIN", uncertain: true });
    const mismatched = await fixture(json(receipt({ capability_baseline_version_ref: actor }), 201,
      { ETag: '"v1"', Location: `${path}/${version}`, "Cache-Control": "no-store" }));
    await expect(mismatched.client.create(project, analysis, '"v0"', input, key))
      .rejects.toMatchObject({ code: "HANDOVER_VERSION_UNCERTAIN", uncertain: true });
  });
});
