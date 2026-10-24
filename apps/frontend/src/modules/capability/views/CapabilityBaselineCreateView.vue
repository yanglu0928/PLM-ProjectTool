<script setup lang="ts">
import { inject, onMounted, onUnmounted, ref, shallowRef, toRaw } from "vue";
import { RouterLink, useRouter } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { DocumentReadClient, DocumentReadError, type DocumentView,
  type DocumentVersionView } from "@/modules/document/api/documentReadClient";
import { CapabilityCreateClient, CapabilityCreateError, normalizeCapabilitySources,
  type CapabilityCreateInput, type CapabilitySource } from "@/modules/capability/api/capabilityCreateClient";

const props = defineProps<{ session?: SessionClient; documents?: DocumentReadClient; creator?: CapabilityCreateClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const documents = toRaw(props.documents ?? new DocumentReadClient());
const creator = toRaw(props.creator ?? new CapabilityCreateClient(session));
const router = useRouter(); const actorId = session.view?.user.user_id;
interface Chosen extends CapabilitySource { readonly title: string; readonly version_no: number | null; }
interface Pending { readonly actor: string; readonly input: CapabilityCreateInput; readonly key: string; }
const code = ref(""); const name = ref(""); const description = ref("");
const chosen = ref<Chosen[]>([]);
const docs = ref<readonly DocumentView[]>([]); const docsCursor = ref<string | null>(null);
const docsLoaded = ref(false); const docsBusy = ref(false); const docsError = ref("");
const active = shallowRef<DocumentView | null>(null);
const versions = ref<readonly DocumentVersionView[]>([]); const versionsCursor = ref<string | null>(null);
const versionsBusy = ref(false); const versionsError = ref("");
const pending = ref<Pending | null>(null); const confirmRetry = ref(false);
const busy = ref(false); const error = ref(""); const locked = ref(false); const createdId = ref("");
let mounted = true; let docsGeneration = 0; let versionsGeneration = 0;
function mayCreate(): boolean {
  const view = session.view;
  return mounted && !!actorId && view?.user.user_id === actorId && !view.password_change_required
    && view.deployment_role === "DEPLOYMENT_ADMIN" && session.canSubmit;
}
function storageKey(): string { return `plm.cap.baseline.create.pending.${actorId ?? "none"}`; }
function restore(): void {
  if (!actorId) return;
  try {
    const raw = window.sessionStorage.getItem(storageKey()); if (!raw) return;
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("invalid");
    const entry = value as Record<string, unknown>;
    if (Object.keys(entry).length !== 3 || entry.actor !== actorId || !entry.input
      || typeof entry.key !== "string" || !/^[\x20-\x7e]{16,128}$/.test(entry.key)) throw new Error("invalid");
    const input = entry.input as CapabilityCreateInput;
    const sources = normalizeCapabilitySources(input.source_documents);
    if (typeof input.baseline_code !== "string" || !/^[A-Z][A-Z0-9_.-]{0,63}$/.test(input.baseline_code)
      || typeof input.name !== "string" || !input.name.trim() || input.name.length > 255
      || input.description !== null && (typeof input.description !== "string" || input.description.length > 2000)) {
      throw new Error("invalid");
    }
    pending.value = { actor: actorId, input: { baseline_code: input.baseline_code, name: input.name,
      description: input.description, source_documents: sources }, key: entry.key };
    code.value = input.baseline_code; name.value = input.name; description.value = input.description ?? "";
    chosen.value = sources.map((source, index) => ({ ...source,
      title: `已保留固定来源 ${index + 1}`, version_no: null }));
  } catch { locked.value = true; error.value = "原操作记录无法安全读取；请核对基线列表和审计，不要重新创建。"; }
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
  if (!mayCreate() || doc.scope !== "GLOBAL" || doc.category !== "STANDARD_CAPABILITY"
    || doc.state !== "ACTIVE" || pending.value || locked.value) return;
  versionsGeneration += 1; active.value = doc; versions.value = []; versionsCursor.value = null;
  void loadVersions(null, true);
}
function chooseVersion(version: DocumentVersionView): void {
  const doc = active.value;
  if (!mayCreate() || !doc || version.availability_state !== "AVAILABLE" || pending.value || locked.value || busy.value) return;
  if (!chosen.value.some(item => item.document_id === doc.document_id) && chosen.value.length >= 500) {
    error.value = "每次最多选择 500 份固定来源。"; return;
  }
  chosen.value = [...chosen.value.filter(item => item.document_id !== doc.document_id), {
    document_id: doc.document_id, document_version_id: version.document_version_id,
    title: doc.title, version_no: version.version_no }];
  active.value = null; versions.value = []; versionsCursor.value = null; error.value = "";
}
function removeSource(documentId: string): void {
  if (pending.value || busy.value || locked.value) return;
  chosen.value = chosen.value.filter(item => item.document_id !== documentId);
}
function clearSessionProjection(): void {
  docsGeneration += 1; versionsGeneration += 1; docs.value = []; docsCursor.value = null;
  docsLoaded.value = false; docsBusy.value = false; active.value = null; versions.value = [];
  versionsCursor.value = null; versionsBusy.value = false; chosen.value = [];
  if (pending.value || busy.value) error.value = "会话已变化；请核对原操作历史，勿重新创建。";
}
const unsubscribe = session.subscribe(() => { clearSessionProjection(); if (mayCreate()) void loadDocs(null, true); });
onMounted(() => { restore(); void loadDocs(null, true); });
onUnmounted(() => { mounted = false; clearSessionProjection(); unsubscribe(); });
async function submit(): Promise<void> {
  if (!mayCreate() || busy.value || locked.value || createdId.value
    || pending.value && !confirmRetry.value) return;
  let attempt = pending.value;
  if (!attempt) {
    let sources: readonly CapabilitySource[];
    try { sources = normalizeCapabilitySources(chosen.value.map(item => ({
      document_id: item.document_id, document_version_id: item.document_version_id }))); }
    catch (failure) { error.value = failure instanceof Error ? failure.message : "固定来源无效。"; return; }
    const input: CapabilityCreateInput = { baseline_code: code.value.trim().toUpperCase(),
      name: name.value.trim(), description: description.value.trim() || null, source_documents: sources };
    attempt = { actor: actorId!, input, key: crypto.randomUUID() };
    try { window.sessionStorage.setItem(storageKey(), JSON.stringify(attempt)); }
    catch { error.value = "无法保存原操作号，本次未提交。"; return; }
    pending.value = attempt;
  }
  if (attempt.actor !== actorId || session.view?.user.user_id !== actorId) {
    locked.value = true; return;
  }
  confirmRetry.value = false; busy.value = true; error.value = "";
  try {
    const result = await creator.create(attempt.input, attempt.key);
    if (!mounted || !mayCreate()) return;
    createdId.value = result.baseline_id;
    try { window.sessionStorage.removeItem(storageKey()); }
    catch { locked.value = true; error.value = "已创建但原操作号清理失败；请勿再次提交。"; return; }
    pending.value = null;
    try { await router.push({ name: "capability-baseline-detail", params: { baselineId: result.baseline_id } }); }
    catch { error.value = "已创建但自动跳转失败；请使用下方详情链接。"; }
  } catch (failure) {
    if (!mounted) return;
    if (failure instanceof CapabilityCreateError && failure.code === "CONFLICT_IDEMPOTENCY") locked.value = true;
    if (failure instanceof CapabilityCreateError && !failure.uncertain && failure.code !== "CONFLICT_IDEMPOTENCY") {
      try { window.sessionStorage.removeItem(storageKey()); pending.value = null; }
      catch { locked.value = true; }
    }
    error.value = failure instanceof Error ? failure.message : "结果无法确认；请保留原操作号。";
  } finally { if (mounted) busy.value = false; }
}
</script>

<template>
  <section class="page-panel" :aria-busy="docsBusy || versionsBusy || busy">
    <RouterLink to="/capability-baselines">返回标准能力基线</RouterLink>
    <h1>创建标准能力基线</h1>
    <p>从已上传的全局标准能力文档选择固定可用版本。这里只创建基线身份；能力条目和正式审批需后续独立完成。</p>
    <p v-if="!mayCreate()" role="status">仅可提交的部署管理员会话可创建。</p>
    <template v-else>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="createdId"><RouterLink :to="{ name: 'capability-baseline-detail', params: { baselineId: createdId } }">重新读取已创建基线</RouterLink></p>
      <template v-else>
        <h2>选择固定来源</h2>
        <RouterLink :to="{ name: 'global-capability-document-upload' }">上传全局标准能力文档</RouterLink>
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
        <h2>已选来源</h2>
        <p v-if="!chosen.length">至少选择一份可用固定版本。</p>
        <ul><li v-for="source in chosen" :key="source.document_id">
          {{ source.title }} · {{ source.version_no === null ? '保留的固定版本' : `第 ${source.version_no} 版` }}
          <button type="button" :disabled="!!pending || busy || locked" @click="removeSource(source.document_id)">移除</button>
        </li></ul>
        <form @submit.prevent="submit">
          <label for="baseline-code">基线代码（大写字母开头，可含数字、点、下划线或连字符）</label>
          <input id="baseline-code" v-model="code" required maxlength="64" :disabled="!!pending || busy || locked" />
          <label for="baseline-name">名称</label>
          <input id="baseline-name" v-model="name" required maxlength="255" :disabled="!!pending || busy || locked" />
          <label for="baseline-description">说明（选填）</label>
          <textarea id="baseline-description" v-model="description" maxlength="2000" :disabled="!!pending || busy || locked" />
          <p v-if="pending" role="status">原操作记录已保留；结果不明时先核对基线列表，再确认同号重试。</p>
          <label v-if="pending"><input v-model="confirmRetry" type="checkbox" :disabled="busy || locked" /> 我已核对历史，确认沿用原来源和操作号</label>
          <button type="submit" :disabled="busy || locked || !chosen.length || !!pending && !confirmRetry">
            {{ pending ? '按原操作号重试创建' : '创建基线身份' }}
          </button>
        </form>
      </template>
    </template>
  </section>
</template>
