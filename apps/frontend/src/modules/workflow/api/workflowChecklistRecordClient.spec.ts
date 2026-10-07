import { afterEach, describe, expect, it, vi } from "vitest";

import { SessionClient, SessionClientError } from "@/modules/auth/api/sessionClient";
import { parseWorkflow } from "./workflowReadClient";
import {
  WorkflowChecklistRecordClient, WorkflowChecklistRecordError,
  type WorkflowChecklistRecordInput,
} from "./workflowChecklistRecordClient";

const projectId = "01234567-89ab-4cde-8123-456789abcdef";
const workflowId = "11234567-89ab-4cde-8123-456789abcdef";
const recordId = "21234567-89ab-4cde-8123-456789abcdef";
const evidenceId = "31234567-89ab-4cde-8123-456789abcdef";
const evidenceId2 = "41234567-89ab-4cde-8123-456789abcdef";
const reviewId = "51234567-89ab-4cde-8123-456789abcdef";
const stages = [
  ["HANDOVER", "HANDOVER_BASELINE", "HANDOVER_ISSUES"],
  ["SURVEY", "SURVEY_ACTUAL_SOURCES", "SURVEY_CONCLUSION"],
  ["REQUIREMENT", "REQUIREMENT_FORMAL_VERSIONS", "REQUIREMENT_ACCEPTANCE"],
  ["PROTOTYPE", "PROTOTYPE_SCOPE_DECISIONS", "PROTOTYPE_COVERAGE"],
  ["SOLUTION", "SOLUTION_APPROVED_SET", "SOLUTION_COVERAGE"],
  ["PLAN", "PLAN_APPROVED_BASELINE", "PLAN_WBS_VALIDATION"],
] as const;

function workflow(etag = '"v4"') {
  return parseWorkflow({ workflow_id: workflowId, version: 1, state: "ACTIVE", current_stage: "HANDOVER",
    stages: stages.map(([stageKey, first, second], index) => ({ stage_key: stageKey, order: index + 1,
      state: index === 0 ? "ACTIVE" : "NOT_STARTED",
      checklist_items: [first, second].map((itemKey) => ({ item_key: itemKey,
        required: true, state: "PENDING" })),
    })), etag,
  });
}
function surveyWorkflow(etag = '"v6"') {
  return parseWorkflow({ workflow_id: workflowId, version: 1, state: "ACTIVE",
    current_stage: "SURVEY", stages: stages.map(([stageKey, first, second], index) => ({
      stage_key: stageKey, order: index + 1,
      state: index === 0 ? "COMPLETED" : index === 1 ? "ACTIVE" : "NOT_STARTED",
      checklist_items: [first, second].map((itemKey) => ({ item_key: itemKey,
        required: true, state: index === 0 ? "PASS" : "PENDING" })),
    })), etag });
}
function record(result: "PASS" | "FAIL" = "PASS", extra: Record<string, unknown> = {}) {
  return { record_id: recordId, workflow_id: workflowId, project_id: projectId,
    definition_version: 1, stage_key: "HANDOVER", item_key: "HANDOVER_BASELINE", result,
    item_version: 1, recorded_workflow_version: 5, current_workflow_version: 5,
    supersedes_record_id: null,
    evidence_refs: result === "PASS" ? [evidenceId, evidenceId2] : [],
    review_round_refs: result === "PASS" ? [reviewId] : [], exception_refs: [],
    reason: result === "PASS" ? "Approved baseline" : "Missing approval",
    impact: result === "PASS" ? "Handover may proceed" : null,
    occurred_at: "2026-10-06T00:00:00Z", etag: '"v5"', ...extra };
}
function response(data: unknown, status = 200, etag = '"v5"') {
  return new Response(JSON.stringify({ data, trace_id: projectId }), {
    status, headers: { "Content-Type": "application/json", ETag: etag },
  });
}
function failure(status: number, code: string) {
  return new Response(JSON.stringify({ error: { code, message: "private details" }, trace_id: projectId }), {
    status, headers: { "Content-Type": "application/json" },
  });
}
function input(result: "PASS" | "FAIL" = "PASS"): WorkflowChecklistRecordInput {
  return { before: workflow(), item_key: "HANDOVER_BASELINE", result,
    evidence_refs: result === "PASS" ? [evidenceId2, evidenceId] : [],
    reason: result === "PASS" ? "  Approved baseline  " : "Missing approval",
    impact: result === "PASS" ? "Handover may proceed" : null,
    idempotency_key: "synthetic-checklist-record-0001" };
}
function surveyInput(): WorkflowChecklistRecordInput {
  return { before: surveyWorkflow(), item_key: "SURVEY_CONCLUSION", result: "PASS",
    evidence_refs: [evidenceId], reason: null, impact: null,
    idempotency_key: "synthetic-survey-record-0001" };
}
function client(server: Response | Error) {
  const session = new SessionClient(vi.fn() as typeof fetch);
  const post = vi.spyOn(session, "postProjectWorkflowChecklistRecord");
  if (server instanceof Error) post.mockRejectedValue(server);
  else post.mockResolvedValue(server);
  return { records: new WorkflowChecklistRecordClient(session), post };
}

