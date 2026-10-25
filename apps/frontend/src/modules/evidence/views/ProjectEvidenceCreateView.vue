<script setup lang="ts">
import { computed, inject, onUnmounted, ref, shallowRef, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { DocumentReadClient, DocumentReadError, type DocumentView,
  type DocumentVersionView } from "@/modules/document/api/documentReadClient";
import { normalizeGlobalEvidenceCreate } from "@/modules/evidence/api/globalEvidenceCreateClient";
import { ProjectEvidenceCreateClient, ProjectEvidenceCreateError,
  type ProjectEvidenceCreateInput, type ProjectEvidenceCreateReceipt } from "@/modules/evidence/api/projectEvidenceCreateClient";

const props = defineProps<{ session?: SessionClient; documents?: DocumentReadClient;
  creator?: ProjectEvidenceCreateClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const documents = toRaw(props.documents ?? new DocumentReadClient());
const creator = toRaw(props.creator ?? new ProjectEvidenceCreateClient(session));
const route = useRoute(); const actor = session.view?.user.user_id;
const projectId = () => typeof route.params.projectId === "string" ? route.params.projectId : "";
const canCreate = computed(() => !!actor && session.view?.user.user_id === actor
  && !session.view.password_change_required && session.canSubmit
  && session.view.authorized_projects.some(value => value.project_id === projectId()
    && (value.role === "PROJECT_MANAGER" || value.role === "IMPLEMENTATION_MEMBER")));
interface Selection { readonly document: DocumentView; readonly version: DocumentVersionView; }
interface Pending { readonly actor: string; readonly project: string;
  readonly input: ProjectEvidenceCreateInput; readonly key: string; }
const docs = ref<readonly DocumentView[]>([]); const docsCursor = ref<string | null>(null);
const docsLoaded = ref(false); const docsBusy = ref(false); const docsError = ref("");
const active = shallowRef<DocumentView | null>(null); const versions = ref<readonly DocumentVersionView[]>([]);
const versionsCursor = ref<string | null>(null); const versionsBusy = ref(false); const versionsError = ref("");
const selected = shallowRef<Selection | null>(null); const label = ref(""); const attested = ref(false);
const pending = ref<Pending | null>(null); const confirmRetry = ref(false);
const created = shallowRef<ProjectEvidenceCreateReceipt | null>(null);
const busy = ref(false); const locked = ref(false); const error = ref("");
let mounted = true; let docsGeneration = 0; let versionsGeneration = 0;
function storageKey(project = projectId()): string { return `plm.evidence.project.create.pending.${actor ?? "none"}.${project}`; }
function restore(): void {
  pending.value = null; confirmRetry.value = false; created.value = null; locked.value = false;
  selected.value = null; label.value = ""; attested.value = false; error.value = "";
  if (!actor || !projectId()) return;
  try {
    const raw = window.sessionStorage.getItem(storageKey()); if (raw === null) return;
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("invalid");
    const entry = value as Record<string, unknown>;
    if (Object.keys(entry).length !== 4 || entry.actor !== actor || entry.project !== projectId()
      || typeof entry.key !== "string" || !/^[\x20-\x7e]{16,128}$/.test(entry.key)) throw new Error("invalid");
    const input = normalizeGlobalEvidenceCreate(entry.input);
    pending.value = { actor, project: projectId(), input, key: entry.key };
    label.value = input.display_label;
  } catch { locked.value = true; error.value = "原操作记录无法安全读取；请核对项目证据与审计，勿换号重建。"; }
}
async function loadDocs(next: string | null = null, replace = false): Promise<void> {
  if (!canCreate.value || docsBusy.value) return;
  const project = projectId(), request = ++docsGeneration; docsBusy.value = true; docsError.value = "";
  if (replace) { docs.value = []; docsCursor.value = null; docsLoaded.value = false; }
  try {
    const page = await documents.list({ kind: "PROJECT", projectId: project }, next);
    if (!mounted || request !== docsGeneration || project !== projectId() || !canCreate.value) return;
    const eligible = page.items.filter(value => value.scope === "PROJECT" && value.state === "ACTIVE");
    if (new Set([...docs.value, ...eligible].map(value => value.document_id)).size
      !== docs.value.length + eligible.length) throw new DocumentReadError("DOCUMENT_CLIENT_UNAVAILABLE");
    docs.value = Object.freeze([...docs.value, ...eligible]); docsCursor.value = page.next_cursor; docsLoaded.value = true;
  } catch (failure) { if (mounted && request === docsGeneration) {
    docs.value = []; docsCursor.value = null; docsLoaded.value = false;
    docsError.value = failure instanceof DocumentReadError ? failure.message : "暂时无法读取项目文档。";
  } } finally { if (mounted && request === docsGeneration) docsBusy.value = false; }
}
async function loadVersions(next: string | null = null, replace = false): Promise<void> {
  const doc = active.value;
  if (!canCreate.value || !doc || versionsBusy.value || pending.value || locked.value) return;
  const project = projectId(), request = ++versionsGeneration; versionsBusy.value = true; versionsError.value = "";
  if (replace) { versions.value = []; versionsCursor.value = null; }
  try {
    const page = await documents.listVersions({ kind: "PROJECT", projectId: project }, doc.document_id, next);
    if (!mounted || request !== versionsGeneration || project !== projectId()
      || active.value?.document_id !== doc.document_id || !canCreate.value) return;
    if (new Set([...versions.value, ...page.items].map(value => value.document_version_id)).size
      !== versions.value.length + page.items.length) throw new DocumentReadError("DOCUMENT_CLIENT_UNAVAILABLE");
    versions.value = Object.freeze([...versions.value, ...page.items]); versionsCursor.value = page.next_cursor;
  } catch (failure) { if (mounted && request === versionsGeneration) {
    versions.value = []; versionsCursor.value = null;
    versionsError.value = failure instanceof DocumentReadError ? failure.message : "暂时无法读取固定版本。";
  } } finally { if (mounted && request === versionsGeneration) versionsBusy.value = false; }
}
function openVersions(doc: DocumentView): void {
  if (!canCreate.value || doc.scope !== "PROJECT" || doc.state !== "ACTIVE"
    || pending.value || locked.value || busy.value) return;
  versionsGeneration++; active.value = doc; versions.value = []; versionsCursor.value = null;
  void loadVersions(null, true);
}
function chooseVersion(version: DocumentVersionView): void {
  if (!canCreate.value || !active.value || active.value.state !== "ACTIVE"
    || version.availability_state !== "AVAILABLE" || pending.value || locked.value || busy.value) return;
  selected.value = { document: active.value, version }; active.value = null;
  versions.value = []; versionsCursor.value = null; attested.value = false; error.value = "";
}
function resetProject(): void {
  docsGeneration++; versionsGeneration++; docs.value = []; docsCursor.value = null; docsLoaded.value = false;
  docsBusy.value = false; docsError.value = ""; active.value = null; versions.value = [];
  versionsCursor.value = null; versionsBusy.value = false; versionsError.value = "";
  restore(); if (canCreate.value) void loadDocs(null, true);
}
watch(() => route.params.projectId, resetProject, { immediate: true });
const unsubscribe = session.subscribe(resetProject);
onUnmounted(() => { mounted = false; docsGeneration++; versionsGeneration++; unsubscribe(); });
async function submit(): Promise<void> {
  if (!canCreate.value || busy.value || locked.value || created.value
    || pending.value && !confirmRetry.value) return;
  const project = projectId(); let attempt = pending.value;
  if (!attempt) {
    if (!selected.value || !attested.value) return;
    let input: ProjectEvidenceCreateInput;
    try { input = normalizeGlobalEvidenceCreate({ document_id: selected.value.document.document_id,
      document_version_id: selected.value.version.document_version_id,
      locator: { locator_type: "DOCUMENT" }, display_label: label.value.trim(), display_excerpt: null }); }
    catch (failure) { error.value = failure instanceof Error ? failure.message : "证据标签无效。"; return; }
    attempt = { actor: actor!, project, input, key: crypto.randomUUID() };
    try { window.sessionStorage.setItem(storageKey(project), JSON.stringify(attempt)); }
    catch { error.value = "无法保存原操作号，本次未提交。"; return; }
    pending.value = attempt; attested.value = false;
  }
  if (attempt.actor !== actor || attempt.project !== project) { locked.value = true; return; }
  confirmRetry.value = false; busy.value = true; error.value = "";
  try {
    const result = await creator.create(project, attempt.input, attempt.key);
    if (!mounted || !canCreate.value || project !== projectId() || actor !== session.view?.user.user_id) return;
    created.value = result;
    try { window.sessionStorage.removeItem(storageKey(project)); }
    catch { locked.value = true; error.value = "候选已创建但原操作号清理失败；请停止再次提交。"; return; }
    pending.value = null;
  } catch (failure) {
    if (!mounted || project !== projectId()) return;
    if (failure instanceof ProjectEvidenceCreateError && failure.code === "CONFLICT_IDEMPOTENCY") locked.value = true;
    if (failure instanceof ProjectEvidenceCreateError && !failure.uncertain
      && failure.code !== "CONFLICT_IDEMPOTENCY") {
      try { window.sessionStorage.removeItem(storageKey(project)); pending.value = null; }
      catch { locked.value = true; }
    }
    error.value = failure instanceof Error ? failure.message : "创建结果无法确认；请保留原操作号。";
  } finally { if (mounted) busy.value = false; }
}
</script>

<template>
  <section class="evidence-create" aria-labelledby="project-evidence-create-title" :aria-busy="docsBusy || versionsBusy || busy">
    <p class="section-kicker">项目资料</p><h1 id="project-evidence-create-title">创建项目证据候选</h1>
    <p>选择同项目的固定文档版本，建立整文档证据候选。不会自动通过资格核定，也不会把资料或 AI 建议变成正式问题。</p>
    <p><RouterLink :to="{ name: 'project-evidence', params: { projectId: route.params.projectId } }">返回项目证据列表</RouterLink></p>
    <p v-if="!canCreate" role="status">仅当前项目负责人或实施成员可创建；请确认登录和项目权限。</p>
    <template v-else>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="created" role="status">已创建候选 {{ created.evidence_id }}；当前仅为 CANDIDATE，须人工核定为 ELIGIBLE 后才能作为交接分析的正式依据。</p>
      <RouterLink v-if="created" :to="{ name: 'project-evidence', params: { projectId: route.params.projectId } }">前往项目证据列表核定资格</RouterLink>
      <template v-else>
        <h2>选择固定文档</h2>
        <p><RouterLink :to="{ name: 'project-documents', params: { projectId: route.params.projectId } }">查看或上传项目文档</RouterLink></p>
        <p v-if="docsError" role="alert">{{ docsError }}</p>
        <p v-if="docsLoaded && !docs.length" role="status">暂无可选的有效项目文档；请先上传并等待固定版本可用。</p>
        <ul aria-label="项目文档候选"><li v-for="doc in docs" :key="doc.document_id">
          {{ doc.title }} · {{ doc.display_name }}
          <button type="button" :disabled="!!pending || locked || busy" @click="openVersions(doc)">选择固定版本</button>
        </li></ul>
        <button v-if="docsCursor" type="button" :disabled="docsBusy || !!pending || locked" @click="loadDocs(docsCursor)">加载更多文档</button>
        <div v-if="active && !pending">
          <h3>{{ active.title }} 的可用版本</h3><p v-if="versionsError" role="alert">{{ versionsError }}</p>
          <p v-if="!versionsBusy && !versions.length && !versionsError" role="status">此文档尚无可用固定版本。</p>
          <ul><li v-for="version in versions" :key="version.document_version_id">
            第 {{ version.version_no }} 版 · {{ version.detected_mime }}
            <button type="button" :disabled="versionsBusy || busy" @click="chooseVersion(version)">选用此版本</button>
          </li></ul>
          <button v-if="versionsCursor" type="button" :disabled="versionsBusy" @click="loadVersions(versionsCursor)">加载更多版本</button>
        </div>
        <p v-if="selected">已选：{{ selected.document.title }} · 第 {{ selected.version.version_no }} 版；定位范围为整份文档。</p>
        <form @submit.prevent="submit">
          <label for="project-evidence-label">证据标签</label>
          <input id="project-evidence-label" v-model="label" required maxlength="255" :disabled="!!pending || busy || locked"
            placeholder="例如：技术协议中关于编码规则的约定" />
          <label v-if="!pending"><input v-model="attested" type="checkbox" :disabled="busy || locked" /> 我确认以所选固定整文档建立待审核候选</label>
          <p v-if="pending" role="status">原来源和操作号已保留；结果不明时先核对项目证据与审计，再同号重试。</p>
          <label v-if="pending"><input v-model="confirmRetry" type="checkbox" :disabled="busy || locked" /> 我已核对历史，沿用原来源与操作号</label>
          <button type="submit" :disabled="busy || locked || !pending && (!selected || !attested) || !!pending && !confirmRetry">
            {{ pending ? '按原操作号重试创建' : '创建候选证据' }}
          </button>
        </form>
      </template>
    </template>
  </section>
</template>

<style scoped>
.evidence-create { max-width: 52rem; margin: 1rem auto; padding: 1.5rem; background: #fff; border-radius: 1rem; }
.evidence-create ul { display: grid; gap: .6rem; }
.evidence-create li { overflow-wrap: anywhere; }
.evidence-create form { display: grid; gap: .8rem; margin-top: 1.2rem; }
.evidence-create [role="alert"] { color: #a21d25; }
</style>
