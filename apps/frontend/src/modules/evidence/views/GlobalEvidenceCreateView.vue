<script setup lang="ts">
import { inject, onMounted, onUnmounted, ref, shallowRef, toRaw } from "vue";
import { RouterLink } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { DocumentReadClient, DocumentReadError, type DocumentView,
  type DocumentVersionView } from "@/modules/document/api/documentReadClient";
import { GlobalEvidenceCreateClient, GlobalEvidenceCreateError, normalizeGlobalEvidenceCreate,
  type GlobalEvidenceCreateInput, type GlobalEvidenceCreateReceipt } from "@/modules/evidence/api/globalEvidenceCreateClient";

const props = defineProps<{ session?: SessionClient; documents?: DocumentReadClient;
  creator?: GlobalEvidenceCreateClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const documents = toRaw(props.documents ?? new DocumentReadClient());
const creator = toRaw(props.creator ?? new GlobalEvidenceCreateClient(session));
const actorId = session.view?.user.user_id;
interface Selected { readonly document: DocumentView; readonly version: DocumentVersionView; }
interface Pending { readonly actor: string; readonly input: GlobalEvidenceCreateInput; readonly key: string; }
const docs = ref<readonly DocumentView[]>([]); const docsCursor = ref<string | null>(null);
const docsLoaded = ref(false); const docsBusy = ref(false); const docsError = ref("");
const active = shallowRef<DocumentView | null>(null); const versions = ref<readonly DocumentVersionView[]>([]);
const versionsCursor = ref<string | null>(null); const versionsBusy = ref(false); const versionsError = ref("");
const selected = shallowRef<Selected | null>(null); const displayLabel = ref(""); const confirmed = ref(false);
const pending = ref<Pending | null>(null); const confirmRetry = ref(false);
const busy = ref(false); const error = ref(""); const locked = ref(false);
const created = shallowRef<GlobalEvidenceCreateReceipt | null>(null);
let mounted = true; let docsGeneration = 0; let versionsGeneration = 0;
function mayCreate(): boolean {
  const view = session.view;
  return mounted && !!actorId && view?.user.user_id === actorId && !view.password_change_required
    && view.deployment_role === "DEPLOYMENT_ADMIN" && session.canSubmit;
}
function storageKey(): string { return `plm.evidence.global.create.pending.${actorId ?? "none"}`; }
function restore(): void {
  if (!actorId) return;
  try {
    const raw = window.sessionStorage.getItem(storageKey()); if (!raw) return;
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("invalid");
    const entry = value as Record<string, unknown>;
    if (Object.keys(entry).length !== 3 || entry.actor !== actorId
      || typeof entry.key !== "string" || !/^[\x20-\x7e]{16,128}$/.test(entry.key)) throw new Error("invalid");
    const input = normalizeGlobalEvidenceCreate(entry.input);
    pending.value = { actor: actorId, input, key: entry.key };
    displayLabel.value = input.display_label;
  } catch { locked.value = true; error.value = "原操作记录无法安全读取；请核对全局证据列表和审计，勿换号重建。"; }
}
async function loadDocs(next: string | null = null, replace = false): Promise<void> {
  if (!mayCreate() || docsBusy.value) return;
  const request = ++docsGeneration; docsBusy.value = true; docsError.value = "";
  if (replace) { docs.value = []; docsCursor.value = null; docsLoaded.value = false; }
  try {
    const page = await documents.list({ kind: "GLOBAL" }, next);
    if (!mounted || request !== docsGeneration || !mayCreate()) return;
    const eligible = page.items.filter(item => item.scope === "GLOBAL"
      && item.category === "STANDARD_CAPABILITY" && item.state === "ACTIVE");
    if (new Set([...docs.value, ...eligible].map(item => item.document_id)).size
      !== docs.value.length + eligible.length) throw new DocumentReadError("DOCUMENT_CLIENT_UNAVAILABLE");
    docs.value = [...docs.value, ...eligible]; docsCursor.value = page.next_cursor; docsLoaded.value = true;
  } catch (failure) { if (request === docsGeneration) {
    docs.value = []; docsCursor.value = null; docsLoaded.value = false;
    docsError.value = failure instanceof DocumentReadError ? failure.message : "暂时无法读取全局文档。";
  } } finally { if (request === docsGeneration) docsBusy.value = false; }
}
async function loadVersions(next: string | null = null, replace = false): Promise<void> {
  const doc = active.value;
  if (!mayCreate() || !doc || versionsBusy.value || pending.value || locked.value) return;
  const request = ++versionsGeneration; versionsBusy.value = true; versionsError.value = "";
  if (replace) { versions.value = []; versionsCursor.value = null; }
  try {
    const page = await documents.listVersions({ kind: "GLOBAL" }, doc.document_id, next);
    if (!mounted || request !== versionsGeneration || active.value?.document_id !== doc.document_id || !mayCreate()) return;
    if (new Set([...versions.value, ...page.items].map(item => item.document_version_id)).size
      !== versions.value.length + page.items.length) throw new DocumentReadError("DOCUMENT_CLIENT_UNAVAILABLE");
    versions.value = [...versions.value, ...page.items]; versionsCursor.value = page.next_cursor;
  } catch (failure) { if (request === versionsGeneration) {
    versions.value = []; versionsCursor.value = null;
    versionsError.value = failure instanceof DocumentReadError ? failure.message : "暂时无法读取固定版本。";
  } } finally { if (request === versionsGeneration) versionsBusy.value = false; }
}
function openVersions(doc: DocumentView): void {
  if (!mayCreate() || pending.value || locked.value || busy.value || doc.scope !== "GLOBAL"
    || doc.category !== "STANDARD_CAPABILITY" || doc.state !== "ACTIVE") return;
  versionsGeneration += 1; active.value = doc; versions.value = []; versionsCursor.value = null;
  void loadVersions(null, true);
}
function chooseVersion(version: DocumentVersionView): void {
  const doc = active.value;
  if (!mayCreate() || !doc || version.availability_state !== "AVAILABLE"
    || pending.value || locked.value || busy.value) return;
  selected.value = { document: doc, version };
  active.value = null; versions.value = []; versionsCursor.value = null; confirmed.value = false; error.value = "";
}
function clearSession(): void {
  docsGeneration += 1; versionsGeneration += 1; docs.value = []; docsCursor.value = null;
  docsLoaded.value = false; docsBusy.value = false; active.value = null; versions.value = [];
  versionsCursor.value = null; versionsBusy.value = false; selected.value = null; confirmed.value = false;
  if (pending.value || busy.value) error.value = "会话已变化；请核对原操作历史，勿重新创建。";
}
const unsubscribe = session.subscribe(() => { clearSession(); if (mayCreate()) void loadDocs(null, true); });
onMounted(() => { restore(); void loadDocs(null, true); });
onUnmounted(() => { mounted = false; clearSession(); unsubscribe(); });
async function submit(): Promise<void> {
  if (!mayCreate() || busy.value || locked.value || created.value
    || pending.value && !confirmRetry.value) return;
  let attempt = pending.value;
  if (!attempt) {
    if (!selected.value || !confirmed.value) return;
    let input: GlobalEvidenceCreateInput;
    try { input = normalizeGlobalEvidenceCreate({
      document_id: selected.value.document.document_id,
      document_version_id: selected.value.version.document_version_id,
      locator: { locator_type: "DOCUMENT" }, display_label: displayLabel.value.trim(), display_excerpt: null,
    }); } catch (failure) { error.value = failure instanceof Error ? failure.message : "输入无效。"; return; }
    attempt = { actor: actorId!, input, key: crypto.randomUUID() };
    try { window.sessionStorage.setItem(storageKey(), JSON.stringify(attempt)); }
    catch { error.value = "无法保存原操作号，本次未提交。"; return; }
    pending.value = attempt; confirmed.value = false;
  }
  if (attempt.actor !== actorId || session.view?.user.user_id !== actorId) { locked.value = true; return; }
  confirmRetry.value = false; busy.value = true; error.value = "";
  try {
    const receipt = await creator.create(attempt.input, attempt.key);
    if (!mounted || !mayCreate()) return;
    created.value = receipt;
    try { window.sessionStorage.removeItem(storageKey()); }
    catch { locked.value = true; error.value = "已创建但原操作号清理失败；请勿再次提交。"; return; }
    pending.value = null;
  } catch (failure) {
    if (!mounted) return;
    if (failure instanceof GlobalEvidenceCreateError && failure.code === "CONFLICT_IDEMPOTENCY") locked.value = true;
    if (failure instanceof GlobalEvidenceCreateError && !failure.uncertain
      && failure.code !== "CONFLICT_IDEMPOTENCY") {
      try { window.sessionStorage.removeItem(storageKey()); pending.value = null; }
      catch { locked.value = true; }
    }
    error.value = failure instanceof Error ? failure.message : "结果无法确认；请保留原操作号。";
  } finally { if (mounted) busy.value = false; }
}
</script>

<template>
  <section class="page-panel" :aria-busy="docsBusy || versionsBusy || busy">
    <RouterLink :to="{ name: 'global-evidence' }">返回全局证据</RouterLink>
    <h1>创建全局证据候选</h1>
    <p>仅部署管理员可提交。本入口只证明整份 GLOBAL 标准能力文档，不提供页、段或引用原文定位；创建后仍为 CANDIDATE，须另行人工确认资格。</p>
    <p v-if="!mayCreate()" role="status">需要已登录且可提交的部署管理员会话。</p>
    <template v-else>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="created" role="status">已创建证据 {{ created.evidence_id }}，当前仅为 CANDIDATE，不可作为能力版本的合格引用。</p>
      <RouterLink v-if="created" :to="{ name: 'global-evidence' }">前往全局证据列表进行人工资格确认</RouterLink>
      <template v-else>
        <h2>选择固定文档版本</h2>
        <p v-if="docsError" role="alert">{{ docsError }}</p>
        <p v-if="docsLoaded && !docs.length" role="status">暂无合格的全局标准能力文档；请先上传并等待固定版本可用。</p>
        <ul aria-label="标准能力文档候选"><li v-for="doc in docs" :key="doc.document_id">
          {{ doc.title }} · {{ doc.display_name }}
          <button type="button" :disabled="!!pending || locked || busy" @click="openVersions(doc)">选择固定版本</button>
        </li></ul>
        <button v-if="docsCursor" type="button" :disabled="docsBusy || !!pending || locked" @click="loadDocs(docsCursor)">加载更多文档</button>
        <div v-if="active && !pending">
          <h3>{{ active.title }} 的可用版本</h3>
          <p v-if="versionsError" role="alert">{{ versionsError }}</p>
          <p v-if="!versionsBusy && !versions.length && !versionsError" role="status">此文档尚无可用固定版本。</p>
          <ul><li v-for="version in versions" :key="version.document_version_id">
            第 {{ version.version_no }} 版 · {{ version.availability_state }}
            <button type="button" :disabled="busy" @click="chooseVersion(version)">选用此版本</button>
          </li></ul>
          <button v-if="versionsCursor" type="button" :disabled="versionsBusy" @click="loadVersions(versionsCursor)">加载更多版本</button>
        </div>
        <p v-if="selected">已选：{{ selected.document.title }} · 第 {{ selected.version.version_no }} 版；定位范围为整份文档。</p>
        <form @submit.prevent="submit">
          <label for="global-evidence-label">证据标签</label>
          <input id="global-evidence-label" v-model="displayLabel" required maxlength="255" :disabled="!!pending || busy || locked" />
          <label v-if="!pending"><input v-model="confirmed" type="checkbox" :disabled="busy || locked" /> 我确认仅将所选固定整文档建立为待审核候选</label>
          <p v-if="pending" role="status">原操作记录已保留；结果不明时先核对全局证据列表，再确认同号重试。</p>
          <label v-if="pending"><input v-model="confirmRetry" type="checkbox" :disabled="busy || locked" /> 我已核对历史，确认沿用原来源和操作号</label>
          <button type="submit" :disabled="busy || locked || !pending && (!selected || !confirmed) || !!pending && !confirmRetry">
            {{ pending ? '按原操作号重试创建' : '创建候选证据' }}
          </button>
        </form>
      </template>
    </template>
  </section>
</template>
