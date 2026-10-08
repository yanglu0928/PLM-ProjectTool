<script setup lang="ts">
import { inject, onMounted, onUnmounted, ref, toRaw } from "vue";
import { RouterLink } from "vue-router";

import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { EvidenceListClient, EvidenceListError, type EvidenceSummary } from "@/modules/evidence/api/evidenceListClient";
import { EvidenceViewerClient, EvidenceViewerClientError,
  type EvidenceViewerDescriptor } from "@/modules/evidence/api/evidenceViewerClient";
import { EvidenceEligibilityClient, EvidenceEligibilityClientError,
  type CurrentEvidenceEligibility, type EvidenceEligibilityFirstReceipt } from "@/modules/evidence/api/evidenceEligibilityClient";
import { EvidenceEligibilityOperationLookupClient, EvidenceEligibilityOperationLookupError,
  type EvidenceEligibilityOperationLookup } from "@/modules/evidence/api/evidenceEligibilityOperationLookupClient";

const props = defineProps<{ session?: SessionClient; listClient?: EvidenceListClient;
  viewerClient?: EvidenceViewerClient; eligibilityClient?: EvidenceEligibilityClient;
  eligibilityLookupClient?: EvidenceEligibilityOperationLookupClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const lists = toRaw(props.listClient ?? new EvidenceListClient());
const viewers = toRaw(props.viewerClient ?? new EvidenceViewerClient());
const eligibility = toRaw(props.eligibilityClient ?? new EvidenceEligibilityClient(session));
const eligibilityLookup = toRaw(props.eligibilityLookupClient ?? new EvidenceEligibilityOperationLookupClient(session));
const actorId = session.view?.user.user_id;
const items = ref<readonly EvidenceSummary[]>([]);
const cursor = ref<string | null>(null);
const loaded = ref(false);
const busy = ref(false);
const error = ref("");
const selected = ref<EvidenceViewerDescriptor | null>(null);
const current = ref<CurrentEvidenceEligibility | null>(null);
const selectedBusy = ref(false);
const selectedError = ref("");
type GlobalPendingDecision = { actorId: string; evidenceId: string; key: string };
const pendingStorageKey = actorId ? `plm.evidence.global.eligibility.pending.${actorId}` : "";
const pendingId = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const pendingStorageError = ref(false);
function pendingRecord(value: unknown): value is GlobalPendingDecision {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const entry = value as Record<string, unknown>;
  return entry.actorId === actorId && typeof entry.evidenceId === "string"
    && pendingId.test(entry.evidenceId) && typeof entry.key === "string"
    && /^[\x20-\x7e]{16,128}$/.test(entry.key);
}
function readPending(): GlobalPendingDecision | null {
  if (!pendingStorageKey) return null;
  try {
    const saved = window.sessionStorage.getItem(pendingStorageKey);
    if (saved === null) return null;
    const parsed: unknown = JSON.parse(saved);
    if (pendingRecord(parsed)) return parsed;
  } catch { /* Invalid or inaccessible storage must close write admission. */ }
  pendingStorageError.value = true;
  return null;
}
const unresolved = ref<GlobalPendingDecision | null>(readPending());
const lookupResult = ref<EvidenceEligibilityOperationLookup | null>(null);
const lookupCurrent = ref<CurrentEvidenceEligibility | null>(null);
const lookupBusy = ref(false);
const lookupError = ref("");
let lookupGeneration = 0;
function clearLookup() {
  lookupGeneration += 1; lookupResult.value = null; lookupCurrent.value = null;
  lookupBusy.value = false; lookupError.value = "";
}
async function lookupPending() {
  const pending = unresolved.value;
  if (!mayRead() || !pending || pending.actorId !== actorId
    || pendingStorageError.value || lookupBusy.value) return;
  clearLookup();
  const request = ++lookupGeneration;
  lookupBusy.value = true;
  try {
    const result = await eligibilityLookup.lookupGlobal(pending.evidenceId, pending.key);
    if (!mounted || request !== lookupGeneration || unresolved.value !== pending || !mayRead()) return;
    if (result.status === "COMPLETED") {
      const state = await eligibility.currentGlobal(pending.evidenceId);
      if (!mounted || request !== lookupGeneration || unresolved.value !== pending
        || !mayRead() || state.evidence_id !== pending.evidenceId) return;
      lookupCurrent.value = state;
    }
    lookupResult.value = result;
  } catch (failure) {
    if (mounted && request === lookupGeneration) {
      lookupError.value = failure instanceof EvidenceEligibilityOperationLookupError
        || failure instanceof EvidenceEligibilityClientError
        ? failure.message : "暂时无法核对原操作；请保留操作号，不要重新提交。";
    }
  } finally { if (mounted && request === lookupGeneration) lookupBusy.value = false; }
}
function confirmLookup() {
  const pending = unresolved.value;
  if (!pending || !mayRead() || pendingStorageError.value || lookupBusy.value
    || lookupResult.value?.status !== "COMPLETED"
    || lookupResult.value.evidence_id !== pending.evidenceId
    || lookupCurrent.value?.evidence_id !== pending.evidenceId) return;
  if (!clearPending(pending)) {
    lookupError.value = "无法清除待核对操作；请保留原操作号并检查浏览器会话存储。";
    return;
  }
  clearLookup();
}
function savePending(value: GlobalPendingDecision): boolean {
  if (!pendingStorageKey || pendingStorageError.value || unresolved.value) return false;
  try {
    const encoded = JSON.stringify(value);
    window.sessionStorage.setItem(pendingStorageKey, encoded);
    if (window.sessionStorage.getItem(pendingStorageKey) !== encoded) {
      pendingStorageError.value = true; return false;
    }
    unresolved.value = value; return true;
  } catch { pendingStorageError.value = true; return false; }
}
function clearPending(value: GlobalPendingDecision): boolean {
  if (!pendingStorageKey) return false;
  try {
    if (window.sessionStorage.getItem(pendingStorageKey) !== JSON.stringify(value)) {
      pendingStorageError.value = true; return false;
    }
    window.sessionStorage.removeItem(pendingStorageKey);
    unresolved.value = null; return true;
  } catch { pendingStorageError.value = true; return false; }
}
const decisionTarget = ref<"ELIGIBLE" | "INELIGIBLE" | null>(null);
const decisionReason = ref("");
const decisionAttested = ref(false);
const decisionBusy = ref(false);
const decisionError = ref("");
const decisionReceipt = ref<EvidenceEligibilityFirstReceipt | null>(null);
let mounted = true;
let generation = 0;
let selectionGeneration = 0;

function mayRead(): boolean {
  return mounted && !!actorId && session.view?.user.user_id === actorId
    && session.view.deployment_role === "DEPLOYMENT_ADMIN"
    && !session.view.password_change_required;
}
function clearSelection() {
  selectionGeneration += 1; selected.value = null; current.value = null;
  selectedBusy.value = false; selectedError.value = "";
  decisionTarget.value = null; decisionReason.value = ""; decisionAttested.value = false;
  decisionBusy.value = false; decisionError.value = ""; decisionReceipt.value = null;
  clearLookup();
}
function mayDecide(): boolean {
  return mayRead() && !!selected.value && current.value?.evidence_id === selected.value.evidence_id
    && current.value.eligibility_state === "CANDIDATE"
    && !unresolved.value && !pendingStorageError.value && !decisionReceipt.value;
}
async function submitDecision() {
  const view = selected.value;
  const before = current.value;
  const target = decisionTarget.value;
  const justification = decisionReason.value;
  if (!mayDecide() || !view || !before || !target || !decisionAttested.value
    || decisionBusy.value || !session.canSubmit) return;
  const request = selectionGeneration;
  const pending = { actorId: actorId!, evidenceId: before.evidence_id, key: crypto.randomUUID() };
  if (!savePending(pending)) {
    decisionError.value = "无法安全保存本次操作号，资格请求未发送；请检查浏览器会话存储。";
    return;
  }
  decisionBusy.value = true; decisionError.value = "";
  try {
    const receipt = await eligibility.setGlobal(before, view, target, justification, pending.key);
    if (!mounted || request !== selectionGeneration || !mayRead() || selected.value !== view) return;
    if (!clearPending(pending)) {
      decisionError.value = "已收到提交回执，但待核对记录无法清除；请保留操作号并核对当前资格。";
      return;
    }
    current.value = null; decisionReceipt.value = receipt;
  } catch (failure) {
    if (mounted && request === selectionGeneration) {
      decisionError.value = failure instanceof EvidenceEligibilityClientError
        ? failure.message : "资格提交结果暂无法确认；请保留操作号。";
      if (failure instanceof EvidenceEligibilityClientError
        && failure.code !== "EVIDENCE_ELIGIBILITY_UNCERTAIN") {
        if (!clearPending(pending)) {
          decisionError.value = "拒绝结果已返回，但无法清除待核对记录；请保留操作号。";
        }
      }
    }
  } finally { if (mounted && request === selectionGeneration) decisionBusy.value = false; }
}
async function load(refresh = false) {
  if (!mayRead() || busy.value || !refresh && loaded.value && !cursor.value) return;
  if (refresh) { generation += 1; items.value = []; cursor.value = null; loaded.value = false;
    clearSelection(); }
  const after = cursor.value;
  const request = ++generation;
  busy.value = true; error.value = "";
  try {
    const page = await lists.list({ kind: "GLOBAL" }, after);
    if (!mounted || request !== generation || !mayRead()) return;
    const previous = after ? items.value : [];
    if (page.items.some((entry) => previous.some((older) => older.evidence_id === entry.evidence_id))) {
      throw new EvidenceListError("EVIDENCE_LIST_UNAVAILABLE");
    }
    items.value = [...previous, ...page.items]; cursor.value = page.next_cursor;
    loaded.value = true;
  } catch (failure) {
    if (mounted && request === generation) {
      error.value = failure instanceof EvidenceListError ? failure.message : "暂时无法读取全局证据。";
    }
  } finally { if (mounted && request === generation) busy.value = false; }
}
async function locate(item: EvidenceSummary) {
  if (!mayRead() || selectedBusy.value
    || !items.value.some((entry) => entry.evidence_id === item.evidence_id)) return;
  clearSelection();
  const request = ++selectionGeneration;
  selectedBusy.value = true;
  try {
    const view = await viewers.get({ kind: "GLOBAL" }, item.evidence_id);
    if (!mounted || request !== selectionGeneration || !mayRead()) return;
    if (view.document_id !== item.document_id
      || view.document_version_id !== item.document_version_id) {
      throw new EvidenceViewerClientError("EVIDENCE_CLIENT_UNAVAILABLE");
    }
    const state = await eligibility.currentGlobal(item.evidence_id);
    if (!mounted || request !== selectionGeneration || !mayRead()) return;
    if (state.document_id !== view.document_id
      || state.document_version_id !== view.document_version_id) {
      throw new EvidenceEligibilityClientError("EVIDENCE_ELIGIBILITY_UNCERTAIN");
    }
    selected.value = view; current.value = state;
  } catch (failure) {
    if (mounted && request === selectionGeneration) {
      selectedError.value = failure instanceof EvidenceViewerClientError
        || failure instanceof EvidenceEligibilityClientError
        ? failure.message : "暂时无法核验全局证据固定来源。";
    }
  } finally { if (mounted && request === selectionGeneration) selectedBusy.value = false; }
}
onMounted(() => { void load(true); });
onUnmounted(() => { mounted = false; generation += 1; clearSelection(); });
</script>

<template>
  <section class="global-evidence" aria-labelledby="global-evidence-title" :aria-busy="busy">
    <p class="section-kicker">全局资料</p>
    <h1 id="global-evidence-title">全局证据</h1>
    <p>仅部署管理员可读。短提示不是原文；定位时重新核验固定文档版本和当前资格。</p>
    <template v-if="!mayRead()">
      <p role="status">当前身份无权查看全局证据，或登录状态已变化。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else>
      <button type="button" :disabled="busy" @click="load(true)">刷新全局证据</button>
      <p v-if="pendingStorageError" role="alert">浏览器会话存储不可用或待核对记录无效；资格提交已关闭，避免丢失操作号。</p>
      <p v-if="unresolved" role="alert">一项 GLOBAL 资格操作结果尚未确认（证据 {{ unresolved.evidenceId }}，操作号 {{ unresolved.key }}）。
        请保留原操作号，勿换号重复提交。</p>
      <section v-if="unresolved" aria-label="GLOBAL 原操作号回查">
        <button type="button" :disabled="lookupBusy || pendingStorageError" @click="lookupPending()">
          {{ lookupBusy ? '正在回查原操作…' : '按原操作号回查' }}
        </button>
        <p v-if="lookupError" role="alert">{{ lookupError }}</p>
        <p v-if="lookupResult?.status === 'UNCONFIRMED'" role="status">
          尚不能确认原操作是否提交；请保留原操作号，勿换号重试，可稍后再次回查。
        </p>
        <template v-if="lookupResult?.status === 'COMPLETED' && lookupCurrent">
          <p role="status">原操作已有完成收据；这仅证明历史提交，不代表当前资格。</p>
          <p>受权重新读取的当前资格：{{ lookupCurrent.eligibility_state === 'ELIGIBLE' ? '可用'
            : lookupCurrent.eligibility_state === 'INELIGIBLE' ? '不可用'
            : lookupCurrent.eligibility_state === 'REVOKED' ? '已撤销' : '待核定' }}（{{ lookupCurrent.etag }}）。</p>
          <button type="button" @click="confirmLookup()">已核对当前资格，清除待核对提醒</button>
        </template>
      </section>
      <p v-if="busy" role="status">正在读取全局证据…</p>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="loaded && items.length === 0">暂无全局证据。</p>
      <ol v-if="items.length" aria-label="全局证据列表">
        <li v-for="item in items" :key="item.evidence_id">
          <strong>{{ item.display_label }}</strong> · {{ item.eligibility_state === 'CANDIDATE' ? '待核定'
            : item.eligibility_state === 'ELIGIBLE' ? '可用'
            : item.eligibility_state === 'INELIGIBLE' ? '不可用' : '已撤销' }}
          <p v-if="item.display_excerpt">{{ item.display_excerpt }}</p>
          <button type="button" :disabled="selectedBusy" @click="locate(item)">定位固定原文</button>
        </li>
      </ol>
      <button v-if="cursor" type="button" :disabled="busy" @click="load()">继续加载</button>
      <p v-if="selectedError" role="alert">{{ selectedError }}</p>
      <section v-if="selected && current" aria-label="已核验的全局证据">
        <h2>已核验的全局证据</h2>
        <p>固定文档第 {{ selected.document_version_no }} 版；位置：{{ selected.display_label }}。</p>
        <p>当前资格：{{ current.eligibility_state === 'ELIGIBLE' ? '可用'
          : current.eligibility_state === 'INELIGIBLE' ? '不可用'
          : current.eligibility_state === 'REVOKED' ? '已撤销' : '待核定' }}（{{ current.etag }}）。</p>
        <p>来源精度：{{ selected.precision === 'DOCUMENT' ? '整文档' : '解析节点' }}；此页不提供精确高亮。</p>
        <p><a :href="selected.content_url">下载受权固定版本原文</a></p>
        <p><RouterLink :to="{ name: 'global-reference-deidentification',
          params: { evidenceId: selected.evidence_id } }">对这条固定来源进行人工脱敏核查</RouterLink></p>
        <section v-if="mayDecide()" aria-label="GLOBAL 人工资格确认">
          <h3>人工核定全局证据资格</h3>
          <p>先核对固定版本原文。模板与 AI 建议不能自动成为正式业务事实；请写明实际核对依据。</p>
          <form @submit.prevent="submitDecision()">
            <fieldset :disabled="decisionBusy">
              <legend>资格结论</legend>
              <label><input v-model="decisionTarget" type="radio" value="ELIGIBLE"> 可用</label>
              <label><input v-model="decisionTarget" type="radio" value="INELIGIBLE"> 不可用</label>
            </fieldset>
            <label for="global-evidence-reason">人工确认理由</label>
            <textarea id="global-evidence-reason" v-model="decisionReason" maxlength="1024" rows="4"
              placeholder="写明固定原文中的具体依据以及可用或不可用原因。" />
            <label><input v-model="decisionAttested" type="checkbox"> 我已核对固定版本原文，以上是我的人工判断</label>
            <button type="submit" :disabled="decisionBusy || !decisionTarget || !decisionReason.trim()
              || !decisionAttested || !session.canSubmit">{{ decisionBusy ? '正在提交…' : '提交资格裁定' }}</button>
          </form>
        </section>
      </section>
      <p v-if="decisionReceipt" role="status">首次提交回执：{{ decisionReceipt.eligibility_state === 'ELIGIBLE' ? '可用' : '不可用' }}。
        回执不代表当前状态，请刷新列表核对。</p>
      <p v-if="decisionError" role="alert">{{ decisionError }}</p>
    </template>
  </section>
</template>

<style scoped>
.global-evidence { max-width: 48rem; margin: 1rem auto; padding: 1.5rem; background: #fff; border-radius: 1rem; }
.global-evidence li { margin-block: 1rem; overflow-wrap: anywhere; }
.global-evidence p { line-height: 1.6; }
.global-evidence [role="alert"] { color: #a21d25; }
</style>
