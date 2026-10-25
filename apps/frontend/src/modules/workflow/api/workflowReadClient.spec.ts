import { afterEach, describe, expect, it, vi } from "vitest";

import { WorkflowReadClient, WorkflowReadError, parseWorkflow } from "./workflowReadClient";

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
function snapshot(state: "NOT_STARTED" | "ACTIVE" | "COMPLETED" = "NOT_STARTED") {
  return {
    workflow_id: workflowId, version: 1, state,
    current_stage: state === "NOT_STARTED" ? null : state === "ACTIVE" ? "HANDOVER" : "PLAN",
    stages: stages.map(([stageKey, first, second], index) => ({
      stage_key: stageKey, order: index + 1,
      state: state === "NOT_STARTED" ? "NOT_STARTED"
        : state === "COMPLETED" ? "COMPLETED" : index === 0 ? "ACTIVE" : "NOT_STARTED",
      checklist_items: [first, second].map((key) => ({ item_key: key, required: true, state: "PENDING" })),
    })),
    etag: state === "NOT_STARTED" ? '"v0"' : '"v1"',
  };
}
function response(data: unknown, status = 200, tag = '"v0"') {
  return new Response(JSON.stringify({ data, trace_id: projectId }), {
    status, headers: { "Content-Type": "application/json", ETag: tag },
  });
}
function failure(status: number, code: string) {
  return new Response(JSON.stringify({ error: { code, message: "private details" }, trace_id: projectId }), {
    status, headers: { "Content-Type": "application/json" },
  });
}

describe("WorkflowReadClient", () => {
  afterEach(() => vi.restoreAllMocks());

  it("sends a same-origin no-store GET and accepts fixed immutable V1 initial view", async () => {
    const fetcher = vi.fn().mockResolvedValue(response(snapshot()));
    const view = await new WorkflowReadClient(fetcher as typeof fetch).get(projectId);
    expect(view.workflow_id).toBe(workflowId);
    expect(view.current_stage).toBeNull();
    expect(view.stages).toHaveLength(6);
    expect(view.stages.flatMap((stage) => stage.checklist_items)).toHaveLength(12);
    expect(Object.isFrozen(view)).toBe(true);
    expect(Object.isFrozen(view.stages[0]?.checklist_items)).toBe(true);
    expect(fetcher).toHaveBeenCalledWith(`/api/v1/projects/${projectId}/workflow`,
      expect.objectContaining({ method: "GET", credentials: "same-origin", cache: "no-store",
        redirect: "error" }));
  });

  it("accepts ACTIVE and completed fixed stage structures, not an approval inference", async () => {
    expect(parseWorkflow(snapshot("ACTIVE")).current_stage).toBe("HANDOVER");
    expect(parseWorkflow(snapshot("COMPLETED")).current_stage).toBe("PLAN");
  });

  it("rejects unsafe project IDs before transport", async () => {
    const fetcher = vi.fn();
    await expect(new WorkflowReadClient(fetcher as typeof fetch).get("../other"))
      .rejects.toMatchObject({ code: "WORKFLOW_INVALID_PROJECT" });
    expect(fetcher).not.toHaveBeenCalled();
  });

  it.each([
    [401, "AUTH_SESSION_EXPIRED"], [403, "LICENSE_OPERATION_DENIED"],
    [404, "RESOURCE_NOT_FOUND"],
  ])("maps frozen safe error %s %s", async (status, code) => {
    const client = new WorkflowReadClient(vi.fn().mockResolvedValue(failure(status, code)) as typeof fetch);
    await expect(client.get(projectId)).rejects.toMatchObject({ code });
  });

  it("rejects unknown error pairs without exposing server text", async () => {
    for (const server of [failure(500, "SYSTEM_INTERNAL"), failure(403, "RESOURCE_NOT_FOUND")]) {
      const client = new WorkflowReadClient(vi.fn().mockResolvedValue(server) as typeof fetch);
      await expect(client.get(projectId)).rejects.toMatchObject({ code: "WORKFLOW_CLIENT_UNAVAILABLE" });
    }
  });

  it("requires an exact response ETag and JSON envelope", async () => {
    for (const server of [response(snapshot(), 200, '"v2"'),
      new Response(JSON.stringify({ data: snapshot(), trace_id: projectId }), { status: 200 }),
      response(snapshot(), 202),
      response(snapshot(), 200, 'W/"v0"')]) {
      const client = new WorkflowReadClient(vi.fn().mockResolvedValue(server) as typeof fetch);
      await expect(client.get(projectId)).rejects.toBeInstanceOf(WorkflowReadError);
    }
  });

  it("rejects inconsistent state, ordering, item identity, type and ETag", () => {
    const variants = [
      { ...snapshot(), workflow_id: "00000000-0000-0000-0000-000000000000" },
      { ...snapshot(), version: 2 },
      { ...snapshot(), current_stage: "HANDOVER" },
      { ...snapshot("ACTIVE"), current_stage: "SURVEY" },
      { ...snapshot(), stages: snapshot().stages.slice(0, 5) },
      { ...snapshot(), stages: snapshot().stages.map((stage, index) => index === 0
        ? { ...stage, order: 2 } : stage) },
      { ...snapshot(), stages: snapshot().stages.map((stage, index) => index === 0
        ? { ...stage, checklist_items: [{ ...stage.checklist_items[0], item_key: "FALSE" },
          stage.checklist_items[1]] } : stage) },
      { ...snapshot(), stages: snapshot().stages.map((stage, index) => index === 0
        ? { ...stage, checklist_items: [{ ...stage.checklist_items[0], required: false },
          stage.checklist_items[1]] } : stage) },
      { ...snapshot(), etag: '"v9007199254740993"' },
    ];
    for (const data of variants) {
      expect(() => parseWorkflow(data)).toThrowError(WorkflowReadError);
    }
  });

  it("fails closed on network errors", async () => {
    const client = new WorkflowReadClient(vi.fn().mockRejectedValue(new Error("secret")) as typeof fetch);
    await expect(client.get(projectId)).rejects.toMatchObject({ code: "WORKFLOW_CLIENT_UNAVAILABLE" });
  });
});
