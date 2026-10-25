import { describe, expect, it, vi } from "vitest";

import {
  WorkflowChecklistQualificationClient, WorkflowChecklistQualificationError,
} from "./workflowChecklistQualificationClient";

const project = "01234567-89ab-4cde-8123-456789abcdef";
const workflow = "11234567-89ab-4cde-8123-456789abcdef";
const analysis = "21234567-89ab-4cde-8123-456789abcdef";
const round = "31234567-89ab-4cde-8123-456789abcdef";
const evidence = "41234567-89ab-4cde-8123-456789abcdef";
const conclusion = "51234567-89ab-4cde-8123-456789abcdef";
const requirementVersion = "61234567-89ab-4cde-8123-456789abcdef";
const prototype = "71234567-89ab-4cde-8123-456789abcdef";
const prototypeVersion = "81234567-89ab-4cde-8123-456789abcdef";
const prototypeRound = "91234567-89ab-4cde-8123-456789abcdef";
function data() {
  return { workflow_id: workflow, project_id: project, definition_version: 1,
    stage_key: "HANDOVER", item_key: "HANDOVER_BASELINE", current_item_state: "PENDING",
    workflow_etag: '"v4"', handover_analysis_version_id: analysis,
    review_round_ref: round, evidence_refs: [evidence] };
}
function surveyData() {
  return { workflow_id: workflow, project_id: project, definition_version: 1,
    stage_key: "SURVEY", item_key: "SURVEY_CONCLUSION", current_item_state: "PENDING",
    workflow_etag: '"v6"', survey_conclusion_id: conclusion,
    review_round_ref: round, evidence_refs: [evidence] };
}
function requirementData() {
  return { workflow_id: workflow, project_id: project, definition_version: 1,
    stage_key: "REQUIREMENT", item_key: "REQUIREMENT_ACCEPTANCE",
    current_item_state: "PENDING", workflow_etag: '"v9"',
    requirement_version_refs: [requirementVersion], review_round_refs: [round],
    evidence_refs: [evidence] };
}
function prototypeData() {
  return { workflow_id: workflow, project_id: project, definition_version: 1,
    stage_key: "PROTOTYPE", item_key: "PROTOTYPE_COVERAGE",
    current_item_state: "PENDING", workflow_etag: '"v11"',
    qualified_subjects: [
      { subject_type: "PRT-03", subject_id: prototype,
        subject_version_id: prototypeVersion, review_round_ref: prototypeRound },
      { subject_type: "REQ-03", subject_id: analysis,
        subject_version_id: requirementVersion, review_round_ref: round },
    ], evidence_refs: [evidence] };
}
function response(value: unknown, status = 200, tag = '"v4"', cache = "no-store") {
  return new Response(JSON.stringify(status === 200
    ? { data: value, trace_id: project }
    : { error: { code: value, message: "private" }, trace_id: project }), {
    status, headers: { "Content-Type": "application/json", ETag: tag,
      "Cache-Control": cache },
  });
}

