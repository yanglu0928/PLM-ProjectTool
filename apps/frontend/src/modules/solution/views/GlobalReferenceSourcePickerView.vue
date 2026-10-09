<script setup lang="ts">
import { inject, onMounted, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink } from "vue-router";

import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { EvidenceListClient, type EvidenceSummary } from "@/modules/evidence/api/evidenceListClient";
import { EvidenceViewerClient, type EvidenceViewerDescriptor } from "@/modules/evidence/api/evidenceViewerClient";
import { EvidenceEligibilityClient } from "@/modules/evidence/api/evidenceEligibilityClient";
import { ReferenceDeidentificationClient, ReferenceDeidentificationError,
  type DeidentificationSources, type DeidentificationPreview,
  type DeidentificationConfirmation, type DeidentificationOperationStatus } from "@/modules/solution/api/referenceDeidentificationClient";
import { GlobalReferenceCreateClient, GlobalReferenceCreateError,
  type GlobalReferenceCreated } from "@/modules/solution/api/globalReferenceCreateClient";
import { GlobalReferenceReadClient, type GlobalReferenceCurrent } from "@/modules/solution/api/globalReferenceReadClient";
import { ReferenceReviseClient, type ReferenceRevised, type ReferenceReviseInput } from "@/modules/solution/api/referenceReviseClient";

