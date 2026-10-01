<script setup lang="ts">
import { inject, onMounted, onUnmounted, ref, toRaw } from "vue";
import { RouterLink } from "vue-router";

import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { EvidenceListClient, EvidenceListError, type EvidenceSummary } from "@/modules/evidence/api/evidenceListClient";
import { EvidenceViewerClient, EvidenceViewerClientError,
  type EvidenceViewerDescriptor } from "@/modules/evidence/api/evidenceViewerClient";
import { EvidenceEligibilityClient, EvidenceEligibilityClientError,
  type CurrentEvidenceEligibility } from "@/modules/evidence/api/evidenceEligibilityClient";

const props = defineProps<{ session?: SessionClient; listClient?: EvidenceListClient;
  viewerClient?: EvidenceViewerClient; eligibilityClient?: EvidenceEligibilityClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const lists = toRaw(props.listClient ?? new EvidenceListClient());
const viewers = toRaw(props.viewerClient ?? new EvidenceViewerClient());
const eligibility = toRaw(props.eligibilityClient ?? new EvidenceEligibilityClient(session));
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
      </section>
    </template>
  </section>
</template>

<style scoped>
.global-evidence { max-width: 48rem; margin: 1rem auto; padding: 1.5rem; background: #fff; border-radius: 1rem; }
.global-evidence li { margin-block: 1rem; overflow-wrap: anywhere; }
.global-evidence p { line-height: 1.6; }
.global-evidence [role="alert"] { color: #a21d25; }
</style>
