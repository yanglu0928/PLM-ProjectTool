import { afterEach, describe, expect, it, vi } from "vitest";

import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";
import { parseWorkflow } from "./workflowReadClient";
import { WorkflowTransitionClient, WorkflowTransitionError,
  type WorkflowTransitionInput } from "./workflowTransitionClient";

const projectId = "01234567-89ab-4cde-8123-456789abcdef";
const workflowId = "11234567-89ab-4cde-8123-456789abcdef";
const transitionId = "21234567-89ab-4cde-8123-456789abcdef";
const stages = [
  ["HANDOVER", "HANDOVER_BASELINE", "HANDOVER_ISSUES"],
  ["SURVEY", "SURVEY_ACTUAL_SOURCES", "SURVEY_CONCLUSION"],
  ["REQUIREMENT", "REQUIREMENT_FORMAL_VERSIONS", "REQUIREMENT_ACCEPTANCE"],
  ["PROTOTYPE", "PROTOTYPE_SCOPE_DECISIONS", "PROTOTYPE_COVERAGE"],
  ["SOLUTION", "SOLUTION_APPROVED_SET", "SOLUTION_COVERAGE"],
  ["PLAN", "PLAN_APPROVED_BASELINE", "PLAN_WBS_VALIDATION"],
] as const;

function workflow(etag = '"v3"') {
  return parseWorkflow({ workflow_id: workflowId, version: 1, state: "ACTIVE",
    current_stage: "HANDOVER", stages: stages.map(([stageKey, first, second], index) => ({
      stage_key: stageKey, order: index + 1, state: index === 0 ? "ACTIVE" : "NOT_STARTED",
      checklist_items: [first, second].map((itemKey) => ({ item_key: itemKey,
        required: true, state: index === 0 ? "PASS" : "PENDING" })),
    })), etag });
}
function transition(extra: Record<string, unknown> = {}) {
  return { stage_transition_id: transitionId, workflow_id: workflowId, project_id: projectId,
    definition_version: 1, from_stage: "HANDOVER", to_stage: "SURVEY",
    before_workflow_version: 3, transitioned_workflow_version: 4,
    current_workflow_version: 4, reason: "Handover evidence accepted",
    occurred_at: "2026-10-06T02:00:00Z", etag: '"v4"', ...extra };
}
function response(data: unknown, status = 200, etag = '"v4"') {
  return new Response(JSON.stringify({ data, trace_id: projectId }), {
    status, headers: { "Content-Type": "application/json", ETag: etag },
  });
}
function failure(status: number, code: string) {
  return new Response(JSON.stringify({ error: { code, message: "private" }, trace_id: projectId }), {
    status, headers: { "Content-Type": "application/json" },
  });
}
function input(): WorkflowTransitionInput {
  return { before: workflow(), reason: "  Handover evidence accepted  ",
    idempotency_key: "synthetic-transition-key-0001" };
}
function client(server: Response | Error) {
  const session = new SessionClient(vi.fn() as typeof fetch);
  const post = vi.spyOn(session, "postProjectWorkflowTransition");
  if (server instanceof Error) post.mockRejectedValue(server);
  else post.mockResolvedValue(server);
  return { transitions: new WorkflowTransitionClient(session), post };
}

describe("WorkflowTransitionClient", () => {
  afterEach(() => vi.restoreAllMocks());

  it("sends only target, normalized reason and an empty server-owned gate list", async () => {
    const { transitions, post } = client(response(transition()));
    const receipt = await transitions.transition(projectId, input());
    expect(receipt.first_transition).toEqual(transition());
    expect(receipt.is_current_state_proof).toBe(false);
    expect(Object.isFrozen(receipt)).toBe(true);
    expect(Object.isFrozen(receipt.first_transition)).toBe(true);
    expect(post).toHaveBeenCalledWith(projectId, JSON.stringify({ target_stage_key: "SURVEY",
      reason: "Handover evidence accepted", gate_snapshot_refs: [] }),
      '"v3"', "synthetic-transition-key-0001");
    expect(JSON.stringify(post.mock.calls[0])).not.toContain(transitionId);
  });

  it("rejects unsafe scope, state, checklist, reason and key before transport", async () => {
    const { transitions, post } = client(response(transition()));
    const invalid = [
      ["../other", input()],
      [projectId, { ...input(), reason: " " }],
      [projectId, { ...input(), reason: "x".repeat(2001) }],
      [projectId, { ...input(), idempotency_key: "short" }],
      [projectId, { ...input(), before: parseWorkflow({ ...workflow(),
        stages: workflow().stages.map((stage, index) => index === 0 ? { ...stage,
          checklist_items: stage.checklist_items.map((item, itemIndex) => itemIndex === 0
            ? { ...item, state: "FAIL" } : item) } : stage) }) }],
    ] as const;
    for (const [project, value] of invalid) {
      await expect(transitions.transition(project, value as WorkflowTransitionInput))
        .rejects.toMatchObject({ code: "WORKFLOW_TRANSITION_INVALID_INPUT", uncertain: false });
    }
    expect(post).not.toHaveBeenCalled();
  });

  it.each([
    [401, "AUTH_SESSION_EXPIRED"], [403, "AUTH_CSRF_INVALID"],
    [403, "LICENSE_OPERATION_DENIED"], [404, "RESOURCE_NOT_FOUND"],
    [409, "PROJECT_ARCHIVED"], [409, "CONFLICT_VERSION"],
    [409, "CONFLICT_STATE"], [409, "CONFLICT_IDEMPOTENCY"],
    [409, "WORKFLOW_GATE_NOT_SATISFIED"], [409, "WORKFLOW_TRANSITION_INVALID"],
  ])("maps safe server error %s %s", async (status, code) => {
    const { transitions } = client(failure(status, code));
    await expect(transitions.transition(projectId, input()))
      .rejects.toMatchObject({ code, uncertain: false });
  });

  it.each([[400, "REQUEST_MALFORMED"], [422, "VALIDATION_FAILED"],
    [428, "CONFLICT_VERSION_REQUIRED"]])("maps malformed %s %s to safe input error", async (status, code) => {
    const { transitions } = client(failure(status, code));
    await expect(transitions.transition(projectId, input()))
      .rejects.toMatchObject({ code: "WORKFLOW_TRANSITION_INVALID_INPUT", uncertain: false });
  });

  it("treats transport and inconsistent responses as uncertain", async () => {
    const cases: (Response | Error)[] = [
      new SessionClientError("AUTH_CLIENT_UNAVAILABLE"),
      response({ ...transition(), extra: true }),
      response(transition({ workflow_id: projectId })),
      response(transition({ current_workflow_version: 5, etag: '"v5"' }), 200, '"v5"'),
      response(transition({ reason: "different" })),
      new Response("{}", { status: 200, headers: { "Content-Type": "text/plain" } }),
    ];
    for (const server of cases) {
      const { transitions } = client(server);
      await expect(transitions.transition(projectId, input()))
        .rejects.toMatchObject({ code: "WORKFLOW_TRANSITION_UNCERTAIN", uncertain: true });
      vi.restoreAllMocks();
    }
  });
});
