<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { EvidenceViewerClient, type EvidenceViewerDescriptor } from "@/modules/evidence/api/evidenceViewerClient";
import { ReferenceReadClient, type ReferenceCurrent } from "@/modules/solution/api/referenceReadClient";
import { ReferenceEligibilityClient, type ReferenceEligibilityReceipt } from "@/modules/solution/api/referenceEligibilityClient";
import ReferenceEligibilityPanel from "./ReferenceEligibilityPanel.vue";

const props = defineProps<{ session?: SessionClient; reader?: ReferenceReadClient; viewer?: EvidenceViewerClient;
  eligibility?: ReferenceEligibilityClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const reader = toRaw(props.reader ?? new ReferenceReadClient());
const viewer = toRaw(props.viewer ?? new EvidenceViewerClient());
const route = useRoute();
const current = ref<ReferenceCurrent | null>(null); const busy = ref(false); const error = ref("");
const selected = ref<EvidenceViewerDescriptor | null>(null); const viewerBusy = ref(false); const viewerError = ref("");
const lastDecision = ref<ReferenceEligibilityReceipt | null>(null);
let generation = 0; let viewerGeneration = 0; let mounted = true;
const projectId = () => typeof route.params.projectId === "string" ? route.params.projectId : "";
const referenceId = () => typeof route.params.referenceId === "string" ? route.params.referenceId : "";
function mayRead() {
  return mounted && !!session.view && !session.view.password_change_required
    && session.view.authorized_projects.some(item => item.project_id === projectId());
}
function locationText(locator: Readonly<Record<string, unknown>>): string {
  const source = locator.locator_type === "STRUCTURED_NODE" && typeof locator.source_locator === "object"
    && locator.source_locator !== null && !Array.isArray(locator.source_locator)
    ? locator.source_locator as Record<string, unknown> : locator;
  const kind = source.locator_type;
  if (kind === "PAGE" && typeof source.page_no === "number") return `第 ${source.page_no} 页`;
  if (kind === "TEXT_RANGE") {
    const place = typeof source.page_no === "number" ? `第 ${source.page_no} 页`
      : typeof source.section_path === "string" ? `章节 ${source.section_path}` : "文本";
    return `${place} · 字符 ${source.start_offset}–${source.end_offset}`;
  }
  if (kind === "SECTION" && typeof source.section_path === "string") return `章节 ${source.section_path}`;
  if (kind === "PARAGRAPH") return typeof source.paragraph_index === "number"
    ? `段落 ${source.paragraph_index}` : `段落锚点 ${source.stable_anchor}`;
  if (kind === "TABLE_CELL") return `表格 ${source.table_anchor} · 行 ${source.row_no} 列 ${source.column_no}`;
  if (kind === "SHEET_RANGE") return `工作表 ${source.sheet_name} · ${source.start_cell}–${source.end_cell}`;
  if (kind === "SLIDE_SHAPE") return `第 ${source.slide_no} 张幻灯片 · 形状 ${source.shape_id}`;
  return "整份文档";
}
async function load() {
  if (!mayRead() || busy.value) return;
  const project = projectId(), reference = referenceId(), run = ++generation;
  busy.value = true; error.value = ""; current.value = null;
  viewerGeneration += 1; selected.value = null; viewerBusy.value = false; viewerError.value = "";
  try {
    const result = await reader.current(project, reference);
    if (!mounted || run !== generation || project !== projectId() || reference !== referenceId()) return;
    current.value = result;
  } catch (failure) {
    if (mounted && run === generation) error.value = failure instanceof Error ? failure.message : "暂时无法读取参考方案。";
  } finally { if (mounted && run === generation) busy.value = false; }
}
async function locate(evidenceId: string) {
  if (!mayRead() || !current.value || viewerBusy.value || !current.value.evidence_ids.includes(evidenceId)) return;
  const project = projectId(), reference = referenceId(), run = ++viewerGeneration;
  selected.value = null; viewerError.value = ""; viewerBusy.value = true;
  try {
    const descriptor = await viewer.get({ kind: "PROJECT", projectId: project }, evidenceId);
    if (!mounted || run !== viewerGeneration || project !== projectId() || reference !== referenceId()
      || !current.value?.evidence_ids.includes(evidenceId)) return;
    selected.value = descriptor;
  } catch (failure) {
    if (mounted && run === viewerGeneration) viewerError.value = failure instanceof Error
      ? failure.message : "暂时无法定位固定证据原文。";
  } finally { if (mounted && run === viewerGeneration) viewerBusy.value = false; }
}
function accepted(receipt: ReferenceEligibilityReceipt) {
  lastDecision.value = receipt;
  void load();
}
watch(() => [route.params.projectId, route.params.referenceId], () => {
  generation += 1; viewerGeneration += 1; current.value = null; selected.value = null;
  lastDecision.value = null;
  busy.value = false; viewerBusy.value = false; error.value = ""; viewerError.value = "";
  void load();
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; viewerGeneration += 1; });
</script>

<template>
  <section class="reference-detail" aria-labelledby="reference-detail-title" :aria-busy="busy">
    <p class="section-kicker">项目方案</p><h1 id="reference-detail-title">参考方案详情与固定来源</h1>
    <p class="warning">这是历史固定引用，不是当前来源合格、客户确认或方案可实施的证明。点击来源时服务端将重新检查权限与文件完整性。</p>
    <p><RouterLink :to="{ name: 'project-references', params: { projectId: route.params.projectId } }">返回参考方案候选</RouterLink></p>
    <p v-if="!session.view" role="status">尚未读取当前身份，请先登录。</p>
    <p v-else-if="session.view.password_change_required" role="status">当前账户须先修改密码。</p>
    <template v-else>
      <button type="button" :disabled="busy" @click="load()">{{ busy ? "正在读取…" : "重新读取详情" }}</button>
      <p v-if="lastDecision" role="status">首次提交回执：{{ lastDecision.eligibility_state }}（{{ lastDecision.etag }}）。
        这是历史回执；下方当前标记以重新读取结果为准。</p>
      <p v-if="error" role="alert">{{ error }}</p>
      <template v-if="current"><h2>{{ current.name }}</h2>
        <p v-if="session.canSubmit && session.view?.authorized_projects.some(item => item.project_id === current?.project_id
          && (item.role === 'PROJECT_MANAGER' || item.role === 'IMPLEMENTATION_MEMBER'))">
          <RouterLink :to="{ name: 'project-reference-revise', params: { projectId: current.project_id,
            referenceId: current.reference_solution_id } }">选择固定来源并修订草稿</RouterLink>
        </p>
        <dl><dt>当前标记</dt><dd>{{ current.eligibility_state }}</dd>
          <dt>标记原因</dt><dd>{{ current.eligibility_reason ?? "未记录" }}</dd>
          <dt>版本</dt><dd>{{ current.version_no }} · {{ current.version_state }}</dd>
          <dt>来源项目分类</dt><dd>{{ current.source_project_class }}</dd>
          <dt>脱敏分类</dt><dd>{{ current.deidentification_class }}</dd>
          <dt>创建时间</dt><dd><time :datetime="current.created_at">{{ new Date(current.created_at).toLocaleString("zh-CN") }}</time></dd></dl>
        <ReferenceEligibilityPanel :current="current" :session="session" :eligibility="props.eligibility"
          @accepted="accepted" />
        <section aria-labelledby="reference-documents-title"><h3 id="reference-documents-title">固定文档版本</h3>
          <ol><li v-for="(item, index) in current.document_refs" :key="item.document_version_id">
            来源 {{ index + 1 }} · <RouterLink :to="{ name: 'project-document-detail',
              params: { projectId: current.project_id, documentId: item.document_id },
              query: { versionId: item.document_version_id } }">打开固定版本与原文下载</RouterLink>
          </li></ol></section>
        <section aria-labelledby="reference-evidence-title"><h3 id="reference-evidence-title">固定证据定位</h3>
          <p v-if="!current.evidence_ids.length">没有固定证据引用。</p>
          <ol v-else><li v-for="(item, index) in current.evidence_ids" :key="item">
            证据 {{ index + 1 }} · <button type="button" :disabled="viewerBusy" @click="locate(item)">核验并定位原文</button>
          </li></ol>
          <p v-if="viewerBusy" role="status">正在重新核验固定证据…</p><p v-if="viewerError" role="alert">{{ viewerError }}</p>
          <div v-if="selected" aria-label="受权固定证据定位"><strong>{{ selected.display_label }}</strong>
            <p>定位精度：{{ selected.precision === "PARSED_NODE" ? "解析节点" : "文档" }}；位置：{{ locationText(selected.locator) }}</p>
            <p v-if="selected.short_preview">短提示：{{ selected.short_preview }}</p>
            <p>短提示不是权威正文；当前尚未提供浏览器内精确高亮。</p>
            <RouterLink :to="{ name: 'project-document-detail', params: { projectId: current.project_id,
              documentId: selected.document_id }, query: { versionId: selected.document_version_id } }">打开对应固定文档版本</RouterLink>
            <p><a :href="selected.content_url">下载固定证据原文</a></p>
          </div>
        </section>
      </template>
    </template>
  </section>
</template>

<style scoped>
.reference-detail{max-width:60rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}.reference-detail dl{display:grid;grid-template-columns:10rem 1fr;gap:.5rem}.reference-detail dd{margin:0;overflow-wrap:anywhere}.reference-detail li{margin:.7rem 0}.warning{padding:.8rem 1rem;border-left:.3rem solid #d29b42;background:#fff8e9}.reference-detail [role=alert]{color:#a21d25}
</style>
