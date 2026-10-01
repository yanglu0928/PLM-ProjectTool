/** Fixed V1 Workflow snapshot. This read is never a Gate or approval proof. */
export interface WorkflowChecklistItem {
  readonly item_key: string;
  readonly required: true;
  readonly state: "PENDING" | "PASS" | "FAIL" | "WAIVED";
}

export interface WorkflowStage {
  readonly stage_key: "HANDOVER" | "SURVEY" | "REQUIREMENT" | "PROTOTYPE" | "SOLUTION" | "PLAN";
  readonly order: number;
  readonly state: "NOT_STARTED" | "ACTIVE" | "BLOCKED" | "COMPLETED";
  readonly checklist_items: readonly WorkflowChecklistItem[];
}

export interface WorkflowView {
  readonly workflow_id: string;
  readonly version: 1;
  readonly state: "NOT_STARTED" | "ACTIVE" | "COMPLETED";
  readonly current_stage: WorkflowStage["stage_key"] | null;
  readonly stages: readonly WorkflowStage[];
  readonly etag: string;
}

const messages = {
  WORKFLOW_INVALID_PROJECT: "项目标识无效。",
  AUTH_SESSION_EXPIRED: "会话已失效，请重新登录。",
  LICENSE_OPERATION_DENIED: "当前许可不允许读取项目流程。",
  RESOURCE_NOT_FOUND: "项目流程不存在或无权查看。",
  WORKFLOW_CLIENT_UNAVAILABLE: "暂时无法确认项目流程，请稍后重试。",
} as const;
export type WorkflowReadErrorCode = keyof typeof messages;

export class WorkflowReadError extends Error {
  constructor(readonly code: WorkflowReadErrorCode) {
    super(messages[code]); this.name = "WorkflowReadError";
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const etag = /^"v(0|[1-9][0-9]{0,18})"$/;
const definitions = [
  ["HANDOVER", "HANDOVER_BASELINE", "HANDOVER_ISSUES"],
  ["SURVEY", "SURVEY_ACTUAL_SOURCES", "SURVEY_CONCLUSION"],
  ["REQUIREMENT", "REQUIREMENT_FORMAL_VERSIONS", "REQUIREMENT_ACCEPTANCE"],
  ["PROTOTYPE", "PROTOTYPE_SCOPE_DECISIONS", "PROTOTYPE_COVERAGE"],
  ["SOLUTION", "SOLUTION_APPROVED_SET", "SOLUTION_COVERAGE"],
  ["PLAN", "PLAN_APPROVED_BASELINE", "PLAN_WBS_VALIDATION"],
] as const;

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function identifier(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value)
    && value !== "00000000-0000-0000-0000-000000000000";
}
function validEtag(value: unknown): value is string {
  if (typeof value !== "string" || !etag.test(value)) return false;
  const version = Number(value.slice(2, -1));
  return Number.isSafeInteger(version) && version >= 0;
}

/** Whitelist a response into immutable V1 fields; reject incomplete/inconsistent snapshots. */
export function parseWorkflow(value: unknown): WorkflowView {
  if (!record(value) || !identifier(value.workflow_id) || value.version !== 1
    || !["NOT_STARTED", "ACTIVE", "COMPLETED"].includes(value.state as string)
    || !validEtag(value.etag) || !Array.isArray(value.stages)
    || value.stages.length !== definitions.length) {
    throw new WorkflowReadError("WORKFLOW_CLIENT_UNAVAILABLE");
  }
  const stages: WorkflowStage[] = [];
  for (const [index, definition] of definitions.entries()) {
    const stage: unknown = value.stages[index];
    if (!record(stage) || stage.stage_key !== definition[0] || stage.order !== index + 1
      || !["NOT_STARTED", "ACTIVE", "BLOCKED", "COMPLETED"].includes(stage.state as string)
      || !Array.isArray(stage.checklist_items) || stage.checklist_items.length !== 2) {
      throw new WorkflowReadError("WORKFLOW_CLIENT_UNAVAILABLE");
    }
    const items: WorkflowChecklistItem[] = [];
    for (let itemIndex = 0; itemIndex < 2; itemIndex++) {
      const item: unknown = stage.checklist_items[itemIndex];
      if (!record(item) || item.item_key !== definition[itemIndex + 1] || item.required !== true
        || !["PENDING", "PASS", "FAIL", "WAIVED"].includes(item.state as string)) {
        throw new WorkflowReadError("WORKFLOW_CLIENT_UNAVAILABLE");
      }
      items.push(Object.freeze({ item_key: item.item_key as string, required: true,
        state: item.state as WorkflowChecklistItem["state"] }));
    }
    stages.push(Object.freeze({ stage_key: definition[0], order: index + 1,
      state: stage.state as WorkflowStage["state"], checklist_items: Object.freeze(items) }));
  }
  const state = value.state as WorkflowView["state"];
  const current = value.current_stage;
  if (state === "NOT_STARTED") {
    if (current !== null || stages.some((stage) => stage.state !== "NOT_STARTED"
      || stage.checklist_items.some((item) => item.state !== "PENDING"))) {
      throw new WorkflowReadError("WORKFLOW_CLIENT_UNAVAILABLE");
    }
  } else if (state === "COMPLETED") {
    if (current !== "PLAN" || stages.some((stage) => stage.state !== "COMPLETED")) {
      throw new WorkflowReadError("WORKFLOW_CLIENT_UNAVAILABLE");
    }
  } else {
    const index = definitions.findIndex((stage) => stage[0] === current);
    if (index < 0 || stages.some((stage, stageIndex) => stageIndex < index
      ? stage.state !== "COMPLETED" : stageIndex === index
        ? !["ACTIVE", "BLOCKED"].includes(stage.state) : stage.state !== "NOT_STARTED")) {
      throw new WorkflowReadError("WORKFLOW_CLIENT_UNAVAILABLE");
    }
  }
  return Object.freeze({ workflow_id: value.workflow_id, version: 1, state,
    current_stage: current as WorkflowView["current_stage"],
    stages: Object.freeze(stages), etag: value.etag });
}

export class WorkflowReadClient {
  constructor(private readonly fetcher: typeof fetch = fetch,
    private readonly timeoutMs = 10_000) {
    if (!Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 30_000) {
      throw new WorkflowReadError("WORKFLOW_CLIENT_UNAVAILABLE");
    }
  }

