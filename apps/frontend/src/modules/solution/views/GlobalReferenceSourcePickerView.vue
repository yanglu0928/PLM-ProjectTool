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

const props = defineProps<{ session?: SessionClient; listClient?: EvidenceListClient;
  viewerClient?: EvidenceViewerClient; eligibilityClient?: EvidenceEligibilityClient;
  attestationClient?: ReferenceDeidentificationClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const lists = toRaw(props.listClient ?? new EvidenceListClient());
const viewers = toRaw(props.viewerClient ?? new EvidenceViewerClient());
const eligibility = toRaw(props.eligibilityClient ?? new EvidenceEligibilityClient(session));
const attestations = toRaw(props.attestationClient ?? new ReferenceDeidentificationClient(session));
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
let generation = 0; let sourceRevision = 0; let mounted = true;
const mayRead = () => mounted && session.view?.deployment_role === "DEPLOYMENT_ADMIN"
  && !session.view.password_change_required;
const selectedIds = () => new Set(selected.value.map((entry) => entry.evidence.evidence_id));
const documentVersionIds = () => [...new Set(selected.value.map((entry) => entry.viewer.document_version_id))];
const documents = () => selected.value.filter((entry, index, all) =>
  all.findIndex((candidate) => candidate.viewer.document_version_id === entry.viewer.document_version_id) === index);
const storageKey = () => `plm.sol.global.deidentification.multi.pending.${session.view?.user.user_id ?? "none"}`;
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
onMounted(() => { restorePending(); void load(true); });
onUnmounted(() => { mounted = false; generation += 1; selected.value = []; });
</script>

<template>
  <section class="global-source-picker" aria-labelledby="picker-title" :aria-busy="busy">
    <p class="section-kicker">全局参考方案</p>
    <h1 id="picker-title">多来源核查候选</h1>
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
        <label>撤回原因<select v-model="revokeReason"><option value="ADMIN_REVIEW">管理员复核</option>
          <option value="SOURCE_EXPOSED">来源暴露</option><option value="SCOPE_CHANGED">范围变化</option></select></label>
        <button type="button" :disabled="busy || !!pendingKind || !session.canSubmit" @click="revoke()">撤回此集合确认</button>
      </section>
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