const props = defineProps<{ referenceId?: string; session?: SessionClient; listClient?: EvidenceListClient;
  viewerClient?: EvidenceViewerClient; eligibilityClient?: EvidenceEligibilityClient;
  attestationClient?: ReferenceDeidentificationClient;
  createClient?: GlobalReferenceCreateClient; reader?: GlobalReferenceReadClient;
  reviseClient?: ReferenceReviseClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const lists = toRaw(props.listClient ?? new EvidenceListClient());
const viewers = toRaw(props.viewerClient ?? new EvidenceViewerClient());
const eligibility = toRaw(props.eligibilityClient ?? new EvidenceEligibilityClient(session));
const attestations = toRaw(props.attestationClient ?? new ReferenceDeidentificationClient(session));
const creates = toRaw(props.createClient ?? new GlobalReferenceCreateClient(session));
const reader = toRaw(props.reader ?? new GlobalReferenceReadClient());
const revises = toRaw(props.reviseClient ?? new ReferenceReviseClient(session));
type RevisePending = Readonly<{ actor: string; reference: string; key: string; ifMatch: string; body: string }>;
const revisionMode = () => typeof props.referenceId === "string" && props.referenceId.length > 0;
const target = ref<GlobalReferenceCurrent | null>(null);
const revised = ref<ReferenceRevised | null>(null);
const refreshed = ref<GlobalReferenceCurrent | null>(null);
const revisePending = ref<RevisePending | null>(null);
const revisePendingCorrupt = ref(false);
const reviseRecoveryReviewed = ref(false);
type Selected = Readonly<{ evidence: EvidenceSummary; viewer: EvidenceViewerDescriptor }>;
const items = ref<readonly EvidenceSummary[]>([]);
const selected = ref<readonly Selected[]>([]);
const cursor = ref<string | null>(null);
const loaded = ref(false);
const busy = ref(false);
const error = ref("");
const sourceClass = ref(""); const deidentificationClass = ref(""); const industry = ref("");
const preview = ref<DeidentificationPreview | null>(null);
const confirmation = ref<DeidentificationConfirmation | null>(null);
const openedDocuments = ref<readonly string[]>([]); const checkedDocuments = ref<readonly string[]>([]);
const openedEvidence = ref<readonly string[]>([]); const checkedEvidence = ref<readonly string[]>([]);
const attested = ref(false); const success = ref("");
const pendingKind = ref<"confirm" | "revoke" | null>(null); const pendingKey = ref("");
const lookupResult = ref<DeidentificationOperationStatus | null>(null);
const reviewedRecovery = ref(false);
const revokeReason = ref<"SOURCE_EXPOSED" | "SCOPE_CHANGED" | "ADMIN_REVIEW">("ADMIN_REVIEW");
const referenceName = ref(""); const createdReference = ref<GlobalReferenceCreated | null>(null);
const createPendingKey = ref("");
let generation = 0; let sourceRevision = 0; let mounted = true;
const mayRead = () => mounted && session.view?.deployment_role === "DEPLOYMENT_ADMIN"
  && !session.view.password_change_required;
const selectedIds = () => new Set(selected.value.map((entry) => entry.evidence.evidence_id));
const documentVersionIds = () => [...new Set(selected.value.map((entry) => entry.viewer.document_version_id))];
const documents = () => selected.value.filter((entry, index, all) =>
  all.findIndex((candidate) => candidate.viewer.document_version_id === entry.viewer.document_version_id) === index);
const storageKey = () => `plm.sol.global.deidentification.multi.pending.${session.view?.user.user_id ?? "none"}`;
const createStorageKey = () => `plm.sol.global.create.pending.${session.view?.user.user_id ?? "none"}`;
const reviseStorageKey = () => `plm.sol.global.reference.revise.pending.${session.view?.user.user_id ?? "none"}.${props.referenceId ?? "none"}`;
function restoreRevisePending() {
  revisePending.value = null; revisePendingCorrupt.value = false; reviseRecoveryReviewed.value = false;
  try {
    const raw = window.sessionStorage.getItem(reviseStorageKey());
    if (!raw) return;
    const item: unknown = JSON.parse(raw);
    if (!item || typeof item !== "object" || Array.isArray(item)) throw new Error("bad pending");
    const entry = item as Record<string, unknown>;
    if (Object.keys(entry).length !== 5 || entry.actor !== session.view?.user.user_id
      || entry.reference !== props.referenceId || typeof entry.key !== "string"
      || !/^[\x20-\x7e]{16,128}$/.test(entry.key) || typeof entry.ifMatch !== "string"
      || !/^"v(?:0|[1-9]\d*)"$/.test(entry.ifMatch) || typeof entry.body !== "string"
      || !entry.body) throw new Error("bad pending");
    revisePending.value = entry as RevisePending;
  } catch { revisePendingCorrupt.value = true; }
}
function saveRevisePending(item: RevisePending): boolean {
  try { window.sessionStorage.setItem(reviseStorageKey(), JSON.stringify(item)); revisePending.value = item; return true; }
  catch { error.value = "无法保存修订操作号，本次未提交。"; return false; }
}
function clearRevisePending(): boolean {
  try { window.sessionStorage.removeItem(reviseStorageKey()); revisePending.value = null;
    revisePendingCorrupt.value = false; reviseRecoveryReviewed.value = false; return true; }
  catch { error.value = "无法清除修订待核对记录，继续锁定新提交。"; return false; }
}
async function loadTarget() {
  if (!revisionMode() || !mayRead() || busy.value) return;
  const id = props.referenceId!, run = ++generation;
  busy.value = true; error.value = ""; target.value = null; revised.value = null; refreshed.value = null;
  try {
    const result = await reader.current(id);
    if (!mounted || run !== generation || id !== props.referenceId || !mayRead()) return;
    target.value = result;
    sourceClass.value = result.source_project_class;
    deidentificationClass.value = result.deidentification_class;
    industry.value = typeof result.applicability.industry === "string" ? result.applicability.industry : "";
    restoreRevisePending();
  } catch (failure) { if (mounted && run === generation) error.value = failure instanceof Error
    ? failure.message : "无法读取当前全局参考方案。"; }
  finally { if (mounted && run === generation) busy.value = false; }
}
function restoreCreatePending() {
  createPendingKey.value = "";
  try {
    const raw = window.sessionStorage.getItem(createStorageKey());
    if (!raw) return;
    const value: unknown = JSON.parse(raw);
    if (value && typeof value === "object" && !Array.isArray(value)) {
      const item = value as Record<string, unknown>;
      if (item.actor === session.view?.user.user_id && typeof item.key === "string"
        && /^[\x20-\x7e]{16,128}$/.test(item.key)
        && typeof item.request === "string" && item.request.length > 0) {
        createPendingKey.value = item.key; return;
      }
    }
  } catch { /* Corrupt storage remains locked. */ }
  createPendingKey.value = "无法读取";
}
function clearCreatePending(): boolean {
  try { window.sessionStorage.removeItem(createStorageKey()); }
  catch { error.value = "无法清除创建操作号，请停止提交。"; return false; }
  createPendingKey.value = ""; return true;
}
function clearPreview() {
  preview.value = null; confirmation.value = null; success.value = "";
  openedDocuments.value = []; checkedDocuments.value = [];
  openedEvidence.value = []; checkedEvidence.value = []; attested.value = false;
}
function invalidateSources() { sourceRevision += 1; clearPreview(); }
function sources(): DeidentificationSources | null {
  const source = sourceClass.value.trim(), classification = deidentificationClass.value.trim();
  if (selected.value.length < 2 || !/^[A-Z][A-Z0-9_]{1,63}$/.test(source)
    || !/^[A-Z][A-Z0-9_]{1,63}$/.test(classification)) return null;
  return { document_version_ids: documentVersionIds(),
    evidence_ids: selected.value.map((entry) => entry.evidence.evidence_id),
    source_project_class: source, deidentification_class: classification,
    applicability: industry.value.trim() ? { industry: industry.value.trim() } : {} };
}
function markOpened(kind: "document" | "evidence", id: string) {
  const target = kind === "document" ? openedDocuments : openedEvidence;
  if (!target.value.includes(id)) target.value = [...target.value, id];
}
function allChecked() {
  return documents().every((entry) => openedDocuments.value.includes(entry.viewer.document_version_id)
    && checkedDocuments.value.includes(entry.viewer.document_version_id))
    && selected.value.every((entry) => openedEvidence.value.includes(entry.evidence.evidence_id)
      && checkedEvidence.value.includes(entry.evidence.evidence_id));
}
function restorePending() {
  pendingKind.value = null; pendingKey.value = ""; lookupResult.value = null;
  try {
    const raw = window.sessionStorage.getItem(storageKey());
    if (!raw) return;
    const item: unknown = JSON.parse(raw);
    if (item && typeof item === "object" && !Array.isArray(item)) {
      const entry = item as Record<string, unknown>;
      if (entry.actor === session.view?.user.user_id
        && (entry.kind === "confirm" || entry.kind === "revoke")
        && typeof entry.key === "string" && /^[\x20-\x7e]{16,128}$/.test(entry.key)) {
        pendingKind.value = entry.kind; pendingKey.value = entry.key; return;
      }
    }
  } catch { /* Invalid storage closes write admission. */ }
  pendingKind.value = "confirm"; pendingKey.value = "无法读取";
}
function savePending(kind: "confirm" | "revoke", key: string): boolean {
  try {
    window.sessionStorage.setItem(storageKey(), JSON.stringify({ actor: session.view?.user.user_id,
      kind, key }));
    pendingKind.value = kind; pendingKey.value = key; return true;
  } catch { error.value = "无法保存原操作号，本次不提交。"; return false; }
}
function clearPending() {
  try { window.sessionStorage.removeItem(storageKey()); }
  catch { error.value = "无法清除本地待核对记录，请停止提交。"; return; }
  pendingKind.value = null; pendingKey.value = ""; lookupResult.value = null;
  reviewedRecovery.value = false;
}

async function load(refresh = false) {
  if (!mayRead() || busy.value || confirmation.value || !refresh && loaded.value && !cursor.value) return;
  if (refresh) {
    generation += 1; items.value = []; selected.value = []; cursor.value = null; loaded.value = false;
    invalidateSources();
  }
  const after = cursor.value, run = ++generation;
  busy.value = true; error.value = "";
  try {
    const page = await lists.list({ kind: "GLOBAL" }, after);
    if (!mounted || run !== generation || !mayRead()) return;
    if (page.items.some((item) => items.value.some((prior) => prior.evidence_id === item.evidence_id))) {
      throw new Error("duplicate Evidence in pagination");
    }
    items.value = [...items.value, ...page.items]; cursor.value = page.next_cursor; loaded.value = true;
  } catch {
    if (mounted && run === generation) error.value = "无法确认全局证据列表；请重新读取。";
  } finally { if (mounted && run === generation) busy.value = false; }
}

async function choose(item: EvidenceSummary) {
  if (!mayRead() || busy.value || confirmation.value || item.eligibility_state !== "ELIGIBLE"
    || selectedIds().has(item.evidence_id)
    || !items.value.some((candidate) => candidate.evidence_id === item.evidence_id)
    || selected.value.length >= 500) return;
  const run = ++generation;
  busy.value = true; error.value = "";
  try {
    const viewer = await viewers.get({ kind: "GLOBAL" }, item.evidence_id);
    const state = await eligibility.currentGlobal(item.evidence_id);
    if (!mounted || run !== generation || !mayRead()) return;
    if (viewer.evidence_id !== item.evidence_id || viewer.document_id !== item.document_id
      || viewer.document_version_id !== item.document_version_id
      || state.evidence_id !== item.evidence_id || state.document_id !== viewer.document_id
      || state.document_version_id !== viewer.document_version_id
      || state.eligibility_state !== "ELIGIBLE"
      || documentVersionIds().length >= 100
        && !documentVersionIds().includes(viewer.document_version_id)) {
      throw new Error("source no longer eligible or exceeds limit");
    }
    selected.value = [...selected.value, { evidence: item, viewer }]; invalidateSources();
  } catch {
    if (mounted && run === generation) error.value = "固定来源已变化、不可用或超过集合限制；请刷新列表后重选。";
  } finally { if (mounted && run === generation) busy.value = false; }
}
function remove(evidenceId: string) {
  if (busy.value || confirmation.value) return;
  selected.value = selected.value.filter((entry) => entry.evidence.evidence_id !== evidenceId);
  invalidateSources(); error.value = "";
}
async function previewSources() {
  const input = sources();
  if (!mayRead() || !input || busy.value || pendingKind.value) return;
  const run = generation, revision = sourceRevision;
  clearPreview(); error.value = ""; busy.value = true;
  try {
    for (const entry of selected.value) {
      const viewer = await viewers.get({ kind: "GLOBAL" }, entry.evidence.evidence_id);
      const state = await eligibility.currentGlobal(entry.evidence.evidence_id);
      if (viewer.evidence_id !== entry.evidence.evidence_id
        || viewer.document_id !== entry.viewer.document_id
        || viewer.document_version_id !== entry.viewer.document_version_id
        || viewer.content_url !== entry.viewer.content_url
        || state.evidence_id !== entry.evidence.evidence_id
        || state.document_id !== viewer.document_id
        || state.document_version_id !== viewer.document_version_id
        || state.eligibility_state !== "ELIGIBLE") throw new Error("source changed");
    }
    const result = await attestations.preview(input);
    if (!mounted || run !== generation || revision !== sourceRevision) return;
    if (result.document_refs.length !== input.document_version_ids.length
      || result.document_refs.some((entry, index) =>
        entry.document_version_id !== input.document_version_ids[index]
        || entry.document_id !== documents()[index]?.viewer.document_id)
      || result.evidence_ids.length !== input.evidence_ids.length
      || result.evidence_ids.some((id, index) => id !== input.evidence_ids[index])) {
      throw new Error("preview identity mismatch");
    }
    preview.value = result;
  } catch (failure) {
    if (mounted && run === generation) error.value = failure instanceof ReferenceDeidentificationError
      ? failure.message : "来源已变化或预览身份不一致；请重新读取并逐项核查。";
  } finally { if (mounted && run === generation) busy.value = false; }
}
async function confirm() {
  const input = sources(), shown = preview.value;
  if (!mayRead() || !input || !shown || !allChecked() || !attested.value
    || !session.canSubmit || busy.value || pendingKind.value) return;
  const run = generation, revision = sourceRevision, key = crypto.randomUUID();
  if (!savePending("confirm", key)) return;
  busy.value = true; error.value = "";
  try {
    const expiry = new Date(Date.now() + 7 * 86_400_000).toISOString();
    const result = await attestations.confirm(input, shown.source_fingerprint, expiry, key);
    if (!mounted || run !== generation || revision !== sourceRevision) return;
    confirmation.value = result; clearPending();
    success.value = "集合人工确认已提交；不会自动创建全局参考方案。";
  } catch (failure) {
    if (!mounted || run !== generation || revision !== sourceRevision) return;
    if (failure instanceof ReferenceDeidentificationError && failure.code === "SOURCE_SNAPSHOT_CHANGED") {
      clearPending(); clearPreview();
    }
    error.value = failure instanceof Error ? failure.message : "提交结果不确定，请保留原操作号。";
  } finally { if (mounted) busy.value = false; }
}
async function createReference() {
  const input = sources(), shown = preview.value, proof = confirmation.value;
  const name = referenceName.value.trim();
  if (!mayRead() || !session.canSubmit || busy.value || pendingKind.value
    || createPendingKey.value || createdReference.value || !input || !shown || !proof
    || proof.source_fingerprint !== shown.source_fingerprint
    || Date.parse(proof.expires_at) <= Date.now() || !name || name.length > 255) return;
  const run = generation, revision = sourceRevision;
  busy.value = true; error.value = "";
  try {
    for (const entry of selected.value) {
      const viewer = await viewers.get({ kind: "GLOBAL" }, entry.evidence.evidence_id);
      const state = await eligibility.currentGlobal(entry.evidence.evidence_id);
      if (viewer.evidence_id !== entry.evidence.evidence_id
        || viewer.document_id !== entry.viewer.document_id
        || viewer.document_version_id !== entry.viewer.document_version_id
        || viewer.content_url !== entry.viewer.content_url
        || state.evidence_id !== entry.evidence.evidence_id
        || state.document_id !== viewer.document_id
        || state.document_version_id !== viewer.document_version_id
        || state.eligibility_state !== "ELIGIBLE") throw new Error("source changed");
    }
    const refreshed = await attestations.preview(input);
    if (!mounted || run !== generation || revision !== sourceRevision) return;
    if (refreshed.source_fingerprint !== shown.source_fingerprint
      || refreshed.document_refs.length !== input.document_version_ids.length
      || refreshed.document_refs.some((item, index) =>
        item.document_version_id !== input.document_version_ids[index]
        || item.document_id !== documents()[index]?.viewer.document_id)
      || refreshed.evidence_ids.length !== input.evidence_ids.length
      || refreshed.evidence_ids.some((id, index) => id !== input.evidence_ids[index])) {
      throw new Error("source changed");
    }
    const request = { name, ...input }, key = crypto.randomUUID();
    try {
      window.sessionStorage.setItem(createStorageKey(), JSON.stringify({
        actor: session.view?.user.user_id, key, request: JSON.stringify(request),
      }));
      createPendingKey.value = key;
    } catch { error.value = "无法保存创建操作号，本次不提交。"; return; }
    try {
      const result = await creates.create(request, key);
      if (!mounted || run !== generation || revision !== sourceRevision) return;
      createdReference.value = result;
      if (clearCreatePending()) success.value = "全局参考方案已创建为仅供参考的草稿；并非正式批准方案。";
    } catch (failure) {
      if (!mounted || run !== generation || revision !== sourceRevision) return;
      if (failure instanceof GlobalReferenceCreateError
        && ["RESOURCE_NOT_FOUND", "AUTH_CSRF_INVALID", "AUTH_SESSION_EXPIRED",
          "LICENSE_OPERATION_DENIED", "VALIDATION_FAILED"].includes(failure.code)) {
        clearCreatePending(); clearPreview();
      }
      error.value = failure instanceof Error ? failure.message : "创建结果不确定，保留原操作号。";
    }
  } catch {
    if (mounted && run === generation) {
      clearPreview(); error.value = "来源或预览已变化，请重新读取并核查。";
    }
  } finally { if (mounted) busy.value = false; }
}
async function recheckRevise(input: ReferenceReviseInput, shown: DeidentificationPreview,
  snapshot: GlobalReferenceCurrent) {
  const latest = await reader.current(snapshot.reference_solution_id);
  if (latest.reference_version_id !== snapshot.reference_version_id || latest.etag !== snapshot.etag)
    throw new Error("当前全局参考版本已变化；请重新读取后决定。");
  for (const entry of selected.value) {
    const viewer = await viewers.get({ kind: "GLOBAL" }, entry.evidence.evidence_id);
    const state = await eligibility.currentGlobal(entry.evidence.evidence_id);
    if (viewer.evidence_id !== entry.evidence.evidence_id
      || viewer.document_id !== entry.viewer.document_id
      || viewer.document_version_id !== entry.viewer.document_version_id
      || viewer.content_url !== entry.viewer.content_url
      || state.evidence_id !== entry.evidence.evidence_id
      || state.document_id !== viewer.document_id
      || state.document_version_id !== viewer.document_version_id
      || state.eligibility_state !== "ELIGIBLE") throw new Error("固定来源已变化；请重新核查。");
  }
  const currentPreview = await attestations.preview(input);
  if (currentPreview.source_fingerprint !== shown.source_fingerprint
    || currentPreview.document_refs.length !== input.document_version_ids.length
    || currentPreview.document_refs.some((item, index) =>
      item.document_version_id !== input.document_version_ids[index]
      || item.document_id !== documents()[index]?.viewer.document_id)
    || currentPreview.evidence_ids.length !== input.evidence_ids.length
    || currentPreview.evidence_ids.some((id, index) => id !== input.evidence_ids[index]))
    throw new Error("来源指纹已变化；请重新预览并核查。");
}
async function sendRevise(item: RevisePending) {
  if (!revisionMode() || !mayRead() || !session.canSubmit || busy.value || revisePendingCorrupt.value) return;
  const run = generation;
  busy.value = true; error.value = "";
  try {
    const input = JSON.parse(item.body) as ReferenceReviseInput;
    const result = await revises.revise("GLOBAL", item.reference, null, input, item.ifMatch, item.key);
    if (!mounted || run !== generation || item.reference !== props.referenceId) return;
    revised.value = result;
    if (!clearRevisePending()) return;
    try { refreshed.value = await reader.current(item.reference); }
    catch { refreshed.value = null; error.value = "修订回执已收到，但当前详情刷新失败；请重新读取。"; }
  } catch (failure) { if (mounted && run === generation) error.value = failure instanceof Error
    ? failure.message : "修订结果不确定，请保留原操作号。"; }
  finally { if (mounted && run === generation) busy.value = false; }
}
async function submitRevise() {
  const input = sources(), shown = preview.value, proof = confirmation.value, snapshot = target.value;
  if (!revisionMode() || !mayRead() || !session.canSubmit || busy.value || pendingKind.value
    || revisePending.value || revisePendingCorrupt.value || revised.value || !input || !shown || !proof || !snapshot
    || proof.source_fingerprint !== shown.source_fingerprint || Date.parse(proof.expires_at) <= Date.now()
    || !allChecked() || !attested.value) return;
  const run = generation, revision = sourceRevision;
  busy.value = true; error.value = "";
  try {
    await recheckRevise(input, shown, snapshot);
    if (!mounted || run !== generation || revision !== sourceRevision || !mayRead()) return;
    const item: RevisePending = { actor: session.view!.user.user_id, reference: snapshot.reference_solution_id,
      key: crypto.randomUUID(), ifMatch: snapshot.etag, body: JSON.stringify(input) };
    if (!saveRevisePending(item)) return;
  } catch (failure) { if (mounted && run === generation) error.value = failure instanceof Error
    ? failure.message : "修订来源无法重新核验。"; }
  finally { if (mounted && run === generation) busy.value = false; }
  if (revisePending.value) await sendRevise(revisePending.value);
}
async function revoke() {
  const target = confirmation.value?.confirmation_id;
  if (!mayRead() || !target || !session.canSubmit || busy.value || pendingKind.value) return;
  const key = crypto.randomUUID();
  if (!savePending("revoke", key)) return;
  busy.value = true; error.value = "";
  try {
    await attestations.revoke(target, revokeReason.value, key);
    if (!mounted) return;
    clearPending(); clearPreview(); success.value = "集合确认已撤回；历史记录保留。";
  } catch (failure) { if (mounted) error.value = failure instanceof Error ? failure.message : "撤回结果不确定，请保留原操作号。"; }
  finally { if (mounted) busy.value = false; }
}
async function lookupPending() {
  const kind = pendingKind.value, key = pendingKey.value;
  if (!mayRead() || !kind || !/^[\x20-\x7e]{16,128}$/.test(key) || busy.value) return;
  busy.value = true; error.value = ""; lookupResult.value = null;
  try { lookupResult.value = await attestations.lookup(kind === "confirm" ? "CONFIRM" : "REVOKE", key); }
  catch (failure) { if (mounted) error.value = failure instanceof Error ? failure.message : "无法核对原操作。"; }
  finally { if (mounted) busy.value = false; }
}
function clearCompletedPending() {
  if (lookupResult.value?.status !== "COMPLETED" || !reviewedRecovery.value) return;
  const result = lookupResult.value;
  clearPending(); success.value = `已核对历史操作 ${result.confirmation_id}；当前状态 ${result.current_state}。`;
}
watch([sourceClass, deidentificationClass, industry], invalidateSources);
watch(() => props.referenceId, () => {
  generation += 1; busy.value = false; items.value = []; selected.value = []; cursor.value = null;
  loaded.value = false; target.value = null; revised.value = null; refreshed.value = null;
  revisePending.value = null; revisePendingCorrupt.value = false; createPendingKey.value = "";
  clearPreview(); error.value = "";
  if (revisionMode()) { restoreRevisePending(); void loadTarget().then(() => load(true)); }
  else { restoreCreatePending(); void load(true); }
});
onMounted(() => {
  restorePending();
  if (revisionMode()) { restoreRevisePending(); void loadTarget().then(() => load(true)); }
  else { restoreCreatePending(); void load(true); }
});
onUnmounted(() => { mounted = false; generation += 1; selected.value = []; });
</script>

<template>
  <section class="global-source-picker" aria-labelledby="picker-title" :aria-busy="busy">
    <p class="section-kicker">全局参考方案</p>
    <h1 id="picker-title">{{ revisionMode() ? '修订全局参考方案' : '多来源核查候选' }}</h1>
    <p><RouterLink :to="{ name: 'global-references' }">查看全局参考方案候选与历史详情</RouterLink></p>
    <p v-if="revisionMode() && target">目标：{{ target.name }} · 当前第 {{ target.version_no }} 版 ·
      当前 ETag <code>{{ target.etag }}</code>。修订只生成新草稿版本，原版本保留。
      <RouterLink :to="{ name: 'global-reference-detail', params: { referenceId: target.reference_solution_id } }">返回目标详情</RouterLink>
    </p>
    <p>仅部署管理员可选择。候选集合本身不是脱敏确认；预览后仍须逐项打开原文并由本人判断，AI 和脚本不能代替业务确认。</p>
    <p><RouterLink to="/admin/evidence">返回全局证据</RouterLink></p>
    <template v-if="!mayRead()">
      <p role="status">需要当前 DeploymentAdmin 登录且已完成密码设置。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else>
      <button type="button" :disabled="busy || !!confirmation" @click="load(true)">重新读取并清空候选</button>
      <p v-if="success" role="status">{{ success }}</p>
      <section v-if="pendingKind" aria-label="待核对集合操作">
        <strong>上次{{ pendingKind === 'confirm' ? '确认' : '撤回' }}结果尚待核对</strong>
        <p>原操作号：<code>{{ pendingKey }}</code>。不要换号或自动重试。</p>
        <button type="button" :disabled="busy || pendingKey === '无法读取'" @click="lookupPending()">按原操作号回查</button>
        <p v-if="lookupResult?.status === 'UNCONFIRMED'" role="status">尚不能确认首次操作是否提交，继续锁定。</p>
        <template v-if="lookupResult?.status === 'COMPLETED'">
          <p role="status">首次操作已完成：{{ lookupResult.confirmation_id }}；当前状态 {{ lookupResult.current_state }}。</p>
          <label><input v-model="reviewedRecovery" type="checkbox"> 我已核对首次结果与当前状态</label>
          <button type="button" :disabled="busy || !reviewedRecovery" @click="clearCompletedPending()">清除本地待核对提醒</button>
        </template>
      </section>
      <section v-if="createPendingKey" aria-label="待核对创建操作">
        <strong>全局参考方案创建结果尚待核对</strong>
        <p>原操作号：<code>{{ createPendingKey }}</code>。当前合同无创建回查入口；不要换号、刷新重试或再次创建，须核对服务端审计后处理。</p>
      </section>
      <section v-if="revisionMode() && (revisePending || revisePendingCorrupt)" aria-label="待核对修订操作">
        <strong>全局参考方案修订结果待核对</strong>
        <p v-if="revisePendingCorrupt" role="alert">本地原请求记录损坏，禁止提交；需人工核对服务端审计与当前版本。</p>
        <template v-else-if="revisePending">
          <p>原操作号：<code>{{ revisePending.key }}</code>；原 If-Match：<code>{{ revisePending.ifMatch }}</code>。
            请先核对审计和当前详情；若首次请求无明确回执，只能以保存的原正文、ETag、操作号重试。</p>
          <button type="button" :disabled="busy || !session.canSubmit" @click="sendRevise(revisePending)">原请求同号重试</button>
          <label><input v-model="reviseRecoveryReviewed" type="checkbox">我已核对服务端审计和当前版本，确认不需再重试原请求</label>
          <button type="button" :disabled="busy || !reviseRecoveryReviewed" @click="clearRevisePending()">清除本地待核对记录</button>
        </template>
      </section>
      <p v-if="busy" role="status">正在核验来源…</p>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="loaded && !items.length">暂无全局证据。</p>
      <ol aria-label="可选全局证据">
        <li v-for="item in items" :key="item.evidence_id">
          {{ item.display_label }} · {{ item.eligibility_state === 'ELIGIBLE' ? '当前列表显示可用' : '当前列表不可选' }}
          <button type="button" :disabled="busy || !!confirmation || item.eligibility_state !== 'ELIGIBLE'
            || selectedIds().has(item.evidence_id) || selected.length >= 500"
            @click="choose(item)">加入核查候选</button>
        </li>
      </ol>
      <button v-if="cursor" type="button" :disabled="busy" @click="load()">继续加载</button>
      <section aria-labelledby="selected-title">
        <h2 id="selected-title">待逐项核查的来源（{{ selected.length }} 条证据、{{ documentVersionIds().length }} 个固定文档版本）</h2>
        <p>选择顺序保留；相同固定文档版本只计一次。当前选择不是预览证明或人工确认，重新读取会清空。</p>
        <ol aria-label="已选固定来源">
          <li v-for="entry in selected" :key="entry.evidence.evidence_id">
            <strong>{{ entry.viewer.display_label }}</strong> · 第 {{ entry.viewer.document_version_no }} 版 ·
            {{ entry.viewer.precision === 'DOCUMENT' ? '整文档' : '解析节点' }}
            <a :href="entry.viewer.content_url" target="_blank" rel="noopener">打开受权固定版本原文</a>
            <button type="button" :disabled="busy || !!confirmation" @click="remove(entry.evidence.evidence_id)">移出候选</button>
          </li>
        </ol>
      </section>
      <section aria-labelledby="multi-preview-title">
        <h2 id="multi-preview-title">集合预览与逐项核查</h2>
        <p>至少选择两条证据。分类和集合发生变化后，旧预览及勾选全部失效；服务端会在确认时重新计算来源指纹。</p>
        <label>来源项目分类（如 PLM）<input v-model="sourceClass" :disabled="busy || !!confirmation" maxlength="64" placeholder="PLM"></label>
        <label>脱敏分类（按实际核查填写）<input v-model="deidentificationClass" :disabled="busy || !!confirmation" maxlength="64" placeholder="DEIDENTIFIED"></label>
        <label>适用行业（可选）<input v-model="industry" :disabled="busy || !!confirmation" maxlength="128" placeholder="例如：离散制造"></label>
        <button type="button" :disabled="busy || !!pendingKind || !!confirmation || !sources()" @click="previewSources()">预览所选来源集合</button>
      </section>
      <section v-if="preview" aria-label="集合预览与逐项原文核查">
        <p>预览时刻：{{ preview.previewed_at }}；来源指纹：<code>{{ preview.source_fingerprint }}</code></p>
        <h3>固定文档版本（{{ documents().length }} 个）</h3>
        <ol><li v-for="entry in documents()" :key="entry.viewer.document_version_id">
          第 {{ entry.viewer.document_version_no }} 版 · {{ entry.viewer.display_label }}
          <a :href="entry.viewer.content_url" target="_blank" rel="noopener"
            @click="markOpened('document', entry.viewer.document_version_id)">打开固定文档版本原文</a>
          <label><input v-model="checkedDocuments" type="checkbox" :value="entry.viewer.document_version_id"
            :disabled="busy || !openedDocuments.includes(entry.viewer.document_version_id)">我已打开并检查此文档版本</label>
        </li></ol>
        <h3>固定证据（{{ selected.length }} 条）</h3>
        <ol><li v-for="entry in selected" :key="entry.evidence.evidence_id">
          {{ entry.viewer.display_label }} · {{ entry.viewer.precision === 'DOCUMENT' ? '整文档' : '解析节点' }}
          <a :href="entry.viewer.content_url" target="_blank" rel="noopener"
            @click="markOpened('evidence', entry.evidence.evidence_id)">打开证据对应原文</a>
          <label><input v-model="checkedEvidence" type="checkbox" :value="entry.evidence.evidence_id"
            :disabled="busy || !openedEvidence.includes(entry.evidence.evidence_id)">我已核对该证据位置和原文</label>
        </li></ol>
        <label><input v-model="attested" type="checkbox" :disabled="busy">
          我本人已逐项核查全部固定来源，确认符合所填脱敏分类；不是 AI 代替我判断</label>
        <button type="button" :disabled="busy || !!pendingKind || !session.canSubmit || !allChecked() || !attested || !!confirmation"
          @click="confirm()">提交集合人工脱敏确认（有效期 7 天）</button>
      </section>
      <section v-if="confirmation" aria-label="集合历史确认">
        <p>历史确认号：<code>{{ confirmation.confirmation_id }}</code>；到期：{{ confirmation.expires_at }}</p>
        <p>这只是本会话历史确认，不代表当前未撤回或来源仍合格；创建时服务端会重新证明。</p>
        <section v-if="!revisionMode() && !createdReference" aria-label="创建全局参考方案">
          <label>参考方案名称<input v-model="referenceName" :disabled="busy || !!createPendingKey" maxlength="255" placeholder="填写便于识别的参考名称"></label>
          <button type="button" :disabled="busy || !!pendingKind || !!createPendingKey || !session.canSubmit
            || !referenceName.trim() || Date.parse(confirmation.expires_at) <= Date.now()"
            @click="createReference()">重新核验并创建全局参考方案</button>
        </section>
        <p v-if="!revisionMode() && createdReference" role="status">已创建参考方案 {{ createdReference.reference_solution_id }}，状态仅供参考 / 草稿；不是正式方案批准。
          <RouterLink :to="{ name: 'global-reference-detail', params: { referenceId: createdReference.reference_solution_id } }">打开刚创建的参考方案详情</RouterLink>
        </p>
        <section v-if="revisionMode()" aria-label="修订全局参考方案">
          <p>提交前重新读取目标当前版和全部固定来源，并重新计算脱敏指纹。人工确认只是历史记录，服务端还会证明它当前有效。</p>
          <button type="button" :disabled="busy || !!pendingKind || !!revisePending || revisePendingCorrupt
            || !!revised || !target || !session.canSubmit || Date.parse(confirmation.expires_at) <= Date.now()"
            @click="submitRevise()">重新核验并修订为新草稿版本</button>
        </section>
        <label>撤回原因<select v-model="revokeReason"><option value="ADMIN_REVIEW">管理员复核</option>
          <option value="SOURCE_EXPOSED">来源暴露</option><option value="SCOPE_CHANGED">范围变化</option></select></label>
        <button type="button" :disabled="busy || !!pendingKind || !session.canSubmit" @click="revoke()">撤回此集合确认</button>
      </section>
      <p v-if="revisionMode() && revised" role="status">修订回执：第 {{ revised.version_no }} 版，版本号 {{ revised.reference_version_id }}；
        {{ refreshed?.reference_version_id === revised.reference_version_id ? '当前详情已确认指向该版本。' : '当前详情尚未确认，请单独读取。' }}
      </p>
    </template>
  </section>
</template>

<style scoped>
.global-source-picker { max-width: 66rem; margin: 1rem auto; padding: 1.5rem; background: #fff; border-radius: 1rem; }
li { padding: .55rem 0; line-height: 1.6; }
button, a { margin-left: .6rem; }
button:disabled { opacity: .55; cursor: not-allowed; }
[role="alert"] { color: #a21d25; }
</style>
