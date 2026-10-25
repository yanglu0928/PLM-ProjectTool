<script setup lang="ts">
import { computed, inject, onUnmounted, ref, shallowRef, toRaw, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { DocumentReadClient, DocumentReadError, type DocumentView,
  type DocumentVersionView } from "@/modules/document/api/documentReadClient";
import { HandoverCreateClient, HandoverCreateError, normalizeHandoverPurpose,
  normalizeHandoverSources, type HandoverCreateSource } from "@/modules/handover/api/handoverCreateClient";

const props = defineProps<{ session?: SessionClient; documents?: DocumentReadClient; creator?: HandoverCreateClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const documents = toRaw(props.documents ?? new DocumentReadClient());
const creator = toRaw(props.creator ?? new HandoverCreateClient(session));
const route = useRoute(); const router = useRouter(); const identity = session.view;
const projectId = () => typeof route.params.projectId === "string" ? route.params.projectId : "";
const authorized = computed(() => !!identity && !identity.password_change_required && session.canSubmit
  && session.view?.user.user_id === identity.user.user_id
  && identity.authorized_projects.some(item => item.project_id === projectId()
    && (item.role === "PROJECT_MANAGER" || item.role === "IMPLEMENTATION_MEMBER")));
interface ChosenSource extends HandoverCreateSource { readonly title: string; readonly version_no: number | null; }
interface PendingCreate { readonly project: string; readonly actor: string; readonly purpose: string;
  readonly sources: readonly HandoverCreateSource[]; readonly key: string; }
const purpose = ref(""); const chosen = ref<ChosenSource[]>([]);
const docs = ref<readonly DocumentView[]>([]); const docsCursor = ref<string | null>(null);
const docsLoaded = ref(false); const docsBusy = ref(false); const docsError = ref("");
const activeDocument = shallowRef<DocumentView | null>(null);
const versions = ref<readonly DocumentVersionView[]>([]); const versionsCursor = ref<string | null>(null);
const versionsBusy = ref(false); const versionsError = ref("");
const pending = ref<PendingCreate | null>(null); const confirmRetry = ref(false);
const writeBusy = ref(false); const error = ref(""); const locked = ref(false); const createdId = ref("");
let mounted = true; let docsGeneration = 0; let versionsGeneration = 0;
function storageKey() { return `plm.hnd.analysis.create.pending.${identity?.user.user_id ?? "none"}.${projectId()}`; }
function restore() {
  pending.value = null; confirmRetry.value = false; locked.value = false; createdId.value = "";
  purpose.value = ""; chosen.value = []; error.value = "";
  try {
    const raw = window.sessionStorage.getItem(storageKey());
    if (!raw) return;
    const value: unknown = JSON.parse(raw);
    if (typeof value !== "object" || value === null || Array.isArray(value)) throw new Error("invalid");
    const entry = value as Record<string, unknown>;
    if (Object.keys(entry).length !== 5 || entry.project !== projectId()
      || entry.actor !== identity?.user.user_id || typeof entry.purpose !== "string"
      || entry.purpose !== normalizeHandoverPurpose(entry.purpose)
      || typeof entry.key !== "string" || !/^[\x20-\x7e]{16,128}$/.test(entry.key)) {
      throw new Error("invalid");
    }
    const sources = normalizeHandoverSources(entry.sources);
    pending.value = { project: entry.project, actor: entry.actor, purpose: entry.purpose,
      sources, key: entry.key } as PendingCreate;
    purpose.value = entry.purpose;
    chosen.value = sources.map((source, index) => ({ ...source,
      title: `已保留固定来源 ${index + 1}`, version_no: null }));
  } catch {
    locked.value = true;
    error.value = "原创建记录无法安全读取，已停止提交。请核对交接列表与审计记录。";
  }
}
async function loadDocs(next: string | null = null, replace = false) {
  if (!authorized.value || docsBusy.value) return;
  const project = projectId(), current = ++docsGeneration;
  docsBusy.value = true; docsError.value = "";
  if (replace) { docs.value = []; docsCursor.value = null; docsLoaded.value = false; }
  try {
    const page = await documents.list({ kind: "PROJECT", projectId: project }, next);
    if (!mounted || current !== docsGeneration || project !== projectId() || !authorized.value) return;
    const known = new Set(docs.value.map(item => item.document_id));
    if (page.items.some(item => known.has(item.document_id))) throw new DocumentReadError("DOCUMENT_CLIENT_UNAVAILABLE");
    docs.value = Object.freeze([...docs.value, ...page.items]);
    docsCursor.value = page.next_cursor; docsLoaded.value = true;
  } catch (failure) {
    if (mounted && current === docsGeneration) {
      docs.value = []; docsCursor.value = null; docsLoaded.value = false;
      docsError.value = failure instanceof DocumentReadError ? failure.message : "暂时无法读取项目文档。";
    }
  } finally { if (mounted && current === docsGeneration) docsBusy.value = false; }
}
async function loadVersions(next: string | null = null, replace = false) {
  const doc = activeDocument.value;
  if (!authorized.value || !doc || versionsBusy.value || pending.value || locked.value) return;
  const project = projectId(), current = ++versionsGeneration;
  versionsBusy.value = true; versionsError.value = "";
  if (replace) { versions.value = []; versionsCursor.value = null; }
  try {
    const page = await documents.listVersions({ kind: "PROJECT", projectId: project }, doc.document_id, next);
    if (!mounted || current !== versionsGeneration || project !== projectId()
      || activeDocument.value?.document_id !== doc.document_id || !authorized.value) return;
    const known = new Set(versions.value.map(item => item.document_version_id));
    if (page.items.some(item => known.has(item.document_version_id))) throw new DocumentReadError("DOCUMENT_CLIENT_UNAVAILABLE");
    versions.value = Object.freeze([...versions.value, ...page.items]); versionsCursor.value = page.next_cursor;
  } catch (failure) {
    if (mounted && current === versionsGeneration) {
      versions.value = []; versionsCursor.value = null;
      versionsError.value = failure instanceof DocumentReadError ? failure.message : "暂时无法读取固定版本。";
    }
  } finally { if (mounted && current === versionsGeneration) versionsBusy.value = false; }
}
function openVersions(doc: DocumentView) {
  if (!authorized.value || doc.state !== "ACTIVE" || pending.value || locked.value) return;
  versionsGeneration++; activeDocument.value = doc; versions.value = []; versionsCursor.value = null; versionsError.value = "";
  void loadVersions(null, true);
}
function chooseVersion(version: DocumentVersionView) {
  const doc = activeDocument.value;
  if (!authorized.value || !doc || doc.state !== "ACTIVE" || version.availability_state !== "AVAILABLE"
    || pending.value || locked.value || writeBusy.value) return;
  if (!chosen.value.some(item => item.document_id === doc.document_id) && chosen.value.length >= 500) {
    error.value = "每次最多选择 500 份固定来源。"; return;
  }
  chosen.value = [...chosen.value.filter(item => item.document_id !== doc.document_id), {
    document_id: doc.document_id, document_version_id: version.document_version_id,
    title: doc.title, version_no: version.version_no,
  }];
  activeDocument.value = null; versions.value = []; versionsCursor.value = null; error.value = "";
}
function removeSource(documentId: string) {
  if (pending.value || locked.value || writeBusy.value) return;
  chosen.value = chosen.value.filter(item => item.document_id !== documentId);
}
watch(() => route.params.projectId, () => {
  docsGeneration++; versionsGeneration++; docs.value = []; docsCursor.value = null; docsLoaded.value = false;
  docsBusy.value = false; docsError.value = ""; activeDocument.value = null;
  versions.value = []; versionsCursor.value = null; versionsBusy.value = false; versionsError.value = "";
  restore(); void loadDocs(null, true);
}, { immediate: true });
onUnmounted(() => { mounted = false; docsGeneration++; versionsGeneration++; });

async function submit() {
  if (!authorized.value || writeBusy.value || locked.value || createdId.value
    || pending.value && !confirmRetry.value) return;
  const project = projectId(), actor = identity!.user.user_id;
  let attempt = pending.value;
  if (!attempt) {
    let normalized: string; let sources: readonly HandoverCreateSource[];
    try {
      normalized = normalizeHandoverPurpose(purpose.value);
      sources = normalizeHandoverSources(chosen.value.map(item => ({
        document_id: item.document_id, document_version_id: item.document_version_id })));
    } catch (failure) { error.value = failure instanceof Error ? failure.message : "交接目的或固定来源无效。"; return; }
    attempt = { project, actor, purpose: normalized, sources, key: crypto.randomUUID() };
    try { window.sessionStorage.setItem(storageKey(), JSON.stringify(attempt)); }
    catch { error.value = "无法保存原操作号，本次未提交。"; return; }
    pending.value = attempt; purpose.value = normalized;
  }
  if (attempt.project !== project || attempt.actor !== actor) { locked.value = true; return; }
  const savedKey = storageKey(); confirmRetry.value = false; writeBusy.value = true; error.value = "";
  try {
    const result = await creator.create(project, { analysis_purpose: attempt.purpose,
      source_documents: attempt.sources }, attempt.key);
    if (!mounted || !authorized.value || project !== projectId() || actor !== session.view?.user.user_id) return;
    createdId.value = result.handover_analysis_id;
    try { window.sessionStorage.removeItem(savedKey); }
    catch { locked.value = true; error.value = "分析已创建，但原操作号清理失败；请停止再次提交。"; return; }
    pending.value = null;
    try { await router.push({ name: "project-handover-detail", params: { projectId: project,
      analysisId: result.handover_analysis_id } }); }
    catch { error.value = "分析已创建，但自动跳转失败；请使用下方详情链接。"; }
  } catch (failure) {
    if (!mounted) return;
    if (failure instanceof HandoverCreateError && failure.code === "CONFLICT_IDEMPOTENCY") locked.value = true;
    if (failure instanceof HandoverCreateError && !failure.uncertain && failure.code !== "CONFLICT_IDEMPOTENCY") {
      try { window.sessionStorage.removeItem(savedKey); pending.value = null; }
      catch { locked.value = true; }
    }
    error.value = failure instanceof Error ? failure.message : "创建结果无法确认，请保留原操作号。";
  } finally { if (mounted) writeBusy.value = false; }
}
</script>

<template>
  <section class="handover-create" aria-labelledby="handover-create-title" :aria-busy="docsBusy || versionsBusy || writeBusy">
    <p class="section-kicker">项目交接</p><h1 id="handover-create-title">创建交接分析</h1>
    <p>先选择项目资料的固定版本，再写明分析目的。这里创建的是分析身份，不会自动确认任何差异、待办或客户结论。</p>
    <p><RouterLink :to="{ name: 'project-handover', params: { projectId: route.params.projectId } }">返回交接分析列表</RouterLink></p>
    <p v-if="!authorized" role="status">仅当前项目负责人或实施成员可创建；请重新登录并确认项目权限。</p>
    <template v-else>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="createdId"><RouterLink :to="{ name: 'project-handover-detail', params: { projectId: route.params.projectId,
        analysisId: createdId } }">查看已创建分析的当前详情</RouterLink></p>
      <template v-else>
        <h2>选择固定来源</h2>
        <p>只显示项目文档元数据；文档正文不会填入此表单。提交时服务器会再次核验归属、状态和固定版本。</p>
        <p><RouterLink :to="{ name: 'project-documents', params: { projectId: route.params.projectId } }">查看或上传项目文档</RouterLink></p>
        <p v-if="docsError" role="alert">{{ docsError }}</p>
        <p v-if="docsLoaded && !docs.length" role="status">当前项目没有可选文档；请先上传并发布可用版本。</p>
        <ul v-if="docs.length" aria-label="项目文档候选">
          <li v-for="doc in docs" :key="doc.document_id">
            <span>{{ doc.title }} · {{ doc.display_name }} · {{ doc.state === 'ACTIVE' ? '有效' : '已归档' }}</span>
            <button type="button" :disabled="doc.state !== 'ACTIVE' || !!pending || locked || versionsBusy || writeBusy"
              @click="openVersions(doc)">选择固定版本</button>
          </li>
        </ul>
        <button v-if="docsCursor && docsLoaded" type="button" :disabled="docsBusy || !!pending || locked"
          @click="loadDocs(docsCursor)">加载更多文档</button>
        <div v-if="activeDocument && !pending" class="version-picker">
          <h3>{{ activeDocument.title }} 的可用版本</h3>
          <p v-if="versionsError" role="alert">{{ versionsError }}</p>
          <p v-if="!versionsBusy && !versions.length && !versionsError" role="status">此文档没有可选的已发布固定版本。</p>
          <ul><li v-for="version in versions" :key="version.document_version_id">
            <span>版本 {{ version.version_no }} · {{ version.detected_mime }} · {{ version.size_bytes }} 字节</span>
            <button type="button" :disabled="versionsBusy || writeBusy" @click="chooseVersion(version)">选用此版本</button>
          </li></ul>
          <button v-if="versionsCursor" type="button" :disabled="versionsBusy" @click="loadVersions(versionsCursor)">加载更多版本</button>
          <button type="button" @click="activeDocument = null">关闭版本选择</button>
        </div>
        <h2>本次固定来源（{{ chosen.length }}/500）</h2>
        <p v-if="!chosen.length" role="status">尚未选择来源，不能提交交接分析。</p>
        <ol v-else aria-label="已选固定来源"><li v-for="item in chosen" :key="item.document_id">
          <RouterLink :to="{ name: 'project-document-detail', params: { projectId: route.params.projectId,
            documentId: item.document_id } }">{{ item.title }}</RouterLink>
          <span> · {{ item.version_no === null ? '已保留的原固定版本' : `版本 ${item.version_no}` }}</span>
          <button v-if="!pending && !locked" type="button" @click="removeSource(item.document_id)">移除此来源</button>
        </li></ol>
        <form @submit.prevent="submit">
          <label for="handover-purpose">分析目的</label>
          <input id="handover-purpose" v-model="purpose" required maxlength="255"
            :disabled="writeBusy || !!pending || locked" placeholder="例如：合同与技术协议交接差异分析" />
          <p v-if="pending" role="status">原操作号与固定来源已保存在本浏览器会话。结果未确认时，请先核对交接列表；不得换号重复创建。</p>
          <label v-if="pending && !locked"><input v-model="confirmRetry" type="checkbox" :disabled="writeBusy" />
            我已核对原目的、固定来源和交接列表，按原操作号重试</label>
          <button type="submit" :disabled="writeBusy || locked || !chosen.length || !!(pending && !confirmRetry)">
            {{ writeBusy ? '正在提交…' : pending ? '按原操作号重试' : '创建交接分析' }}
          </button>
        </form>
      </template>
    </template>
  </section>
</template>

<style scoped>
.handover-create { max-width: 52rem; margin: 1rem auto; padding: 1.5rem; background: #fff; border-radius: 1rem; }
.handover-create ul,.handover-create ol { display: grid; gap: .55rem; }
.handover-create li { overflow-wrap: anywhere; }
.handover-create button { margin-left: .5rem; }
.handover-create form { display: grid; gap: .8rem; margin-top: 1.2rem; }
.handover-create [role="alert"] { color: #a21d25; }
.version-picker { padding: 1rem; border: 1px solid #d8dee7; border-radius: .75rem; }
</style>
