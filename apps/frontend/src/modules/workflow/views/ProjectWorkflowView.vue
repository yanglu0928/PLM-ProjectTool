<script setup lang="ts">
import { inject, onUnmounted, ref, shallowRef, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { WorkflowReadClient, WorkflowReadError, type WorkflowView } from "@/modules/workflow/api/workflowReadClient";
import { WorkflowStartClient, WorkflowStartError,
  type WorkflowStartFirstReceipt } from "@/modules/workflow/api/workflowStartClient";
import { WorkflowChecklistQualificationClient, WorkflowChecklistQualificationError,
  type WorkflowChecklistQualificationView } from "@/modules/workflow/api/workflowChecklistQualificationClient";
import { WorkflowChecklistRecordClient, WorkflowChecklistRecordError,
  type HandoverChecklistItemKey, type SupportedChecklistResult,
  type WorkflowChecklistFirstReceipt } from "@/modules/workflow/api/workflowChecklistRecordClient";
import { WorkflowTransitionClient, WorkflowTransitionError,
  type WorkflowTransitionFirstReceipt } from "@/modules/workflow/api/workflowTransitionClient";

const props = defineProps<{ session?: SessionClient; workflows?: WorkflowReadClient;
  starter?: WorkflowStartClient; qualifications?: WorkflowChecklistQualificationClient;
  checklistRecords?: WorkflowChecklistRecordClient; transitions?: WorkflowTransitionClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const workflows = toRaw(props.workflows ?? new WorkflowReadClient());
const starter = toRaw(props.starter ?? new WorkflowStartClient(session));
const qualifications = toRaw(props.qualifications ?? new WorkflowChecklistQualificationClient());
const checklistRecords = toRaw(props.checklistRecords ?? new WorkflowChecklistRecordClient(session));
const transitions = toRaw(props.transitions ?? new WorkflowTransitionClient(session));
const identity = session.view;
const route = useRoute();
const workflow = shallowRef<WorkflowView | null>(null);
const busy = ref(false);
const writeBusy = ref(false);
const error = ref("");
const startTarget = shallowRef<WorkflowView | null>(null);
const startConfirmed = ref(false);
const retryConfirmed = ref(false);
const clearConfirmed = ref(false);
const receipt = ref<WorkflowStartFirstReceipt | null>(null);
const requireFreshRead = ref(false);
const storageError = ref(false);
const qualificationBusy = ref(false);
const checklistTarget = shallowRef<{ before: WorkflowView; item: HandoverChecklistItemKey;
  result: SupportedChecklistResult; qualification: WorkflowChecklistQualificationView | null } | null>(null);
const checklistConfirmed = ref(false);
const checklistRetryConfirmed = ref(false);
const checklistClearConfirmed = ref(false);
const checklistReason = ref("");
const checklistImpact = ref("");
const checklistReceipt = ref<WorkflowChecklistFirstReceipt | null>(null);
const transitionTarget = shallowRef<WorkflowView | null>(null);
const transitionConfirmed = ref(false);
const transitionRetryConfirmed = ref(false);
const transitionClearConfirmed = ref(false);
const transitionReason = ref("");
const transitionReceipt = ref<WorkflowTransitionFirstReceipt | null>(null);
type PendingStart = { actor: string; project: string; workflow: string; key: string; etag: '"v0"' };
type PendingChecklist = { actor: string; project: string; workflow: string;
  item: HandoverChecklistItemKey; result: SupportedChecklistResult; key: string;
  etag: string; evidence: readonly string[]; reason: string | null; impact: string | null };
type PendingTransition = { actor: string; project: string; workflow: string;
  key: string; etag: string; reason: string; target: "SURVEY" };
const storageKey = identity ? `plm.workflow.start.pending.${identity.user.user_id}` : "";
const checklistStorageKey = identity ? `plm.workflow.checklist.pending.${identity.user.user_id}` : "";
const transitionStorageKey = identity ? `plm.workflow.transition.pending.${identity.user.user_id}` : "";
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
function validPending(value: unknown): value is PendingStart {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const entry = value as Record<string, unknown>;
  return entry.actor === identity?.user.user_id
    && typeof entry.project === "string" && uuid.test(entry.project)
    && typeof entry.workflow === "string" && uuid.test(entry.workflow)
    && typeof entry.key === "string" && /^[\x20-\x7e]{16,128}$/.test(entry.key)
    && entry.etag === '"v0"';
}
function readPending(): PendingStart | null {
  if (!storageKey) return null;
  try {
    const raw = window.sessionStorage.getItem(storageKey);
    if (raw === null) return null;
    const parsed: unknown = JSON.parse(raw);
    if (validPending(parsed)) return parsed;
  } catch { /* Existing operation cannot be safely interpreted. */ }
  storageError.value = true;
  return null;
}
const pending = shallowRef<PendingStart | null>(readPending());
function validChecklistPending(value: unknown): value is PendingChecklist {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const entry = value as Record<string, unknown>;
  const evidence = entry.evidence;
  const identifier = (item: unknown) => typeof item === "string" && uuid.test(item)
    && item !== "00000000-0000-0000-0000-000000000000";
  const text = (item: unknown) => typeof item === "string" && item.length > 0
    && item.length <= 2000 && item.trim() === item && !item.includes("\u0000");
  const version = typeof entry.etag === "string" && /^"v[1-9]\d*"$/.test(entry.etag)
    ? Number(entry.etag.slice(2, -1)) : null;
  return Object.keys(entry).length === 10 && entry.actor === identity?.user.user_id
    && identifier(entry.actor) && identifier(entry.project) && identifier(entry.workflow)
    && ["HANDOVER_BASELINE", "HANDOVER_ISSUES"].includes(entry.item as string)
    && ["PASS", "FAIL"].includes(entry.result as string)
    && typeof entry.key === "string" && /^[\x20-\x7e]{16,128}$/.test(entry.key)
    && Number.isSafeInteger(version) && version !== null && version < Number.MAX_SAFE_INTEGER
    && Array.isArray(evidence) && evidence.length <= 500
    && evidence.every(identifier)
    && new Set(evidence).size === evidence.length
    && (entry.result === "PASS"
      ? evidence.length > 0 && entry.reason === null && entry.impact === null
      : evidence.length === 0 && text(entry.reason) && text(entry.impact));
}
function readChecklistPending(): PendingChecklist | null {
  if (!checklistStorageKey) return null;
  try {
    const raw = window.sessionStorage.getItem(checklistStorageKey);
    if (raw === null) return null;
    const parsed: unknown = JSON.parse(raw);
    if (validChecklistPending(parsed)) return Object.freeze({ ...parsed,
      evidence: Object.freeze([...parsed.evidence]) });
  } catch { /* Existing operation cannot be safely interpreted. */ }
  storageError.value = true;
  return null;
}
const checklistPending = shallowRef<PendingChecklist | null>(readChecklistPending());
function validTransitionPending(value: unknown): value is PendingTransition {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const entry = value as Record<string, unknown>;
  const version = typeof entry.etag === "string" && /^"v[1-9]\d*"$/.test(entry.etag)
    ? Number(entry.etag.slice(2, -1)) : null;
  return Object.keys(entry).length === 7 && entry.actor === identity?.user.user_id
    && typeof entry.actor === "string" && uuid.test(entry.actor)
    && typeof entry.project === "string" && uuid.test(entry.project)
    && typeof entry.workflow === "string" && uuid.test(entry.workflow)
    && typeof entry.key === "string" && /^[\x20-\x7e]{16,128}$/.test(entry.key)
    && Number.isSafeInteger(version) && version !== null && version < Number.MAX_SAFE_INTEGER
    && typeof entry.reason === "string" && entry.reason.length > 0
    && entry.reason.length <= 2000 && entry.reason.trim() === entry.reason
    && !entry.reason.includes("\u0000") && entry.target === "SURVEY";
}
function readTransitionPending(): PendingTransition | null {
  if (!transitionStorageKey) return null;
  try {
    const raw = window.sessionStorage.getItem(transitionStorageKey);
    if (raw === null) return null;
    const parsed: unknown = JSON.parse(raw);
    if (validTransitionPending(parsed)) return Object.freeze({ ...parsed });
  } catch { /* Existing operation cannot be safely interpreted. */ }
  storageError.value = true;
  return null;
}
const transitionPending = shallowRef<PendingTransition | null>(readTransitionPending());
function savePending(value: PendingStart): boolean {
  if (!storageKey || storageError.value || pending.value) return false;
  try {
    const serialized = JSON.stringify(value);
    window.sessionStorage.setItem(storageKey, serialized);
    if (window.sessionStorage.getItem(storageKey) !== serialized) return false;
    pending.value = value;
    return true;
  } catch { storageError.value = true; return false; }
}
function clearPending(value: PendingStart): boolean {
  if (!storageKey || pending.value !== value) return false;
  try {
    if (window.sessionStorage.getItem(storageKey) !== JSON.stringify(value)) return false;
    window.sessionStorage.removeItem(storageKey);
    if (window.sessionStorage.getItem(storageKey) !== null) return false;
    pending.value = null;
    return true;
  } catch { storageError.value = true; return false; }
}
function saveChecklistPending(value: PendingChecklist): boolean {
  if (!checklistStorageKey || storageError.value || checklistPending.value) return false;
  try {
    const serialized = JSON.stringify(value);
    window.sessionStorage.setItem(checklistStorageKey, serialized);
    if (window.sessionStorage.getItem(checklistStorageKey) !== serialized) return false;
    checklistPending.value = value;
    return true;
  } catch { storageError.value = true; return false; }
}
function clearChecklistPending(value: PendingChecklist): boolean {
  if (!checklistStorageKey || checklistPending.value !== value) return false;
  try {
    if (window.sessionStorage.getItem(checklistStorageKey) !== JSON.stringify(value)) return false;
    window.sessionStorage.removeItem(checklistStorageKey);
    if (window.sessionStorage.getItem(checklistStorageKey) !== null) return false;
    checklistPending.value = null;
    return true;
  } catch { storageError.value = true; return false; }
}
function saveTransitionPending(value: PendingTransition): boolean {
  if (!transitionStorageKey || storageError.value || transitionPending.value) return false;
  try {
    const serialized = JSON.stringify(value);
    window.sessionStorage.setItem(transitionStorageKey, serialized);
    if (window.sessionStorage.getItem(transitionStorageKey) !== serialized) return false;
    transitionPending.value = value;
    return true;
  } catch { storageError.value = true; return false; }
}
function clearTransitionPending(value: PendingTransition): boolean {
  if (!transitionStorageKey || transitionPending.value !== value) return false;
  try {
    if (window.sessionStorage.getItem(transitionStorageKey) !== JSON.stringify(value)) return false;
    window.sessionStorage.removeItem(transitionStorageKey);
    if (window.sessionStorage.getItem(transitionStorageKey) !== null) return false;
    transitionPending.value = null;
    return true;
  } catch { storageError.value = true; return false; }
}
let generation = 0;
let mounted = true;
function mayRead() {
  return mounted && !!identity && !identity.password_change_required
    && session.view?.user.user_id === identity.user.user_id;
}
function mayStart() {
  return mayRead() && session.canSubmit && !storageError.value
    && !!session.view?.authorized_projects.some((item) =>
      item.project_id === route.params.projectId && item.role === "PROJECT_MANAGER");
}
function supportedItem(value: string): value is HandoverChecklistItemKey {
  return value === "HANDOVER_BASELINE" || value === "HANDOVER_ISSUES";
}
function mayRecord() {
  return mayStart() && workflow.value?.state === "ACTIVE"
    && workflow.value.current_stage === "HANDOVER";
}
function mayTransition() {
  const handover = workflow.value?.stages[0];
  return mayStart() && workflow.value?.state === "ACTIVE"
    && workflow.value.current_stage === "HANDOVER" && handover?.state === "ACTIVE"
    && handover.checklist_items.every((item) => item.state === "PASS");
}
async function load() {
  if (!mayRead() || busy.value || writeBusy.value || qualificationBusy.value) return;
  const projectId = typeof route.params.projectId === "string" ? route.params.projectId : "";
  const current = ++generation;
  busy.value = true; error.value = ""; workflow.value = null;
  startTarget.value = null; startConfirmed.value = false;
  retryConfirmed.value = false; clearConfirmed.value = false;
  checklistTarget.value = null; checklistConfirmed.value = false;
  checklistRetryConfirmed.value = false; checklistClearConfirmed.value = false;
  checklistReason.value = ""; checklistImpact.value = "";
  transitionTarget.value = null; transitionConfirmed.value = false;
  transitionRetryConfirmed.value = false; transitionClearConfirmed.value = false;
  transitionReason.value = "";
  try {
    const latest = await workflows.get(projectId);
    if (!mounted || current !== generation || route.params.projectId !== projectId || !mayRead()) return;
    workflow.value = latest;
    requireFreshRead.value = false;
    receipt.value = null;
    checklistReceipt.value = null;
    transitionReceipt.value = null;
  } catch (failure) {
    if (!mounted || current !== generation || route.params.projectId !== projectId) return;
    error.value = failure instanceof WorkflowReadError
      ? failure.message : "暂时无法确认项目流程，请稍后重试。";
  } finally { if (mounted && current === generation) busy.value = false; }
}
async function beginChecklistPass(item: string) {
  if (!supportedItem(item) || !mayRecord() || busy.value || writeBusy.value
    || qualificationBusy.value || pending.value || checklistPending.value || transitionPending.value
    || requireFreshRead.value || receipt.value || checklistReceipt.value) return;
  const before = workflow.value!;
  const projectId = route.params.projectId as string;
  const current = ++generation;
  qualificationBusy.value = true; error.value = ""; checklistTarget.value = null;
  checklistConfirmed.value = false; checklistReason.value = ""; checklistImpact.value = "";
  try {
    const proof = await qualifications.get(projectId, item);
    const latestItem = before.stages.find((stage) => stage.stage_key === "HANDOVER")
      ?.checklist_items.find((value) => value.item_key === item);
    if (!mounted || current !== generation || route.params.projectId !== projectId
      || workflow.value !== before || !mayRecord()) return;
    if (proof.project_id !== projectId || proof.workflow_id !== before.workflow_id
      || proof.workflow_etag !== before.etag || proof.current_item_state !== latestItem?.state) {
      requireFreshRead.value = true; workflow.value = null;
      error.value = "资格依据与当前流程快照不一致，请重新读取。";
      return;
    }
    checklistTarget.value = Object.freeze({ before, item, result: "PASS" as const,
      qualification: proof });
  } catch (failure) {
    if (!mounted || current !== generation || route.params.projectId !== projectId) return;
    error.value = failure instanceof WorkflowChecklistQualificationError
      ? failure.message : "暂时无法确认权威资格，请稍后重试。";
  } finally { if (mounted && current === generation) qualificationBusy.value = false; }
}
function beginChecklistFail(item: string) {
  if (!supportedItem(item) || !mayRecord() || busy.value || writeBusy.value
    || qualificationBusy.value || pending.value || checklistPending.value || transitionPending.value
    || requireFreshRead.value || receipt.value || checklistReceipt.value) return;
  checklistTarget.value = Object.freeze({ before: workflow.value!, item,
    result: "FAIL" as const, qualification: null });
  checklistConfirmed.value = false; checklistReason.value = ""; checklistImpact.value = "";
  error.value = "";
}
function canRetryChecklist(): boolean {
  const operation = checklistPending.value;
  const latest = workflow.value;
  return !!operation && !!latest && mayRecord() && !busy.value && !writeBusy.value
    && !qualificationBusy.value && !requireFreshRead.value
    && operation.project === route.params.projectId
    && operation.workflow === latest.workflow_id && operation.etag === latest.etag
    && latest.stages.find((stage) => stage.stage_key === "HANDOVER")
      ?.checklist_items.some((item) => item.item_key === operation.item) === true;
}
async function submitChecklist() {
  if (!mayRecord() || busy.value || writeBusy.value || qualificationBusy.value
    || requireFreshRead.value || pending.value || transitionPending.value) return;
  const recovery = checklistPending.value;
  if (recovery && (!canRetryChecklist() || !checklistRetryConfirmed.value)) return;
  const target = checklistTarget.value;
  if (!recovery && (!target || !checklistConfirmed.value || workflow.value !== target.before)) return;
  const reason = recovery?.reason ?? (target?.result === "FAIL" ? checklistReason.value.trim() : null);
  const impact = recovery?.impact ?? (target?.result === "FAIL" ? checklistImpact.value.trim() : null);
  if (!recovery && target?.result === "FAIL" && (!reason || !impact
    || reason.length > 2000 || impact.length > 2000)) {
    error.value = "记录未通过时，请填写未满足原因和影响/后续处理（各不超过2000字）。";
    return;
  }
  const before = workflow.value!;
  const attempt: PendingChecklist = recovery ?? Object.freeze({
    actor: identity!.user.user_id, project: route.params.projectId as string,
    workflow: before.workflow_id, item: target!.item, result: target!.result,
    key: crypto.randomUUID(), etag: before.etag,
    evidence: target!.qualification?.evidence_refs ?? Object.freeze([]),
    reason, impact,
  });
  if (!recovery && !saveChecklistPending(attempt)) {
    storageError.value = true;
    error.value = "无法安全保存原检查项操作，记录请求未发送。";
    return;
  }
  const current = ++generation;
  checklistTarget.value = null; checklistConfirmed.value = false;
  checklistRetryConfirmed.value = false; writeBusy.value = true; error.value = "";
  workflow.value = null;
  try {
    const result = await checklistRecords.record(attempt.project, {
      before, item_key: attempt.item, result: attempt.result,
      evidence_refs: attempt.evidence, reason: attempt.reason, impact: attempt.impact,
      idempotency_key: attempt.key,
    });
    if (!mounted || current !== generation || route.params.projectId !== attempt.project
      || !mayRead()) return;
    checklistReceipt.value = result;
    if (!clearChecklistPending(attempt)) storageError.value = true;
    requireFreshRead.value = true;
  } catch (failure) {
    if (!mounted || current !== generation || route.params.projectId !== attempt.project) return;
    requireFreshRead.value = true;
    if (failure instanceof WorkflowChecklistRecordError && !failure.uncertain
      && failure.code !== "CONFLICT_IDEMPOTENCY") {
      if (!clearChecklistPending(attempt)) storageError.value = true;
      error.value = failure.message + " 请重新读取流程后再决定。";
    } else {
      error.value = "检查项记录结果无法确认。原操作号、版本和依据已保留；先重新读取流程与审计，勿生成新操作。";
    }
  } finally { if (mounted && current === generation) writeBusy.value = false; }
}
function acknowledgeChecklistChanged() {
  const operation = checklistPending.value;
  const latest = workflow.value;
  if (!operation || !latest || !checklistClearConfirmed.value || !mayRead()
    || busy.value || writeBusy.value || qualificationBusy.value
    || operation.project !== route.params.projectId || operation.workflow !== latest.workflow_id
    || latest.etag === operation.etag) return;
  if (!clearChecklistPending(operation)) { storageError.value = true; return; }
  checklistClearConfirmed.value = false;
  error.value = "已在核对当前流程及审计后清除原检查项操作；当前状态仍以独立读取结果为准。";
}
function beginTransition() {
  if (!mayTransition() || busy.value || writeBusy.value || qualificationBusy.value
    || pending.value || checklistPending.value || transitionPending.value
    || requireFreshRead.value || receipt.value || checklistReceipt.value
    || transitionReceipt.value) return;
  transitionTarget.value = workflow.value;
  transitionConfirmed.value = false;
  transitionReason.value = "";
  error.value = "";
}
function canRetryTransition(): boolean {
  const operation = transitionPending.value;
  const latest = workflow.value;
  return !!operation && !!latest && mayTransition() && !busy.value && !writeBusy.value
    && !qualificationBusy.value && !requireFreshRead.value
    && operation.project === route.params.projectId
    && operation.workflow === latest.workflow_id && operation.etag === latest.etag;
}
async function submitTransition() {
  if (!mayTransition() || busy.value || writeBusy.value || qualificationBusy.value
    || requireFreshRead.value || pending.value || checklistPending.value) return;
  const recovery = transitionPending.value;
  if (recovery && (!canRetryTransition() || !transitionRetryConfirmed.value)) return;
  if (!recovery && (!transitionTarget.value || !transitionConfirmed.value
    || workflow.value !== transitionTarget.value)) return;
  const reason = recovery?.reason ?? transitionReason.value.trim();
  if (!reason || reason.length > 2000 || reason.includes("\u0000")) {
    error.value = "推进阶段前，请填写本次推进理由（不超过2000字）。";
    return;
  }
  const before = workflow.value!;
  const attempt: PendingTransition = recovery ?? Object.freeze({
    actor: identity!.user.user_id, project: route.params.projectId as string,
    workflow: before.workflow_id, key: crypto.randomUUID(), etag: before.etag,
    reason, target: "SURVEY" as const,
  });
  if (!recovery && !saveTransitionPending(attempt)) {
    storageError.value = true;
    error.value = "无法安全保存原推进操作，阶段推进请求未发送。";
    return;
  }
  const current = ++generation;
  transitionTarget.value = null; transitionConfirmed.value = false;
  transitionRetryConfirmed.value = false; writeBusy.value = true; error.value = "";
  workflow.value = null;
  try {
    const result = await transitions.transition(attempt.project, {
      before, reason: attempt.reason, idempotency_key: attempt.key,
    });
    if (!mounted || current !== generation || route.params.projectId !== attempt.project
      || !mayRead()) return;
    transitionReceipt.value = result;
    if (!clearTransitionPending(attempt)) storageError.value = true;
    requireFreshRead.value = true;
  } catch (failure) {
    if (!mounted || current !== generation || route.params.projectId !== attempt.project) return;
    requireFreshRead.value = true;
    if (failure instanceof WorkflowTransitionError && !failure.uncertain
      && failure.code !== "CONFLICT_IDEMPOTENCY") {
      if (!clearTransitionPending(attempt)) storageError.value = true;
      error.value = failure.message + " 请重新读取流程后再决定。";
    } else {
      error.value = "阶段推进结果无法确认。原操作号、理由和版本已保留；先重新读取流程与审计，勿生成新操作。";
    }
  } finally { if (mounted && current === generation) writeBusy.value = false; }
}
function acknowledgeTransitionChanged() {
  const operation = transitionPending.value;
  const latest = workflow.value;
  if (!operation || !latest || !transitionClearConfirmed.value || !mayRead()
    || busy.value || writeBusy.value || qualificationBusy.value
    || operation.project !== route.params.projectId || operation.workflow !== latest.workflow_id
    || latest.etag === operation.etag) return;
  if (!clearTransitionPending(operation)) { storageError.value = true; return; }
  transitionClearConfirmed.value = false;
  error.value = "已在核对当前流程及审计后清除原推进操作；当前状态仍以独立读取结果为准。";
}
function beginStart() {
  if (!mayStart() || busy.value || writeBusy.value || pending.value || checklistPending.value
    || transitionPending.value
    || requireFreshRead.value
    || receipt.value || workflow.value?.state !== "NOT_STARTED" || workflow.value.etag !== '"v0"') return;
  startTarget.value = workflow.value;
  startConfirmed.value = false;
  error.value = "";
}
function canRetry(): boolean {
  const operation = pending.value;
  return !!operation && !!workflow.value && mayStart() && !busy.value && !writeBusy.value
    && !requireFreshRead.value && operation.project === route.params.projectId
    && operation.workflow === workflow.value.workflow_id
    && operation.etag === workflow.value.etag && workflow.value.state === "NOT_STARTED";
}
async function submitStart() {
  if (!mayStart() || busy.value || writeBusy.value || requireFreshRead.value
    || checklistPending.value || transitionPending.value) return;
  const recovery = pending.value;
  if (recovery && (!canRetry() || !retryConfirmed.value)) return;
  if (!recovery && (!startTarget.value || !startConfirmed.value
    || workflow.value !== startTarget.value || workflow.value.state !== "NOT_STARTED"
    || workflow.value.etag !== '"v0"')) return;
  const before = workflow.value!;
  const attempt: PendingStart = recovery ?? Object.freeze({
    actor: identity!.user.user_id, project: route.params.projectId as string,
    workflow: before.workflow_id, key: crypto.randomUUID(), etag: '"v0"',
  });
  if (!recovery && !savePending(attempt)) {
    storageError.value = true;
    error.value = "无法安全保存原操作号，启动请求未发送。";
    return;
  }
  const current = ++generation;
  startTarget.value = null; startConfirmed.value = false; retryConfirmed.value = false;
  writeBusy.value = true; error.value = ""; workflow.value = null;
  try {
    const result = await starter.start(attempt.project, before, attempt.key);
    if (!mounted || current !== generation || route.params.projectId !== attempt.project
      || !mayRead()) return;
    receipt.value = result;
    if (!clearPending(attempt)) storageError.value = true;
    requireFreshRead.value = true;
  } catch (failure) {
    if (!mounted || current !== generation || route.params.projectId !== attempt.project) return;
    requireFreshRead.value = true;
    if (failure instanceof WorkflowStartError && !failure.uncertain
      && failure.code !== "CONFLICT_IDEMPOTENCY") {
      if (!clearPending(attempt)) storageError.value = true;
      error.value = failure.message + " 请重新读取流程后再决定。";
    } else {
      error.value = "启动结果无法确认。原操作号和版本已保留；先重新读取流程与审计，勿生成新操作。";
    }
  } finally { if (mounted && current === generation) writeBusy.value = false; }
}
function acknowledgeChanged() {
  const operation = pending.value;
  const latest = workflow.value;
  if (!operation || !latest || !clearConfirmed.value || !mayRead() || busy.value || writeBusy.value
    || operation.project !== route.params.projectId || operation.workflow !== latest.workflow_id
    || latest.etag === operation.etag) return;
  if (!clearPending(operation)) { storageError.value = true; return; }
  clearConfirmed.value = false;
  error.value = "已在核对当前流程及审计后清除原操作记录；当前状态仍以独立读取结果为准。";
}
watch(() => route.params.projectId, () => {
  generation += 1; workflow.value = null; busy.value = false; writeBusy.value = false;
  qualificationBusy.value = false;
  error.value = ""; startTarget.value = null; startConfirmed.value = false;
  retryConfirmed.value = false; clearConfirmed.value = false;
  receipt.value = null; requireFreshRead.value = false;
  checklistTarget.value = null; checklistConfirmed.value = false;
  checklistRetryConfirmed.value = false; checklistClearConfirmed.value = false;
  checklistReason.value = ""; checklistImpact.value = ""; checklistReceipt.value = null;
  transitionTarget.value = null; transitionConfirmed.value = false;
  transitionRetryConfirmed.value = false; transitionClearConfirmed.value = false;
  transitionReason.value = ""; transitionReceipt.value = null;
  void load();
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; });
</script>

<template>
  <section class="project-detail" aria-labelledby="workflow-title" :aria-busy="busy || writeBusy || qualificationBusy">
    <p class="section-kicker">当前项目</p>
    <h1 id="workflow-title">项目流程</h1>
    <p><RouterLink :to="{ name: 'project-detail', params: { projectId: route.params.projectId } }">返回项目详情</RouterLink></p>
    <template v-if="!identity">
      <p role="status">尚未读取当前身份。请先登录。</p><RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else-if="identity.password_change_required">
      <p role="status">当前账户须先修改密码，暂不能读取项目流程。</p>
    </template>
    <template v-else>
      <button type="button" :disabled="busy || writeBusy || qualificationBusy" @click="load()">{{ busy ? '正在读取…' : '刷新当前流程' }}</button>
      <p v-if="busy" role="status">正在确认项目流程和当前权限…</p>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="storageError" role="alert">原流程操作记录无法安全读取或保存；本页已关闭新的启动请求及检查项记录请求，并关闭阶段推进请求。请核对当前流程与审计。</p>
      <p v-if="requireFreshRead" role="status">提交后的旧流程快照已清除；须重新读取当前流程。</p>
      <p v-if="receipt" role="status">首次启动回执：{{ receipt.first_result.current_stage }} · {{ receipt.first_result.etag }}。这是首次结果，不是当前状态或 Gate 通过证明。</p>
      <p v-if="checklistReceipt" role="status">首次检查项回执：{{ checklistReceipt.first_record.item_key }} · {{ checklistReceipt.first_record.result }} · {{ checklistReceipt.first_record.etag }}。这是首次结果，不是当前状态或 Gate 通过证明。</p>
      <p v-if="transitionReceipt" role="status">首次阶段推进回执：{{ transitionReceipt.first_transition.from_stage }} → {{ transitionReceipt.first_transition.to_stage }} · {{ transitionReceipt.first_transition.etag }}。这是不可变历史回执，不是当前流程状态证明。</p>
      <p v-if="pending" role="status">原启动操作号已保留。即使离开本页也不可生成新操作；请先读取当前流程与审计。</p>
      <p v-if="checklistPending" role="status">原检查项操作号、版本和依据已保留。即使离开本页也不可生成新操作；请先读取当前流程与审计。</p>
      <p v-if="transitionPending" role="status">原阶段推进操作号、版本和理由已保留。即使离开本页也不可生成新操作；请先读取当前流程与审计。</p>
      <template v-if="workflow">
        <p>流程状态：{{ workflow.state }}；当前阶段：{{ workflow.current_stage ?? '未启动' }}；版本：{{ workflow.etag }}</p>
        <p>以下清单状态仅为服务器当前快照，不代表客户已确认或项目 Gate 已通过。</p>
        <ol aria-label="六阶段流程">
          <li v-for="stage in workflow.stages" :key="stage.stage_key">
            <h2>{{ stage.order }}. {{ stage.stage_key }} · {{ stage.state }}</h2>
            <ul><li v-for="item in stage.checklist_items" :key="item.item_key">
              {{ item.item_key }} · {{ item.state }}
              <span v-if="stage.stage_key === 'HANDOVER' && stage.state !== 'COMPLETED'
                && supportedItem(item.item_key) && mayRecord() && !pending && !checklistPending
                && !transitionPending && !requireFreshRead && !receipt && !checklistReceipt
                && !transitionReceipt && !checklistTarget">
                <button type="button" :disabled="busy || writeBusy || qualificationBusy"
                  @click="beginChecklistPass(item.item_key)">核验并记录通过</button>
                <button type="button" :disabled="busy || writeBusy || qualificationBusy"
                  @click="beginChecklistFail(item.item_key)">记录未通过</button>
              </span>
            </li></ul>
          </li>
        </ol>
      </template>
      <p v-if="qualificationBusy" role="status">正在由服务器复验当前固定来源、评审和处理项资格…</p>
      <form v-if="checklistTarget && !checklistPending && mayRecord() && !requireFreshRead"
        aria-label="检查项记录确认" @submit.prevent="submitChecklist">
        <h2>确认记录 {{ checklistTarget.item }} 为 {{ checklistTarget.result }}</h2>
        <template v-if="checklistTarget.result === 'PASS' && checklistTarget.qualification">
          <p>服务器已按当前版本 {{ checklistTarget.qualification.workflow_etag }} 复验
            {{ checklistTarget.qualification.evidence_refs.length }} 项固定依据。页面不会要求手填或展示内部UUID；提交时服务端仍会再次完整复验。</p>
        </template>
        <template v-else>
          <label>未满足原因（必填）
            <textarea v-model="checklistReason" maxlength="2000" :disabled="writeBusy" required></textarea>
          </label>
          <label>影响及后续处理（必填）
            <textarea v-model="checklistImpact" maxlength="2000" :disabled="writeBusy" required></textarea>
          </label>
        </template>
        <label><input v-model="checklistConfirmed" type="checkbox" :disabled="writeBusy" />
          我已核对当前检查项和服务器资格结果，确认记录</label>
        <button type="submit" :disabled="busy || writeBusy || qualificationBusy || !checklistConfirmed">
          {{ writeBusy ? '正在提交…' : '确认记录' }}</button>
        <button type="button" :disabled="writeBusy" @click="checklistTarget = null">取消</button>
      </form>
      <form v-if="checklistPending && canRetryChecklist()" aria-label="检查项原操作重试"
        @submit.prevent="submitChecklist">
        <h2>使用原操作号核查未确定的检查项记录</h2>
        <p>当前仍是原版本 {{ checklistPending.etag }}。仅使用已保存的原Key、原结果和原依据；不会生成新Key。</p>
        <label><input v-model="checklistRetryConfirmed" type="checkbox" :disabled="writeBusy" />
          我已核对原操作、当前流程与审计</label>
        <button type="submit" :disabled="busy || writeBusy || !checklistRetryConfirmed">使用原操作号重试</button>
      </form>
      <div v-if="checklistPending && workflow && workflow.workflow_id === checklistPending.workflow
        && workflow.etag !== checklistPending.etag">
        <p>当前流程已变化。不能自动认定由原检查项操作造成；请核对审计后再清除原操作记录。</p>
        <label><input v-model="checklistClearConfirmed" type="checkbox" :disabled="writeBusy" />
          我已核对当前流程与审计</label>
        <button type="button" :disabled="busy || writeBusy || !checklistClearConfirmed"
          @click="acknowledgeChecklistChanged">清除原检查项操作记录</button>
      </div>
      <button v-if="mayTransition() && !pending && !checklistPending && !transitionPending
        && !transitionTarget && !requireFreshRead && !receipt && !checklistReceipt
        && !transitionReceipt" type="button" :disabled="busy || writeBusy || qualificationBusy"
        @click="beginTransition">准备推进至 SURVEY</button>
      <form v-if="transitionTarget && !transitionPending && mayTransition() && !requireFreshRead"
        aria-label="阶段推进确认" @submit.prevent="submitTransition">
        <h2>确认从 HANDOVER 推进至 SURVEY</h2>
        <p>服务器会在提交事务中重新验证两项当前 PASS、固定来源、评审与处理项。页面不会接收、展示或生成 Gate UUID。</p>
        <label>推进理由（必填）
          <textarea v-model="transitionReason" maxlength="2000" :disabled="writeBusy" required></textarea>
        </label>
        <label><input v-model="transitionConfirmed" type="checkbox" :disabled="writeBusy" />
          我已核对当前流程 {{ transitionTarget.etag }}、两项检查结果和推进影响，确认推进</label>
        <button type="submit" :disabled="busy || writeBusy || qualificationBusy || !transitionConfirmed">
          {{ writeBusy ? '正在推进…' : '确认推进' }}</button>
        <button type="button" :disabled="writeBusy" @click="transitionTarget = null">取消</button>
      </form>
      <form v-if="transitionPending && canRetryTransition()" aria-label="阶段推进原操作重试"
        @submit.prevent="submitTransition">
        <h2>使用原操作号核查未确定的阶段推进</h2>
        <p>当前仍是原版本 {{ transitionPending.etag }}。仅使用已保存的原Key、原理由和空Gate请求；不会生成新Key。</p>
        <label><input v-model="transitionRetryConfirmed" type="checkbox" :disabled="writeBusy" />
          我已核对原操作、当前流程与审计</label>
        <button type="submit" :disabled="busy || writeBusy || !transitionRetryConfirmed">使用原操作号重试推进</button>
      </form>
      <div v-if="transitionPending && workflow && workflow.workflow_id === transitionPending.workflow
        && workflow.etag !== transitionPending.etag">
        <p>当前流程已变化。不能自动认定由原推进操作造成；请核对审计后再清除原操作记录。</p>
        <label><input v-model="transitionClearConfirmed" type="checkbox" :disabled="writeBusy" />
          我已核对当前流程与审计</label>
        <button type="button" :disabled="busy || writeBusy || !transitionClearConfirmed"
          @click="acknowledgeTransitionChanged">清除原阶段推进操作记录</button>
      </div>
      <button v-if="workflow?.state === 'NOT_STARTED' && !pending && !checklistPending
        && !transitionPending && !startTarget && mayStart() && !requireFreshRead && !receipt"
        type="button" :disabled="busy || writeBusy" @click="beginStart">准备启动流程</button>
      <form v-if="startTarget && mayStart() && !pending && !requireFreshRead" @submit.prevent="submitStart">
        <h2>确认启动项目流程</h2>
        <p>仅激活首阶段 HANDOVER，不确认任何清单、Review 或 Gate；基于 {{ startTarget.etag }} 初态。</p>
        <label><input v-model="startConfirmed" type="checkbox" :disabled="writeBusy" />我已核对项目和初态，确认启动</label>
        <button type="submit" :disabled="busy || writeBusy || !startConfirmed">{{ writeBusy ? '正在提交…' : '确认启动' }}</button>
      </form>
      <form v-if="pending && canRetry()" @submit.prevent="submitStart">
        <h2>使用原操作号核查未确定的启动</h2>
        <p>当前仍为原 v0 初态。此操作只使用已保存的原 Key，不产生新 Key；仍应先核对审计。</p>
        <label><input v-model="retryConfirmed" type="checkbox" :disabled="writeBusy" />我已核对原操作和当前流程</label>
        <button type="submit" :disabled="busy || writeBusy || !retryConfirmed">使用原操作号重试</button>
      </form>
      <div v-if="pending && workflow && workflow.workflow_id === pending.workflow && workflow.etag !== pending.etag">
        <p>当前流程已变化。不能自动认定由本次操作造成；请核对审计后再清除原操作记录。</p>
        <label><input v-model="clearConfirmed" type="checkbox" :disabled="busy || writeBusy" />我已核对当前流程与审计</label>
        <button type="button" :disabled="busy || writeBusy || !clearConfirmed" @click="acknowledgeChanged">清除原操作记录</button>
      </div>
    </template>
  </section>
</template>