  async get(projectId: string): Promise<WorkflowView> {
    if (!identifier(projectId)) throw new WorkflowReadError("WORKFLOW_INVALID_PROJECT");
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const fetcher = this.fetcher;
      const response = await fetcher(`/api/v1/projects/${projectId}/workflow`, {
        method: "GET", credentials: "same-origin", cache: "no-store", redirect: "error",
        headers: { Accept: "application/json" }, signal: controller.signal,
      });
      if (controller.signal.aborted
        || response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
        throw new WorkflowReadError("WORKFLOW_CLIENT_UNAVAILABLE");
      }
      const payload: unknown = await response.json();
      if (controller.signal.aborted || !record(payload) || !identifier(payload.trace_id)) {
        throw new WorkflowReadError("WORKFLOW_CLIENT_UNAVAILABLE");
      }
      if (response.status !== 200) {
        const code = record(payload.error) ? payload.error.code : null;
        const known: Record<string, number> = {
          AUTH_SESSION_EXPIRED: 401, LICENSE_OPERATION_DENIED: 403,
          RESOURCE_NOT_FOUND: 404,
        };
        if (typeof code === "string" && Object.hasOwn(known, code) && known[code] === response.status) {
          throw new WorkflowReadError(code as WorkflowReadErrorCode);
        }
        throw new WorkflowReadError("WORKFLOW_CLIENT_UNAVAILABLE");
      }
      const view = parseWorkflow(payload.data);
      if (response.headers.get("etag") !== view.etag) {
        throw new WorkflowReadError("WORKFLOW_CLIENT_UNAVAILABLE");
      }
      return view;
    } catch (error) {
      if (error instanceof WorkflowReadError) throw error;
      throw new WorkflowReadError("WORKFLOW_CLIENT_UNAVAILABLE");
    } finally { window.clearTimeout(timer); }
  }
}