describe("WorkflowChecklistRecordClient", () => {
  afterEach(() => vi.restoreAllMocks());

  it("accepts an exact PASS first receipt and never marks it as current proof", async () => {
    const { records, post } = client(response(record()));
    const receipt = await records.record(projectId, input());
    expect(receipt.first_record).toEqual(record());
    expect(receipt.is_current_state_proof).toBe(false);
    expect(Object.isFrozen(receipt)).toBe(true);
    expect(Object.isFrozen(receipt.first_record)).toBe(true);
    expect(Object.isFrozen(receipt.first_record.evidence_refs)).toBe(true);
    expect(post).toHaveBeenCalledWith(projectId, "HANDOVER_BASELINE",
      JSON.stringify({ result: "PASS", reason: "Approved baseline", impact: "Handover may proceed",
        evidence_refs: [evidenceId2, evidenceId], exception_refs: [] }),
      '"v4"', "synthetic-checklist-record-0001");
  });

  it("sends FAIL without fabricated Evidence, Review or exception refs", async () => {
    const { records, post } = client(response(record("FAIL")));
    const receipt = await records.record(projectId, input("FAIL"));
    expect(receipt.first_record.result).toBe("FAIL");
    expect(receipt.first_record.evidence_refs).toEqual([]);
    expect(receipt.first_record.review_round_refs).toEqual([]);
    expect(post.mock.calls[0][2]).toBe(JSON.stringify({ result: "FAIL", reason: "Missing approval",
      impact: null, evidence_refs: [], exception_refs: [] }));
  });

  it("records Survey PASS only against the matching current Survey stage", async () => {
    const surveyRecord = record("PASS", { stage_key: "SURVEY",
      item_key: "SURVEY_CONCLUSION", recorded_workflow_version: 7,
      current_workflow_version: 7, evidence_refs: [evidenceId], reason: null,
      impact: null, etag: '"v7"' });
    const { records, post } = client(response(surveyRecord, 200, '"v7"'));
    const receipt = await records.record(projectId, surveyInput());
    expect(receipt.first_record).toMatchObject({ stage_key: "SURVEY",
      item_key: "SURVEY_CONCLUSION", recorded_workflow_version: 7 });
    expect(post).toHaveBeenCalledWith(projectId, "SURVEY_CONCLUSION",
      JSON.stringify({ result: "PASS", reason: null, impact: null,
        evidence_refs: [evidenceId], exception_refs: [] }),
      '"v6"', "synthetic-survey-record-0001");
  });

  it("rejects a cross-stage Checklist item before transport", async () => {
    const { records, post } = client(response(record()));
    await expect(records.record(projectId, { ...input(), item_key: "SURVEY_CONCLUSION" }))
      .rejects.toMatchObject({ code: "WORKFLOW_CHECKLIST_INVALID_INPUT" });
    expect(post).not.toHaveBeenCalled();
  });

  it("rejects unsafe scope, state, result inputs and unavailable WAIVED before transport", async () => {
    const { records, post } = client(response(record()));
    const invalid = [
      ["../other", input()],
      [projectId, { ...input(), before: parseWorkflow({ ...workflow(), state: "NOT_STARTED",
        current_stage: null, stages: workflow().stages.map((stage) => ({ ...stage, state: "NOT_STARTED" })) }) }],
      [projectId, { ...input(), evidence_refs: [] }],
      [projectId, { ...input("FAIL"), evidence_refs: [evidenceId] }],
      [projectId, { ...input(), evidence_refs: [evidenceId, evidenceId] }],
      [projectId, { ...input(), reason: "\u0000" }],
      [projectId, { ...input(), idempotency_key: "short" }],
      [projectId, { ...input(), result: "WAIVED" }],
    ] as const;
    for (const [project, value] of invalid) {
      await expect(records.record(project, value as WorkflowChecklistRecordInput))
        .rejects.toMatchObject({ code: "WORKFLOW_CHECKLIST_INVALID_INPUT", uncertain: false });
    }
    expect(post).not.toHaveBeenCalled();
  });

  it.each([
    [401, "AUTH_SESSION_EXPIRED"], [403, "AUTH_CSRF_INVALID"],
    [403, "LICENSE_OPERATION_DENIED"], [404, "RESOURCE_NOT_FOUND"],
    [409, "PROJECT_ARCHIVED"], [409, "CONFLICT_VERSION"],
    [409, "CONFLICT_STATE"], [409, "CONFLICT_IDEMPOTENCY"],
    [409, "WORKFLOW_GATE_NOT_SATISFIED"],
  ])("maps safe server error %s %s", async (status, code) => {
    const { records } = client(failure(status, code));
    await expect(records.record(projectId, input()))
      .rejects.toMatchObject({ code, uncertain: false });
  });

  it.each([[400, "REQUEST_MALFORMED"], [422, "VALIDATION_FAILED"],
    [428, "CONFLICT_VERSION_REQUIRED"]])("maps malformed command %s %s to invalid input", async (status, code) => {
    const { records } = client(failure(status, code));
    await expect(records.record(projectId, input()))
      .rejects.toMatchObject({ code: "WORKFLOW_CHECKLIST_INVALID_INPUT", uncertain: false });
  });

  it("treats malformed, mismatched or non-current response data as uncertain", async () => {
    for (const server of [
      response({ ...record(), project_id: workflowId }),
      response({ ...record(), workflow_id: projectId }),
      response({ ...record(), item_key: "HANDOVER_ISSUES" }),
      response({ ...record(), recorded_workflow_version: 6, current_workflow_version: 6, etag: '"v6"' }, 200, '"v6"'),
      response({ ...record(), evidence_refs: [evidenceId] }),
      response({ ...record(), review_round_refs: [] }),
      response({ ...record(), exception_refs: [reviewId] }),
      response({ ...record(), extra: true }),
      response(record(), 200, '"v6"'),
      new Response("private", { status: 200 }),
      failure(503, "SYSTEM_UNAVAILABLE"),
    ]) {
      const { records } = client(server);
      await expect(records.record(projectId, input()))
        .rejects.toMatchObject({ code: "WORKFLOW_CHECKLIST_UNCERTAIN", uncertain: true });
    }
  });

  it("preserves login and busy errors but treats unknown transport as uncertain", async () => {
    for (const [server, code] of [
      [new SessionClientError("AUTH_RELOGIN_REQUIRED"), "AUTH_RELOGIN_REQUIRED"],
      [new SessionClientError("AUTH_CLIENT_BUSY"), "AUTH_CLIENT_BUSY"],
      [new SessionClientError("AUTH_CLIENT_UNAVAILABLE"), "WORKFLOW_CHECKLIST_UNCERTAIN"],
    ] as const) {
      const { records } = client(server);
      await expect(records.record(projectId, input())).rejects.toMatchObject({ code });
    }
  });

  it("rejects non-Session owners", () => {
    expect(() => new WorkflowChecklistRecordClient({} as SessionClient))
      .toThrow(WorkflowChecklistRecordError);
  });
});
