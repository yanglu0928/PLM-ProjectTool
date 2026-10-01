import { afterEach, describe, expect, it, vi } from "vitest";

import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";
import { WorkflowStartClient, WorkflowStartError } from "./workflowStartClient";
import { parseWorkflow } from "./workflowReadClient";

const projectId = "01234567-89ab-4cde-8123-456789abcdef";
const workflowId = "11234567-89ab-4cde-8123-456789abcdef";
const stages = [
  ["HANDOVER", "HANDOVER_BASELINE", "HANDOVER_ISSUES"],
  ["SURVEY", "SURVEY_ACTUAL_SOURCES", "SURVEY_CONCLUSION"],
  ["REQUIREMENT", "REQUIREMENT_FORMAL_VERSIONS", "REQUIREMENT_ACCEPTANCE"],
  ["PROTOTYPE", "PROTOTYPE_SCOPE_DECISIONS", "PROTOTYPE_COVERAGE"],
  ["SOLUTION", "SOLUTION_APPROVED_SET", "SOLUTION_COVERAGE"],
  ["PLAN", "PLAN_APPROVED_BASELINE", "PLAN_WBS_VALIDATION"],
] as const;
function view(started = false) {
  return parseWorkflow({ workflow_id: workflowId, version: 1,
    state: started ? "ACTIVE" : "NOT_STARTED",
    current_stage: started ? "HANDOVER" : null,
    stages: stages.map(([stageKey, first, second], index) => ({
      stage_key: stageKey, order: index + 1,
      state: started && index === 0 ? "ACTIVE" : "NOT_STARTED",
      checklist_items: [first, second].map((itemKey) => ({ item_key: itemKey,
        required: true, state: "PENDING" })),
    })), etag: started ? '"v1"' : '"v0"',
  });
}
function response(data: unknown, status = 200, tag = '"v1"') {
  return new Response(JSON.stringify({ data, trace_id: projectId }), {
    status, headers: { "Content-Type": "application/json", ETag: tag },
  });
}
function failure(status: number, code: string) {
  return new Response(JSON.stringify({ error: { code, message: "private details" }, trace_id: projectId }), {
    status, headers: { "Content-Type": "application/json" },
  });
}
function client(server: Response | Error) {
  const session = new SessionClient(vi.fn() as typeof fetch);
  const post = vi.spyOn(session, "postProjectWorkflowStart");
  if (server instanceof Error) post.mockRejectedValue(server);
  else post.mockResolvedValue(server);
  return { start: new WorkflowStartClient(session), post };
}

describe("WorkflowStartClient", () => {
  afterEach(() => vi.restoreAllMocks());

  it("accepts only the original fixed first result and never marks it current", async () => {
    const first = view(true);
    const { start, post } = client(response(first));
    const receipt = await start.start(projectId, view(), "synthetic-workflow-start-0001");
    expect(receipt.first_result).toEqual(first);
    expect(receipt.is_current_state_proof).toBe(false);
    expect(Object.isFrozen(receipt)).toBe(true);
    expect(post).toHaveBeenCalledWith(projectId, '"v0"', "synthetic-workflow-start-0001");
  });

  it("rejects invalid scope, prior state or Key before POST", async () => {
    const { start, post } = client(response(view(true)));
    for (const [project, before, key] of [
      ["../other", view(), "synthetic-workflow-start-0001"],
      [projectId, view(true), "synthetic-workflow-start-0001"],
      [projectId, view(), "short"],
    ] as const) {
      await expect(start.start(project, before, key))
        .rejects.toMatchObject({ code: "WORKFLOW_START_INVALID_INPUT" });
    }
    expect(post).not.toHaveBeenCalled();
  });

  it.each([
    [401, "AUTH_SESSION_EXPIRED"], [403, "AUTH_CSRF_INVALID"],
    [403, "LICENSE_OPERATION_DENIED"], [404, "RESOURCE_NOT_FOUND"],
    [409, "PROJECT_ARCHIVED"], [409, "CONFLICT_VERSION"],
    [409, "CONFLICT_STATE"], [409, "CONFLICT_IDEMPOTENCY"],
  ])("maps safe server error %s %s", async (status, code) => {
    const { start } = client(failure(status, code));
    await expect(start.start(projectId, view(), "synthetic-workflow-start-0001"))
      .rejects.toMatchObject({ code, uncertain: false });
  });

  it("treats body/ETag/identity mismatch as uncertain, not current state", async () => {
    const original = view(true);
    for (const server of [response({ ...original, workflow_id: projectId }),
      response({ ...original, current_stage: "SURVEY" }),
      response({ ...original, etag: '"v2"' }),
      response(original, 200, '"v2"'),
      new Response("private", { status: 200 }),
      failure(503, "SYSTEM_UNAVAILABLE")]) {
      const { start } = client(server);
      await expect(start.start(projectId, view(), "synthetic-workflow-start-0001"))
        .rejects.toMatchObject({ code: "WORKFLOW_START_UNCERTAIN", uncertain: true });
    }
  });

  it("distinguishes missing current write proof from uncertain transport", async () => {
    for (const [failure, code] of [
      [new SessionClientError("AUTH_RELOGIN_REQUIRED"), "AUTH_RELOGIN_REQUIRED"],
      [new SessionClientError("AUTH_CLIENT_BUSY"), "AUTH_CLIENT_BUSY"],
      [new SessionClientError("AUTH_CLIENT_UNAVAILABLE"), "WORKFLOW_START_UNCERTAIN"],
    ] as const) {
      const { start } = client(failure);
      await expect(start.start(projectId, view(), "synthetic-workflow-start-0001"))
        .rejects.toMatchObject({ code });
    }
  });

  it("does not trust malformed input DTOs or unrelated client errors", async () => {
    const { start, post } = client(response(view(true)));
    await expect(start.start(projectId, { ...view(), stages: [] },
      "synthetic-workflow-start-0001")).rejects.toBeInstanceOf(WorkflowStartError);
    expect(post).not.toHaveBeenCalled();
  });
});
