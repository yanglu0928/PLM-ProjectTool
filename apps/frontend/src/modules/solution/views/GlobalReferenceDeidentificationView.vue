<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { EvidenceViewerClient, type EvidenceViewerDescriptor } from "@/modules/evidence/api/evidenceViewerClient";
import { ReferenceDeidentificationClient, ReferenceDeidentificationError,
  type DeidentificationPreview, type DeidentificationSources,
  type DeidentificationConfirmation, type DeidentificationOperationStatus } from "@/modules/solution/api/referenceDeidentificationClient";

const props = defineProps<{ session?: SessionClient; viewer?: EvidenceViewerClient;
  attestations?: ReferenceDeidentificationClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const viewer = toRaw(props.viewer ?? new EvidenceViewerClient());
const attestations = toRaw(props.attestations ?? new ReferenceDeidentificationClient(session));
const route = useRoute();
const fixed = ref<EvidenceViewerDescriptor | null>(null);
const preview = ref<DeidentificationPreview | null>(null);
const confirmation = ref<DeidentificationConfirmation | null>(null);
const busy = ref(false); const error = ref(""); const success = ref("");
const sourceClass = ref(""); const deidentificationClass = ref(""); const industry = ref("");
const documentOpened = ref(false); const evidenceOpened = ref(false);
const documentChecked = ref(false); const evidenceChecked = ref(false); const attested = ref(false);
const pendingKey = ref(""); const pendingKind = ref<"confirm" | "revoke" | null>(null);
const lookupResult = ref<DeidentificationOperationStatus | null>(null);
const reviewedRecovery = ref(false);
const revokeReason = ref<"SOURCE_EXPOSED" | "SCOPE_CHANGED" | "ADMIN_REVIEW">("ADMIN_REVIEW");
let generation = 0; let sourceRevision = 0; let mounted = true;
const evidenceId = () => typeof route.params.evidenceId === "string" ? route.params.evidenceId : "";
const mayRead = () => mounted && !!session.view && !session.view.password_change_required
  && session.view.deployment_role === "DEPLOYMENT_ADMIN";
const storageKey = () => `plm.sol.global.deidentification.pending.${session.view?.user.user_id ?? "none"}`;
function locationText(locator: Readonly<Record<string, unknown>>): string {
  const source = locator.locator_type === "STRUCTURED_NODE" && typeof locator.source_locator === "object"
    && locator.source_locator !== null && !Array.isArray(locator.source_locator)
    ? locator.source_locator as Record<string, unknown> : locator;
  if (source.locator_type === "PAGE" && typeof source.page_no === "number") return `第 ${source.page_no} 页`;
  if (source.locator_type === "TEXT_RANGE") {
    const place = typeof source.page_no === "number" ? `第 ${source.page_no} 页`
      : typeof source.section_path === "string" ? `章节 ${source.section_path}` : "文本";
    return `${place} · 字符 ${source.start_offset}–${source.end_offset}`;
  }
  if (source.locator_type === "SECTION" && typeof source.section_path === "string") return `章节 ${source.section_path}`;
  if (source.locator_type === "PARAGRAPH") return typeof source.paragraph_index === "number"
    ? `段落 ${source.paragraph_index}` : `段落锚点 ${source.stable_anchor}`;
  if (source.locator_type === "TABLE_CELL") return `表格 ${source.table_anchor} · 行 ${source.row_no} 列 ${source.column_no}`;
  if (source.locator_type === "SHEET_RANGE") return `工作表 ${source.sheet_name} · ${source.start_cell}–${source.end_cell}`;
  if (source.locator_type === "SLIDE_SHAPE") return `第 ${source.slide_no} 张幻灯片 · 形状 ${source.shape_id}`;
  return "整份文档";
}
function clearPreview() {
  preview.value = null; documentOpened.value = false; evidenceOpened.value = false;
  documentChecked.value = false; evidenceChecked.value = false;
  attested.value = false; confirmation.value = null; success.value = "";
}
function persistPending(kind: "confirm" | "revoke", key: string): boolean {
  try {
    window.sessionStorage.setItem(storageKey(), JSON.stringify({ kind, key,
      actor: session.view?.user.user_id, evidence_id: evidenceId() }));
    pendingKind.value = kind; pendingKey.value = key; return true;
  } catch { error.value = "无法保存待核对操作号；本次不提交，请检查浏览器会话存储。"; return false; }
}
function restorePending() {
  pendingKind.value = null; pendingKey.value = ""; lookupResult.value = null; reviewedRecovery.value = false;
  try {
    const raw = window.sessionStorage.getItem(storageKey());
    if (!raw) return;
    const saved: unknown = JSON.parse(raw);
    if (typeof saved === "object" && saved !== null && !Array.isArray(saved)) {
      const item = saved as Record<string, unknown>;
      if (item.actor === session.view?.user.user_id && item.evidence_id === evidenceId()
        && (item.kind === "confirm" || item.kind === "revoke")
        && typeof item.key === "string" && /^[\x20-\x7e]{16,128}$/.test(item.key)) {
        pendingKind.value = item.kind; pendingKey.value = item.key; return;
      }
    }
  } catch { /* Inaccessible/corrupt storage cannot authorize a new write. */ }
  pendingKind.value = "confirm"; pendingKey.value = "无法读取";
}
function clearPending() {
  try { window.sessionStorage.removeItem(storageKey()); }
  catch { error.value = "无法清除本地待核对记录；请停止提交并检查浏览器存储。"; return; }
  pendingKind.value = null; pendingKey.value = ""; lookupResult.value = null; reviewedRecovery.value = false;
}
async function lookupPending() {
  const kind = pendingKind.value, key = pendingKey.value;
  if (!mayRead() || !kind || !/^[\x20-\x7e]{16,128}$/.test(key) || busy.value) return;
  const run = generation;
  lookupResult.value = null; reviewedRecovery.value = false; error.value = ""; busy.value = true;
  try {
    const result = await attestations.lookup(kind === "confirm" ? "CONFIRM" : "REVOKE", key);
    if (mounted && run === generation && pendingKey.value === key) lookupResult.value = result;
  } catch (failure) {
    if (mounted && run === generation) error.value = failure instanceof Error ? failure.message : "无法核对原操作。";
  } finally { if (mounted && run === generation) busy.value = false; }
}
function clearCompletedPending() {
  if (lookupResult.value?.status !== "COMPLETED" || !reviewedRecovery.value) return;
  success.value = `已核对原操作：${lookupResult.value.confirmation_id}，当前状态 ${lookupResult.value.current_state}。历史收据不等于当前来源资格。`;
  clearPending();
}
async function load() {
  const target = evidenceId(), run = ++generation;
  fixed.value = null; clearPreview(); error.value = ""; busy.value = false;
  if (!mayRead()) return;
  restorePending(); busy.value = true;
  try {
    const result = await viewer.get({ kind: "GLOBAL" }, target);
    if (mounted && run === generation && evidenceId() === target) fixed.value = result;
  } catch (failure) {
    if (mounted && run === generation) error.value = failure instanceof Error ? failure.message : "无法定位来源。";
  } finally { if (mounted && run === generation) busy.value = false; }
}
function sources(): DeidentificationSources | null {
  const item = fixed.value;
  const source = sourceClass.value.trim(), classification = deidentificationClass.value.trim();
  if (!item || !/^[A-Z][A-Z0-9_]{1,63}$/.test(source)
    || !/^[A-Z][A-Z0-9_]{1,63}$/.test(classification)) return null;
  return { document_version_ids: [item.document_version_id], evidence_ids: [item.evidence_id],
    source_project_class: source, deidentification_class: classification,
    applicability: industry.value.trim() ? { industry: industry.value.trim() } : {} };
}
async function previewSources() {
  const input = sources(); if (!mayRead() || !input || busy.value || pendingKind.value) return;
  const run = generation, revision = sourceRevision;
  clearPreview(); error.value = ""; busy.value = true;
  try {
    const result = await attestations.preview(input);
    if (mounted && run === generation && revision === sourceRevision && fixed.value
      && result.document_refs.length === 1
      && result.document_refs[0]?.document_id === fixed.value.document_id
      && result.document_refs[0]?.document_version_id === fixed.value.document_version_id
      && result.evidence_ids.length === 1 && result.evidence_ids[0] === fixed.value.evidence_id) {
      preview.value = result;
    } else error.value = "预览来源与当前证据不一致，请重新定位。";
  } catch (failure) { if (mounted) error.value = failure instanceof Error ? failure.message : "无法预览。"; }
  finally { if (mounted) busy.value = false; }
}
async function confirm() {
  const input = sources(), shown = preview.value;
  if (!mayRead() || !input || !shown || !documentOpened.value || !evidenceOpened.value
    || !documentChecked.value || !evidenceChecked.value || !attested.value
    || busy.value || pendingKind.value || !session.canSubmit) return;
  const run = generation, revision = sourceRevision;
  const key = crypto.randomUUID();
  if (!persistPending("confirm", key)) return;
  busy.value = true; error.value = "";
  try {
    const expires = new Date(Date.now() + 7 * 86_400_000).toISOString();
    const result = await attestations.confirm(input, shown.source_fingerprint, expires, key);
    if (!mounted || run !== generation || revision !== sourceRevision) return;
    confirmation.value = result; clearPending(); success.value = "人工确认已提交。它不自动创建全局参考方案。";
  } catch (failure) {
    if (!mounted || run !== generation || revision !== sourceRevision) return;
    if (failure instanceof ReferenceDeidentificationError && failure.code === "SOURCE_SNAPSHOT_CHANGED") {
      clearPending(); clearPreview();
    }
    error.value = failure instanceof Error ? failure.message : "提交结果不确定，请保留操作号。";
  } finally { if (mounted) busy.value = false; }
}
async function revoke() {
  const target = confirmation.value?.confirmation_id;
  if (!mayRead() || !target || busy.value || pendingKind.value || !session.canSubmit) return;
  const run = generation;
  const key = crypto.randomUUID();
  if (!persistPending("revoke", key)) return;
  busy.value = true; error.value = "";
  try {
    await attestations.revoke(target, revokeReason.value, key);
    if (!mounted || run !== generation) return;
    clearPending(); clearPreview(); success.value = "确认已撤回；历史记录保留。";
  } catch (failure) { if (mounted && run === generation) error.value = failure instanceof Error ? failure.message : "撤回结果不确定，请保留操作号。"; }
  finally { if (mounted) busy.value = false; }
}
watch(() => route.params.evidenceId, () => { void load(); }, { immediate: true });
watch([sourceClass, deidentificationClass, industry], () => { sourceRevision += 1; clearPreview(); });
onUnmounted(() => { mounted = false; generation += 1; });
</script>

<template>
  <section class="global-attestation" aria-labelledby="attestation-title">
    <p class="section-kicker">全局参考方案</p><h1 id="attestation-title">固定来源人工脱敏核查</h1>
    <p class="warning">仅管理员本人逐项检查原文后才能声明。预览、AI 建议和本页点击记录都不是脱敏完成的证明；确认也不自动创建参考方案。</p>
    <p><RouterLink :to="{ name: 'global-evidence' }">返回全局证据</RouterLink></p>
    <p v-if="!mayRead()" role="status">需要当前 DeploymentAdmin 登录且已完成密码设置。</p>
    <template v-else>
      <p v-if="error" role="alert">{{ error }}</p><p v-if="success" role="status">{{ success }}</p>
      <section v-if="pendingKind" aria-label="待核对操作" class="warning">
        <strong>上次{{ pendingKind === 'confirm' ? '确认' : '撤回' }}结果尚待核对</strong>
        <p>操作号：<code>{{ pendingKey }}</code>。不要换号或自动重试。</p>
        <button type="button" :disabled="busy || pendingKey === '无法读取'" @click="lookupPending()">按原操作号回查</button>
        <p v-if="lookupResult?.status === 'UNCONFIRMED'" role="status">尚不能确认首次操作是否提交；保持锁定，稍后用原操作号回查。</p>
        <template v-if="lookupResult?.status === 'COMPLETED'">
          <p role="status">首次操作已完成：{{ lookupResult.confirmation_id }}；当前状态：{{ lookupResult.current_state }}。历史收据不代表当前来源仍合格。</p>
          <label><input v-model="reviewedRecovery" type="checkbox"> 我已核对首次结果与当前状态</label>
          <button type="button" :disabled="!reviewedRecovery || busy" @click="clearCompletedPending()">清除本地待核对提醒</button>
        </template>
      </section>
      <p v-if="busy" role="status">正在处理…</p>
      <template v-if="fixed">
        <h2>当前固定来源</h2>
        <p>证据：{{ fixed.display_label }}；固定文档版本：第 {{ fixed.document_version_no }} 版。</p>
        <p>定位精度：{{ fixed.precision === 'PARSED_NODE' ? '解析节点' : '整份文档' }}；位置：{{ locationText(fixed.locator) }}。提示不替代原文核查。</p>
        <label>来源项目分类（如 PLM）<input v-model="sourceClass" :disabled="busy" maxlength="64" placeholder="PLM"></label>
        <label>脱敏分类（按实际核查填写，如 DEIDENTIFIED）<input v-model="deidentificationClass" :disabled="busy" maxlength="64" placeholder="DEIDENTIFIED"></label>
        <label>适用行业（可选）<input v-model="industry" :disabled="busy" maxlength="128" placeholder="例如：离散制造"></label>
        <p>分类仅描述本次待核查来源，不会自动宣告来源已脱敏。</p>
        <button type="button" :disabled="busy || !!pendingKind || !sources()" @click="previewSources()">预览当前固定来源</button>
      </template>
      <section v-if="preview && fixed" aria-label="预览与逐项核查">
        <h2>逐项打开原文并作出判断</h2>
        <p>预览时刻：{{ preview.previewed_at }}；来源指纹：<code>{{ preview.source_fingerprint }}</code></p>
        <ol><li>固定文档版本：
          <a :href="fixed.content_url" target="_blank" rel="noopener" @click="documentOpened = true">打开固定文档版本原文</a>
          <label><input v-model="documentChecked" type="checkbox" :disabled="!documentOpened"> 我已打开并检查此文档版本</label>
        </li><li>固定证据：{{ fixed.display_label }}（{{ fixed.precision === 'PARSED_NODE' ? '解析节点' : '整文档' }}）
          <a :href="fixed.content_url" target="_blank" rel="noopener" @click="evidenceOpened = true">打开证据对应原文</a>
          <label><input v-model="evidenceChecked" type="checkbox" :disabled="!evidenceOpened"> 我已核对该证据位置和原文</label>
        </li></ol>
        <label><input v-model="attested" type="checkbox"> 我本人已逐项核查，确认此固定来源符合所填脱敏分类；不是 AI 代替我作出的判断</label>
        <button type="button" :disabled="busy || !!pendingKind || !session.canSubmit || !documentOpened || !evidenceOpened || !documentChecked || !evidenceChecked || !attested" @click="confirm()">提交人工脱敏确认（有效期 7 天）</button>
      </section>
      <section v-if="confirmation" aria-label="已提交确认">
        <h2>历史确认</h2><p>确认号：<code>{{ confirmation.confirmation_id }}</code>；到期：{{ confirmation.expires_at }}</p>
        <label>撤回原因<select v-model="revokeReason"><option value="ADMIN_REVIEW">管理员复核</option>
          <option value="SOURCE_EXPOSED">来源暴露</option><option value="SCOPE_CHANGED">范围变化</option></select></label>
        <button type="button" :disabled="busy || !!pendingKind || !session.canSubmit" @click="revoke()">撤回此确认</button>
      </section>
    </template>
  </section>
</template>

<style scoped>
.global-attestation{max-width:60rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}
.global-attestation label{display:block;margin:.8rem 0}.global-attestation input:not([type=checkbox]){display:block;min-width:18rem;padding:.45rem}
.global-attestation li{margin:.9rem 0}.global-attestation code{overflow-wrap:anywhere}.warning{padding:.8rem;border-left:.3rem solid #d29b42;background:#fff8e9}
.global-attestation [role=alert]{color:#a21d25}
</style>
