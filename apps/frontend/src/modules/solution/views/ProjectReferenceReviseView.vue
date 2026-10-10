<script setup lang="ts">
import { inject, onMounted, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { DocumentReadClient, type DocumentView, type DocumentVersionView } from "@/modules/document/api/documentReadClient";
import { EvidenceListClient, type EvidenceSummary } from "@/modules/evidence/api/evidenceListClient";
import { EvidenceViewerClient, type EvidenceViewerDescriptor } from "@/modules/evidence/api/evidenceViewerClient";
import { EvidenceEligibilityClient } from "@/modules/evidence/api/evidenceEligibilityClient";
import { ReferenceReadClient, type ReferenceCurrent } from "@/modules/solution/api/referenceReadClient";
import { ReferenceReviseClient, type ReferenceRevised, type ReferenceReviseInput } from "@/modules/solution/api/referenceReviseClient";

const props = defineProps<{ session?: SessionClient; reader?: ReferenceReadClient;
  documents?: DocumentReadClient; evidences?: EvidenceListClient;
  viewers?: EvidenceViewerClient; eligibility?: EvidenceEligibilityClient;
  revises?: ReferenceReviseClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const reader = toRaw(props.reader ?? new ReferenceReadClient());
const documents = toRaw(props.documents ?? new DocumentReadClient());
const evidences = toRaw(props.evidences ?? new EvidenceListClient());
const viewers = toRaw(props.viewers ?? new EvidenceViewerClient());
const eligibility = toRaw(props.eligibility ?? new EvidenceEligibilityClient(session));
const revises = toRaw(props.revises ?? new ReferenceReviseClient(session));
const route = useRoute();
type SelectedDocument = Readonly<{ document: DocumentView; version: DocumentVersionView }>;
type SelectedEvidence = Readonly<{ evidence: EvidenceSummary; viewer: EvidenceViewerDescriptor }>;
type Pending = Readonly<{ actor: string; project: string; reference: string;
  key: string; ifMatch: string; body: string }>;
const current = ref<ReferenceCurrent | null>(null);
const candidateDocuments = ref<readonly DocumentView[]>([]);
const documentCursor = ref<string | null>(null);
const candidateEvidence = ref<readonly EvidenceSummary[]>([]);
const evidenceCursor = ref<string | null>(null);
const expandedDocument = ref<DocumentView | null>(null);
const versions = ref<readonly DocumentVersionView[]>([]);
const versionCursor = ref<string | null>(null);
const chosenDocuments = ref<readonly SelectedDocument[]>([]);
const chosenEvidence = ref<readonly SelectedEvidence[]>([]);
const reviewedDocuments = ref<readonly string[]>([]); const reviewedEvidence = ref<readonly string[]>([]);
const sourceClass = ref(""); const deidentificationClass = ref(""); const industry = ref("");
const checked = ref(false); const busy = ref(false); const error = ref("");
const historical = ref<ReferenceRevised | null>(null); const refreshed = ref<ReferenceCurrent | null>(null);
const pending = ref<Pending | null>(null); const pendingCorrupt = ref(false);
const reviewedRecovery = ref(false);
let generation = 0; let mounted = true;
const projectId = () => typeof route.params.projectId === "string" ? route.params.projectId : "";
const referenceId = () => typeof route.params.referenceId === "string" ? route.params.referenceId : "";
const scope = () => ({ kind: "PROJECT" as const, projectId: projectId() });
const allowedCategory = new Set(["CONTRACTUAL", "PROJECT_RECORD", "REFERENCE_MATERIAL", "STANDARD_CAPABILITY"]);
function mayWrite(): boolean {
  return mounted && !!session.view && !session.view.password_change_required && session.canSubmit
    && session.view.authorized_projects.some(item => item.project_id === projectId()
      && (item.role === "PROJECT_MANAGER" || item.role === "IMPLEMENTATION_MEMBER"));
}
function storageKey(): string {
  return `plm.sol.project.reference.revise.pending.${session.view?.user.user_id ?? "none"}.${projectId()}.${referenceId()}`;
}
function restorePending() {
  pending.value = null; pendingCorrupt.value = false; reviewedRecovery.value = false;
  try {
    const raw = window.sessionStorage.getItem(storageKey());
    if (!raw) return;
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("bad pending");
    const item = value as Record<string, unknown>;
    if (Object.keys(item).length !== 6 || item.actor !== session.view?.user.user_id
      || item.project !== projectId() || item.reference !== referenceId()
      || typeof item.key !== "string" || !/^[\x20-\x7e]{16,128}$/.test(item.key)
      || typeof item.ifMatch !== "string" || !/^"v(?:0|[1-9]\d*)"$/.test(item.ifMatch)
      || typeof item.body !== "string" || !item.body) throw new Error("bad pending");
    pending.value = item as Pending;
  } catch { pendingCorrupt.value = true; }
}
function savePending(item: Pending): boolean {
  try { window.sessionStorage.setItem(storageKey(), JSON.stringify(item)); pending.value = item; return true; }
  catch { error.value = "无法保存原操作号，本次未提交。"; return false; }
}
function clearPending(): boolean {
  try { window.sessionStorage.removeItem(storageKey()); pending.value = null;
    pendingCorrupt.value = false; reviewedRecovery.value = false; return true; }
  catch { error.value = "无法清除待核对记录，继续锁定提交。"; return false; }
}
function changed() { checked.value = false; historical.value = null; refreshed.value = null; }
function allReviewed(): boolean {
  return chosenDocuments.value.length > 0
    && chosenDocuments.value.every(item => reviewedDocuments.value.includes(item.version.document_version_id))
    && chosenEvidence.value.every(item => reviewedEvidence.value.includes(item.evidence.evidence_id));
}
async function loadRoot() {
  if (!mayWrite() || busy.value) return;
  const project = projectId(), reference = referenceId(), run = ++generation;
  busy.value = true; error.value = ""; current.value = null;
  try {
    const result = await reader.current(project, reference);
    if (!mounted || run !== generation || project !== projectId() || reference !== referenceId()) return;
    current.value = result; sourceClass.value = result.source_project_class;
    deidentificationClass.value = result.deidentification_class;
    industry.value = typeof result.applicability.industry === "string" ? result.applicability.industry : "";
    restorePending();
  } catch (failure) { if (mounted && run === generation) error.value = failure instanceof Error
    ? failure.message : "无法读取当前参考方案。"; }
  finally { if (mounted && run === generation) busy.value = false; }
}
async function loadDocuments(reset = false) {
  if (!mayWrite() || busy.value || !reset && candidateDocuments.value.length && !documentCursor.value) return;
  const project = projectId(), run = generation, after = reset ? null : documentCursor.value;
  busy.value = true; error.value = "";
  try {
    const page = await documents.list(scope(), after);
    if (!mounted || run !== generation || project !== projectId()) return;
    const existing = reset ? [] : candidateDocuments.value;
    if (page.items.some(item => existing.some(prior => prior.document_id === item.document_id))) throw new Error("重复文档");
    candidateDocuments.value = [...existing, ...page.items]; documentCursor.value = page.next_cursor;
    if (reset) { expandedDocument.value = null; versions.value = []; versionCursor.value = null; }
  } catch { if (mounted && run === generation) error.value = "无法读取文档候选；请刷新。"; }
  finally { if (mounted && run === generation) busy.value = false; }
}
async function loadVersions(document: DocumentView, reset = false) {
  if (!mayWrite() || busy.value || document.state !== "ACTIVE" || !allowedCategory.has(document.category)
    || !candidateDocuments.value.some(item => item.document_id === document.document_id)) return;
  const project = projectId(), run = generation, after = reset ? null : versionCursor.value;
  busy.value = true; error.value = "";
  try {
    const page = await documents.listVersions(scope(), document.document_id, after);
    if (!mounted || run !== generation || project !== projectId()) return;
    const existing = reset ? [] : versions.value;
    if (page.items.some(item => existing.some(prior => prior.document_version_id === item.document_version_id))) throw new Error("重复版本");
    expandedDocument.value = document; versions.value = [...existing, ...page.items]; versionCursor.value = page.next_cursor;
  } catch { if (mounted && run === generation) error.value = "无法读取固定文档版本。"; }
  finally { if (mounted && run === generation) busy.value = false; }
}
async function chooseDocument(document: DocumentView, version: DocumentVersionView) {
  if (!mayWrite() || busy.value || chosenDocuments.value.length >= 100
    || chosenDocuments.value.some(item => item.version.document_version_id === version.document_version_id)) return;
  const project = projectId(), run = generation;
  busy.value = true; error.value = "";
  try {
    const fresh = await documents.get(scope(), document.document_id);
    const fixed = await documents.getVersion(scope(), document.document_id, version.document_version_id);
    if (!mounted || run !== generation || project !== projectId()) return;
    if (fresh.state !== "ACTIVE" || !allowedCategory.has(fresh.category)
      || fixed.document_version_id !== version.document_version_id || fixed.content_sha256 !== version.content_sha256)
      throw new Error("候选已变化");
    chosenDocuments.value = [...chosenDocuments.value, { document: fresh, version: fixed }]; changed();
  } catch { if (mounted && run === generation) error.value = "文档版本不再可用，请刷新并重选。"; }
  finally { if (mounted && run === generation) busy.value = false; }
}
function removeDocument(versionId: string) {
  if (busy.value || pending.value) return;
  chosenDocuments.value = chosenDocuments.value.filter(item => item.version.document_version_id !== versionId);
  chosenEvidence.value = chosenEvidence.value.filter(item => item.viewer.document_version_id !== versionId);
  reviewedDocuments.value = reviewedDocuments.value.filter(id => id !== versionId);
  reviewedEvidence.value = reviewedEvidence.value.filter(id => chosenEvidence.value.some(item => item.evidence.evidence_id === id));
  changed();
}
async function loadEvidence(reset = false) {
  if (!mayWrite() || busy.value || !reset && candidateEvidence.value.length && !evidenceCursor.value) return;
  const project = projectId(), run = generation, after = reset ? null : evidenceCursor.value;
  busy.value = true; error.value = "";
  try {
    const page = await evidences.list(scope(), after);
    if (!mounted || run !== generation || project !== projectId()) return;
    const existing = reset ? [] : candidateEvidence.value;
    if (page.items.some(item => existing.some(prior => prior.evidence_id === item.evidence_id))) throw new Error("重复证据");
    candidateEvidence.value = [...existing, ...page.items]; evidenceCursor.value = page.next_cursor;
  } catch { if (mounted && run === generation) error.value = "无法读取证据候选；可只选择文档。"; }
  finally { if (mounted && run === generation) busy.value = false; }
}
async function chooseEvidence(item: EvidenceSummary) {
  if (!mayWrite() || busy.value || item.eligibility_state !== "ELIGIBLE" || chosenEvidence.value.length >= 500
    || chosenEvidence.value.some(entry => entry.evidence.evidence_id === item.evidence_id)
    || !chosenDocuments.value.some(entry => entry.version.document_version_id === item.document_version_id)) return;
  const project = projectId(), run = generation;
  busy.value = true; error.value = "";
  try {
    const viewer = await viewers.get(scope(), item.evidence_id);
    const state = await eligibility.current(project, item.evidence_id);
    if (!mounted || run !== generation || project !== projectId()) return;
    if (viewer.evidence_id !== item.evidence_id || viewer.document_id !== item.document_id
      || viewer.document_version_id !== item.document_version_id || state.evidence_id !== item.evidence_id
      || state.document_id !== item.document_id || state.document_version_id !== item.document_version_id
      || state.eligibility_state !== "ELIGIBLE") throw new Error("证据已变化");
    chosenEvidence.value = [...chosenEvidence.value, { evidence: item, viewer }]; changed();
  } catch { if (mounted && run === generation) error.value = "证据已变化或无法定位，请刷新。"; }
  finally { if (mounted && run === generation) busy.value = false; }
}
function removeEvidence(id: string) {
  if (busy.value || pending.value) return;
  chosenEvidence.value = chosenEvidence.value.filter(item => item.evidence.evidence_id !== id); changed();
  reviewedEvidence.value = reviewedEvidence.value.filter(item => item !== id);
}
function request(): ReferenceReviseInput | null {
  const source = sourceClass.value.trim(), classification = deidentificationClass.value.trim();
  if (!chosenDocuments.value.length || chosenDocuments.value.length > 100 || chosenEvidence.value.length > 500
    || !source || source.length > 128 || /\p{C}/u.test(source)
    || !classification || classification.length > 128 || /\p{C}/u.test(classification)
    || industry.value.trim().length > 128) return null;
  return { document_version_ids: chosenDocuments.value.map(item => item.version.document_version_id),
    evidence_ids: chosenEvidence.value.map(item => item.evidence.evidence_id),
    source_project_class: source, deidentification_class: classification,
    applicability: industry.value.trim() ? { industry: industry.value.trim() } : {} };
}
async function recheck(snapshot: ReferenceCurrent) {
  const latest = await reader.current(projectId(), referenceId());
  if (latest.reference_solution_id !== snapshot.reference_solution_id
    || latest.reference_version_id !== snapshot.reference_version_id || latest.etag !== snapshot.etag) {
    throw new Error("当前参考版本已变化，请重新读取后决定。" );
  }
  for (const entry of chosenDocuments.value) {
    const doc = await documents.get(scope(), entry.document.document_id);
    const version = await documents.getVersion(scope(), doc.document_id, entry.version.document_version_id);
    if (doc.state !== "ACTIVE" || !allowedCategory.has(doc.category)
      || version.content_sha256 !== entry.version.content_sha256) throw new Error("文档版本已变化。");
  }
  for (const entry of chosenEvidence.value) {
    const viewer = await viewers.get(scope(), entry.evidence.evidence_id);
    const state = await eligibility.current(projectId(), entry.evidence.evidence_id);
    if (viewer.document_version_id !== entry.viewer.document_version_id
      || viewer.document_id !== entry.viewer.document_id || viewer.content_url !== entry.viewer.content_url
      || state.document_version_id !== entry.viewer.document_version_id
      || state.eligibility_state !== "ELIGIBLE") throw new Error("证据资格或原文已变化。");
  }
}
async function send(item: Pending) {
  if (!mayWrite() || busy.value || pendingCorrupt.value) return;
  const run = generation; busy.value = true; error.value = "";
  try {
    const input = JSON.parse(item.body) as ReferenceReviseInput;
    const result = await revises.revise("PROJECT", item.reference, item.project, input, item.ifMatch, item.key);
    if (!mounted || run !== generation) return;
    historical.value = result;
    if (!clearPending()) return;
    try { refreshed.value = await reader.current(item.project, item.reference); }
    catch { refreshed.value = null; error.value = "修订回执已收到，但当前详情刷新失败；请重新读取。"; }
  } catch (failure) {
    if (mounted && run === generation) error.value = failure instanceof Error ? failure.message : "结果不确定，请保留原操作号。";
  } finally { if (mounted && run === generation) busy.value = false; }
}
async function submit() {
  const input = request(), snapshot = current.value;
  if (!mayWrite() || busy.value || pending.value || pendingCorrupt.value || !checked.value
    || !allReviewed() || !input || !snapshot) return;
  const run = generation; busy.value = true; error.value = "";
  try {
    await recheck(snapshot);
    if (!mounted || run !== generation || !mayWrite()) return;
    const item: Pending = { actor: session.view!.user.user_id, project: projectId(), reference: referenceId(),
      key: crypto.randomUUID(), ifMatch: snapshot.etag, body: JSON.stringify(input) };
    if (!savePending(item)) return;
  } catch (failure) { if (mounted && run === generation) error.value = failure instanceof Error
    ? failure.message : "来源无法重新核验。"; }
  finally { if (mounted && run === generation) busy.value = false; }
  if (pending.value) await send(pending.value);
}
function abandonPending() { if (reviewedRecovery.value && !busy.value) clearPending(); }
watch(() => [route.params.projectId, route.params.referenceId], () => {
  generation += 1; busy.value = false; current.value = null; candidateDocuments.value = []; documentCursor.value = null;
  candidateEvidence.value = []; evidenceCursor.value = null; expandedDocument.value = null; versions.value = [];
  chosenDocuments.value = []; chosenEvidence.value = []; reviewedDocuments.value = [];
  reviewedEvidence.value = []; pending.value = null; pendingCorrupt.value = false;
  changed(); void loadRoot();
});
watch([sourceClass, deidentificationClass, industry], changed);
onMounted(() => { void loadRoot(); });
onUnmounted(() => { mounted = false; generation += 1; });
</script>

<template>
  <section class="reference-revise" aria-labelledby="revise-title" :aria-busy="busy">
    <p class="section-kicker">项目方案</p><h1 id="revise-title">修订项目参考方案</h1>
    <p class="warning">修订只生成新的草稿版本，不代表客户确认或方案可实施。固定来源列表不是物理文件证明，提交时服务端会再次核验。</p>
    <p><RouterLink :to="{ name: 'project-reference-detail', params: { projectId: projectId(), referenceId: referenceId() } }">返回当前详情</RouterLink></p>
    <p v-if="!mayWrite()" role="status">仅项目经理或实施成员可修订；请确认当前登录和项目权限。</p>
    <template v-else>
      <button type="button" :disabled="busy || !!pending || pendingCorrupt" @click="loadRoot()">重新读取当前版本</button>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="busy" role="status">正在核验…</p>
      <section v-if="pending || pendingCorrupt" aria-label="待核对修订操作">
        <h2>上次修订结果待核对</h2>
        <p v-if="pendingCorrupt" role="alert">本地操作记录损坏，停止新提交；请先核对服务端审计。</p>
        <template v-else-if="pending">
          <p>原操作号：<code>{{ pending.key }}</code>。只能沿用原请求、原 If-Match 和原操作号显式重试；不要换号。</p>
          <button type="button" :disabled="busy" @click="send(pending)">同键恢复原操作</button>
        </template>
        <label><input v-model="reviewedRecovery" type="checkbox" :disabled="busy"> 我已核对服务端当前版本和审计，决定放弃此待核对记录</label>
        <button type="button" :disabled="busy || !reviewedRecovery" @click="abandonPending()">清除本地锁定</button>
      </section>
      <section v-if="current" aria-label="提交基准">
        <h2>{{ current.name }} · 当前第 {{ current.version_no }} 版</h2>
        <p>当前版本 ETag：<code>{{ current.etag }}</code>。提交前会重新读取；成功回执不自动代表仍为当前版。</p>
        <p>当前固定来源：{{ current.document_version_ids.length }} 个文档版本、{{ current.evidence_ids.length }} 条证据。</p>
      </section>
      <section aria-label="文档版本候选">
        <h2>选择固定文档版本（必选）</h2>
        <p>仅可选择当前项目活动文档的合同、项目记录、参考材料或标准能力版本；请打开原文核查，不输入 UUID。</p>
        <button type="button" :disabled="busy || !!pending || pendingCorrupt" @click="loadDocuments(true)">读取项目文档候选</button>
        <ol><li v-for="item in candidateDocuments" :key="item.document_id">
          {{ item.title }} · {{ item.category }} · {{ item.state }}
          <button type="button" :disabled="busy || !!pending || pendingCorrupt || item.state !== 'ACTIVE' || !allowedCategory.has(item.category)"
            @click="loadVersions(item, true)">查看可用版本</button>
        </li></ol>
        <button v-if="documentCursor" type="button" :disabled="busy" @click="loadDocuments()">加载更多文档</button>
        <div v-if="expandedDocument" aria-label="固定版本">
          <h3>{{ expandedDocument.title }} 的可用版本</h3>
          <ol><li v-for="version in versions" :key="version.document_version_id">
            第 {{ version.version_no }} 版 · {{ version.detected_mime }}
            <RouterLink :to="{ name: 'project-document-detail', params: { projectId: projectId(), documentId: expandedDocument.document_id }, query: { versionId: version.document_version_id } }" target="_blank">打开固定版本与原文</RouterLink>
            <button type="button" :disabled="busy || !!pending || pendingCorrupt || chosenDocuments.length >= 100"
              @click="chooseDocument(expandedDocument, version)">选择此版本</button>
          </li></ol>
          <button v-if="versionCursor" type="button" :disabled="busy" @click="loadVersions(expandedDocument)">加载更多版本</button>
        </div>
        <h3>已选文档版本</h3>
        <ol><li v-for="entry in chosenDocuments" :key="entry.version.document_version_id">
          {{ entry.document.title }} · 第 {{ entry.version.version_no }} 版
          <RouterLink :to="{ name: 'project-document-detail', params: { projectId: projectId(), documentId: entry.document.document_id }, query: { versionId: entry.version.document_version_id } }" target="_blank">核查原文</RouterLink>
          <label><input v-model="reviewedDocuments" type="checkbox" :value="entry.version.document_version_id"
            :disabled="busy || !!pending">我已打开并核查此固定文档版本</label>
          <button type="button" :disabled="busy || !!pending" @click="removeDocument(entry.version.document_version_id)">移除</button>
        </li></ol>
      </section>
      <section aria-label="证据候选">
        <h2>选择固定证据（可选）</h2><p>只可加入已选文档版本下当前合格的项目证据；证据列表状态不是最终证明。</p>
        <button type="button" :disabled="busy || !!pending || pendingCorrupt" @click="loadEvidence(true)">读取项目证据</button>
        <ol><li v-for="item in candidateEvidence" :key="item.evidence_id">
          {{ item.display_label }} · {{ item.eligibility_state }}
          <button type="button" :disabled="busy || !!pending || pendingCorrupt || item.eligibility_state !== 'ELIGIBLE' || !chosenDocuments.some(entry => entry.version.document_version_id === item.document_version_id)"
            @click="chooseEvidence(item)">核验并加入</button>
        </li></ol>
        <button v-if="evidenceCursor" type="button" :disabled="busy" @click="loadEvidence()">加载更多证据</button>
        <ol><li v-for="entry in chosenEvidence" :key="entry.evidence.evidence_id">
          {{ entry.viewer.display_label }} · <a :href="entry.viewer.content_url" target="_blank" rel="noopener">打开受权固定证据原文</a>
          <label><input v-model="reviewedEvidence" type="checkbox" :value="entry.evidence.evidence_id"
            :disabled="busy || !!pending">我已打开并核查此证据原文</label>
          <button type="button" :disabled="busy || !!pending" @click="removeEvidence(entry.evidence.evidence_id)">移除</button>
        </li></ol>
      </section>
      <section aria-label="修订分类和确认">
        <h2>来源分类与修订确认</h2>
        <label>来源项目分类（例如 PLM）<input v-model="sourceClass" maxlength="128" :disabled="busy || !!pending" placeholder="PLM"></label>
        <label>脱敏分类（项目内使用可填 PROJECT_INTERNAL）<input v-model="deidentificationClass" maxlength="128" :disabled="busy || !!pending" placeholder="PROJECT_INTERNAL"></label>
        <label>适用行业（可选）<input v-model="industry" maxlength="128" :disabled="busy || !!pending" placeholder="例如：离散制造"></label>
        <p>本次候选：{{ chosenDocuments.length }} 个文档版本、{{ chosenEvidence.length }} 条证据；保留选择顺序。</p>
        <label><input v-model="checked" type="checkbox" :disabled="busy || !!pending || !request() || !allReviewed()"> 我已逐项核查所选固定来源，理解这是新的草稿而非客户确认</label>
        <button type="button" :disabled="busy || !!pending || pendingCorrupt || !current || !checked || !request() || !allReviewed()" @click="submit()">重新核验并修订</button>
      </section>
      <section v-if="historical" aria-label="历史首次结果">
        <h2>本次修订回执</h2><p>第 {{ historical.version_no }} 版 · 回执 ETag {{ historical.etag }}。这是首次结果快照，不代表当前状态。</p>
        <p v-if="refreshed">重新读取当前第 {{ refreshed.version_no }} 版 · 当前 ETag {{ refreshed.etag }}。</p>
        <p v-else>当前详情尚未确认，请重新读取。</p>
        <RouterLink :to="{ name: 'project-reference-detail', params: { projectId: projectId(), referenceId: referenceId() } }">打开当前详情</RouterLink>
      </section>
    </template>
  </section>
</template>

<style scoped>
.reference-revise{max-width:68rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}
.reference-revise section{margin:1.5rem 0;padding:1rem;border:1px solid #d8e0e9;border-radius:.6rem}
.reference-revise li{margin:.7rem 0}.reference-revise button{margin:.25rem .5rem}.reference-revise label{display:block;margin:.7rem 0}
.warning{padding:.8rem 1rem;border-left:.3rem solid #d29b42;background:#fff8e9}.reference-revise [role=alert]{color:#a21d25}
</style>
