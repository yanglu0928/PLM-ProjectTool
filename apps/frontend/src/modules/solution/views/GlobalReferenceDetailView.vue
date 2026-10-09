<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { EvidenceViewerClient, type EvidenceViewerDescriptor } from "@/modules/evidence/api/evidenceViewerClient";
import { GlobalReferenceReadClient, type GlobalReferenceCurrent } from "@/modules/solution/api/globalReferenceReadClient";

const props = defineProps<{ session?: SessionClient; reader?: GlobalReferenceReadClient;
  viewer?: EvidenceViewerClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const reader = toRaw(props.reader ?? new GlobalReferenceReadClient());
const viewer = toRaw(props.viewer ?? new EvidenceViewerClient());
const route = useRoute();
const current = ref<GlobalReferenceCurrent | null>(null);
const busy = ref(false); const error = ref("");
const selected = ref<EvidenceViewerDescriptor | null>(null);
const viewerBusy = ref(false); const viewerError = ref("");
let generation = 0; let viewerGeneration = 0; let mounted = true;
const referenceId = () => typeof route.params.referenceId === "string" ? route.params.referenceId : "";
function mayRead() {
  return mounted && session.view?.deployment_role === "DEPLOYMENT_ADMIN"
    && !session.view.password_change_required;
}
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
async function load() {
  if (!mayRead() || busy.value) return;
  const identity = referenceId(), run = ++generation;
  busy.value = true; error.value = ""; current.value = null;
  viewerGeneration += 1; selected.value = null; viewerBusy.value = false; viewerError.value = "";
  try {
    const result = await reader.current(identity);
    if (!mounted || run !== generation || identity !== referenceId() || !mayRead()) return;
    current.value = result;
  } catch (failure) {
    if (mounted && run === generation) error.value = failure instanceof Error
      ? failure.message : "暂时无法读取全局参考方案。";
  } finally { if (mounted && run === generation) busy.value = false; }
}
async function locate(evidenceId: string) {
  if (!mayRead() || !current.value || viewerBusy.value || !current.value.evidence_ids.includes(evidenceId)) return;
  const identity = referenceId(), run = ++viewerGeneration;
  selected.value = null; viewerError.value = ""; viewerBusy.value = true;
  try {
    const descriptor = await viewer.get({ kind: "GLOBAL" }, evidenceId);
    if (!mounted || run !== viewerGeneration || identity !== referenceId()
      || !current.value?.evidence_ids.includes(evidenceId) || !mayRead()) return;
    selected.value = descriptor;
  } catch (failure) {
    if (mounted && run === viewerGeneration) viewerError.value = failure instanceof Error
      ? failure.message : "暂时无法定位固定证据原文。";
  } finally { if (mounted && run === viewerGeneration) viewerBusy.value = false; }
}
watch(() => route.params.referenceId, () => {
  generation += 1; viewerGeneration += 1; current.value = null; selected.value = null;
  busy.value = false; viewerBusy.value = false; error.value = ""; viewerError.value = "";
  void load();
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; viewerGeneration += 1; });
</script>

<template>
  <section class="global-reference-detail" aria-labelledby="global-reference-detail-title" :aria-busy="busy">
    <p class="section-kicker">平台方案</p><h1 id="global-reference-detail-title">全局参考方案详情与固定来源</h1>
    <p class="warning">这是历史固定引用，不是当前来源合格、脱敏确认未撤回或方案已获客户批准的证明。打开来源时服务端会重新检查权限与文件完整性。</p>
    <p><RouterLink :to="{ name: 'global-references' }">返回全局参考方案候选</RouterLink></p>
    <p v-if="!session.view" role="status">尚未读取当前身份，请先登录。</p>
    <p v-else-if="session.view.password_change_required" role="status">当前账户须先修改密码。</p>
    <p v-else-if="session.view.deployment_role !== 'DEPLOYMENT_ADMIN'" role="status">当前账户无权查看全局参考方案。</p>
    <template v-else>
      <button type="button" :disabled="busy" @click="load()">{{ busy ? "正在读取…" : "重新读取详情" }}</button>
      <p v-if="error" role="alert">{{ error }}</p>
      <template v-if="current"><h2>{{ current.name }}</h2>
        <p><RouterLink :to="{ name: 'global-reference-revise', params: { referenceId: current.reference_solution_id } }">修订此全局参考方案（新建草稿版本）</RouterLink></p>
        <dl><dt>当前标记</dt><dd>{{ current.eligibility_state }}</dd>
          <dt>标记原因</dt><dd>{{ current.eligibility_reason ?? "未记录" }}</dd>
          <dt>版本</dt><dd>{{ current.version_no }} · {{ current.version_state }}</dd>
          <dt>来源项目分类</dt><dd>{{ current.source_project_class }}</dd>
          <dt>脱敏分类</dt><dd>{{ current.deidentification_class }}</dd>
          <dt>创建时间</dt><dd><time :datetime="current.created_at">{{ new Date(current.created_at).toLocaleString("zh-CN") }}</time></dd></dl>
        <section aria-labelledby="global-reference-documents-title"><h3 id="global-reference-documents-title">固定文档版本</h3>
          <ol><li v-for="(item, index) in current.document_refs" :key="item.document_version_id">
            来源 {{ index + 1 }} · <a :href="`/api/v1/global/documents/${item.document_id}/versions/${item.document_version_id}/content`"
              target="_blank" rel="noopener">打开固定文档版本原文</a>
          </li></ol></section>
        <section aria-labelledby="global-reference-evidence-title"><h3 id="global-reference-evidence-title">固定证据定位</h3>
          <p v-if="!current.evidence_ids.length">没有固定证据引用。</p>
          <ol v-else><li v-for="(item, index) in current.evidence_ids" :key="item">
            证据 {{ index + 1 }} · <button type="button" :disabled="viewerBusy" @click="locate(item)">核验并定位原文</button>
          </li></ol>
          <p v-if="viewerBusy" role="status">正在重新核验固定证据…</p><p v-if="viewerError" role="alert">{{ viewerError }}</p>
          <div v-if="selected" aria-label="受权固定证据定位"><strong>{{ selected.display_label }}</strong>
            <p>定位精度：{{ selected.precision === "PARSED_NODE" ? "解析节点" : "文档" }}；位置：{{ locationText(selected.locator) }}</p>
            <p v-if="selected.short_preview">短提示：{{ selected.short_preview }}</p>
            <p>短提示不是权威正文；当前尚未提供浏览器内精确高亮。</p>
            <p><a :href="selected.content_url" target="_blank" rel="noopener">下载固定证据原文</a></p>
          </div>
        </section>
      </template>
    </template>
  </section>
</template>

<style scoped>
.global-reference-detail{max-width:60rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}.global-reference-detail dl{display:grid;grid-template-columns:10rem 1fr;gap:.5rem}.global-reference-detail dd{margin:0;overflow-wrap:anywhere}.global-reference-detail li{margin:.7rem 0}.warning{padding:.8rem 1rem;border-left:.3rem solid #d29b42;background:#fff8e9}.global-reference-detail [role=alert]{color:#a21d25}
</style>