describe("WorkflowChecklistQualificationClient", () => {
  it("reads and freezes the exact minimal qualification projection", async () => {
    const fetcher = vi.fn().mockResolvedValue(response(data()));
    const client = new WorkflowChecklistQualificationClient(fetcher as typeof fetch);
    const result = await client.get(project, "HANDOVER_BASELINE");
    expect(result.evidence_refs).toEqual([evidence]);
    expect(Object.isFrozen(result)).toBe(true);
    expect(Object.isFrozen(result.evidence_refs)).toBe(true);
    expect(fetcher).toHaveBeenCalledWith(
      `/api/v1/projects/${project}/workflow/checklist-items/HANDOVER_BASELINE/qualification`,
      expect.objectContaining({ method: "GET", credentials: "same-origin", cache: "no-store" }),
    );
  });

  it("reads the strict Survey projection without accepting Handover subject fields", async () => {
    const fetcher = vi.fn().mockResolvedValue(response(surveyData(), 200, '"v6"'));
    const result = await new WorkflowChecklistQualificationClient(fetcher as typeof fetch)
      .get(project, "SURVEY_CONCLUSION");
    expect(result).toMatchObject({ stage_key: "SURVEY", item_key: "SURVEY_CONCLUSION",
      survey_conclusion_id: conclusion });
    expect("handover_analysis_version_id" in result).toBe(false);

    const crossField = response({ ...surveyData(), survey_conclusion_id: undefined,
      handover_analysis_version_id: analysis }, 200, '"v6"');
    await expect(new WorkflowChecklistQualificationClient(
      vi.fn().mockResolvedValue(crossField) as typeof fetch,
    ).get(project, "SURVEY_CONCLUSION"))
      .rejects.toMatchObject({ code: "WORKFLOW_QUALIFICATION_UNAVAILABLE" });
  });

  it("reads and freezes the strict aggregate Requirement projection", async () => {
    const fetcher = vi.fn().mockResolvedValue(response(requirementData(), 200, '"v9"'));
    const result = await new WorkflowChecklistQualificationClient(fetcher as typeof fetch)
      .get(project, "REQUIREMENT_ACCEPTANCE");
    expect(result).toMatchObject({ stage_key: "REQUIREMENT",
      item_key: "REQUIREMENT_ACCEPTANCE", requirement_version_refs: [requirementVersion],
      review_round_refs: [round] });
    if (result.stage_key !== "REQUIREMENT") throw new Error("wrong qualification variant");
    expect(Object.isFrozen(result.requirement_version_refs)).toBe(true);
    expect(Object.isFrozen(result.review_round_refs)).toBe(true);
    for (const invalid of [
      { ...requirementData(), review_round_refs: [] },
      { ...requirementData(), requirement_version_refs: [requirementVersion, requirementVersion] },
      { ...requirementData(), review_round_ref: round },
    ]) {
      await expect(new WorkflowChecklistQualificationClient(
        vi.fn().mockResolvedValue(response(invalid, 200, '"v9"')) as typeof fetch,
      ).get(project, "REQUIREMENT_ACCEPTANCE"))
        .rejects.toMatchObject({ code: "WORKFLOW_QUALIFICATION_UNAVAILABLE" });
    }
  });

  it("reads only ordered mixed Prototype subjects without exposing internal details", async () => {
    const fetcher = vi.fn().mockResolvedValue(response(prototypeData(), 200, '"v11"'));
    const result = await new WorkflowChecklistQualificationClient(fetcher as typeof fetch)
      .get(project, "PROTOTYPE_COVERAGE");
    expect(result.stage_key).toBe("PROTOTYPE");
    if (result.stage_key !== "PROTOTYPE") throw new Error("wrong qualification variant");
    expect(result.qualified_subjects.map((subject) => subject.subject_type))
      .toEqual(["PRT-03", "REQ-03"]);
    expect(Object.isFrozen(result.qualified_subjects)).toBe(true);
    expect(Object.isFrozen(result.qualified_subjects[0])).toBe(true);
    expect("requirement_version_refs" in result).toBe(false);
    expect(fetcher).toHaveBeenCalledWith(
      `/api/v1/projects/${project}/workflow/checklist-items/PROTOTYPE_COVERAGE/qualification`,
      expect.objectContaining({ method: "GET", credentials: "same-origin" }),
    );
    for (const invalid of [
      { ...prototypeData(), qualified_subjects: [] },
      { ...prototypeData(), qualified_subjects: [...prototypeData().qualified_subjects].reverse() },
      { ...prototypeData(), qualified_subjects: [prototypeData().qualified_subjects[0],
        prototypeData().qualified_subjects[0]] },
      { ...prototypeData(), requirement_version_refs: [requirementVersion] },
      { ...prototypeData(), qualified_subjects: [{ ...prototypeData().qualified_subjects[0],
        content_fingerprint: "private" }] },
    ]) {
      await expect(new WorkflowChecklistQualificationClient(
        vi.fn().mockResolvedValue(response(invalid, 200, '"v11"')) as typeof fetch,
      ).get(project, "PROTOTYPE_COVERAGE"))
        .rejects.toMatchObject({ code: "WORKFLOW_QUALIFICATION_UNAVAILABLE" });
    }
  });

  it("rejects invalid input without a request", async () => {
    const fetcher = vi.fn();
    const client = new WorkflowChecklistQualificationClient(fetcher as typeof fetch);
    await expect(client.get("../other", "HANDOVER_BASELINE"))
      .rejects.toMatchObject({ code: "WORKFLOW_QUALIFICATION_INVALID_INPUT" });
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("projects only matching safe server errors", async () => {
    const fetcher = vi.fn().mockResolvedValue(response("WORKFLOW_GATE_NOT_SATISFIED", 409));
    await expect(new WorkflowChecklistQualificationClient(fetcher as typeof fetch)
      .get(project, "HANDOVER_BASELINE"))
      .rejects.toMatchObject({ code: "WORKFLOW_GATE_NOT_SATISFIED" });
    fetcher.mockResolvedValue(response("AUTH_SESSION_EXPIRED", 409));
    await expect(new WorkflowChecklistQualificationClient(fetcher as typeof fetch)
      .get(project, "HANDOVER_BASELINE"))
      .rejects.toMatchObject({ code: "WORKFLOW_QUALIFICATION_UNAVAILABLE" });
  });

  it("rejects extra fields, identity drift, duplicate evidence and header drift", async () => {
    const bad = [
      response({ ...data(), extra: true }),
      response({ ...data(), project_id: workflow }),
      response({ ...data(), evidence_refs: [evidence, evidence] }),
      response(data(), 200, '"v5"'),
      response(data(), 200, '"v4"', "public"),
    ];
    for (const value of bad) {
      const client = new WorkflowChecklistQualificationClient(
        vi.fn().mockResolvedValue(value) as typeof fetch,
      );
      await expect(client.get(project, "HANDOVER_BASELINE"))
        .rejects.toBeInstanceOf(WorkflowChecklistQualificationError);
    }
  });
});
