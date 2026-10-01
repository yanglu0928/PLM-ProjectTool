<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { EvidenceListClient, EvidenceListError, type EvidenceSummary } from "@/modules/evidence/api/evidenceListClient";
import { EvidenceViewerClient, EvidenceViewerClientError,
  type EvidenceViewerDescriptor } from "@/modules/evidence/api/evidenceViewerClient";
import { EvidenceEligibilityClient, EvidenceEligibilityClientError,
  type CurrentEvidenceEligibility, type EvidenceEligibilityFirstReceipt } from "@/modules/evidence/api/evidenceEligibilityClient";

const props = defineProps<{ session?: SessionClient; listClient?: EvidenceListClient;
  viewerClient?: EvidenceViewerClient; eligibilityClient?: EvidenceEligibilityClient;
  previewFetch?: typeof fetch }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const lists = toRaw(props.listClient ?? new EvidenceListClient());
const viewers = toRaw(props.viewerClient ?? new EvidenceViewerClient());
const eligibility = toRaw(props.eligibilityClient ?? new EvidenceEligibilityClient(session));
const previewFetch = props.previewFetch ?? fetch;
const identity = session.view;
const route = useRoute();
const items = ref<readonly EvidenceSummary[]>([]);
const cursor = ref<string | null>(null);
const loaded = ref(false);
const busy = ref(false);
const error = ref("");
const selected = ref<EvidenceViewerDescriptor | null>(null);
const selectedBusy = ref<string | null>(null);
const selectedError = ref("");
const pdfUrl = ref<string | null>(null);
const previewBusy = ref(false);
const previewError = ref("");
const decisionCurrent = ref<CurrentEvidenceEligibility | null>(null);
const decisionTarget = ref<"ELIGIBLE" | "INELIGIBLE" | null>(null);
const decisionReason = ref("");
const decisionAttested = ref(false);
const decisionBusy = ref(false);
const decisionError = ref("");
const decisionReceipt = ref<EvidenceEligibilityFirstReceipt | null>(null);
const decisionKey = ref<string | null>(null);
const decisionUncertain = ref(false);
const unresolved = ref<{ actorId: string; projectId: string; evidenceId: string; key: string } | null>(null);
let generation = 0;
let selectionGeneration = 0;
let previewGeneration = 0;
let previewController: AbortController | null = null;
let mounted = true;

function projectId(): string { return typeof route.params.projectId === "string" ? route.params.projectId : ""; }
function mayRead(): boolean {
  return mounted && !!identity && !identity.password_change_required
    && session.view?.user.user_id === identity.user.user_id;
}
function clearSelection() {
  selectionGeneration += 1;
  clearPreview();
  clearDecision();
  selected.value = null;
  selectedBusy.value = null;
  selectedError.value = "";
}
function clearDecision() {
  decisionCurrent.value = null; decisionTarget.value = null; decisionReason.value = "";
  decisionAttested.value = false; decisionBusy.value = false;
  decisionError.value = ""; decisionReceipt.value = null;
  decisionKey.value = null; decisionUncertain.value = false;
}
function mayDecide(): boolean {
  const project = projectId();
  const role = identity?.authorized_projects.find((entry) => entry.project_id === project)?.role;
  return mayRead() && !!selected.value && (role === "PROJECT_MANAGER" || role === "CUSTOMER_MANAGER")
    && !(unresolved.value?.projectId === project
      && unresolved.value.actorId === session.view?.user.user_id)
    && items.value.some((item) => item.evidence_id === selected.value?.evidence_id
      && item.eligibility_state === "CANDIDATE");
}
async function prepareDecision() {
  const view = selected.value;
  if (!mayDecide() || !view || decisionBusy.value || decisionUncertain.value) return;
  const currentSelection = selectionGeneration;
  const project = projectId();
  decisionBusy.value = true; decisionError.value = ""; decisionReceipt.value = null;
  try {
    const current = await eligibility.current(project, view.evidence_id);
    if (!mounted || currentSelection !== selectionGeneration || projectId() !== project
      || selected.value !== view || !mayRead()) return;
    if (current.document_id !== view.document_id
      || current.document_version_id !== view.document_version_id
      || current.eligibility_state !== "CANDIDATE") {
      throw new EvidenceEligibilityClientError("EVIDENCE_ELIGIBILITY_INVALID");
    }
    decisionCurrent.value = current;
  } catch (failure) {
    if (mounted && currentSelection === selectionGeneration) {
      decisionError.value = failure instanceof EvidenceEligibilityClientError
        ? failure.message : "暂时无法准备资格确认，请重新核对原文。";
    }
  } finally { if (mounted && currentSelection === selectionGeneration) decisionBusy.value = false; }
}
async function submitDecision() {
  const view = selected.value;
  const before = decisionCurrent.value;
  const target = decisionTarget.value;
  const justification = decisionReason.value;
  if (!mayDecide() || !view || !before || !target || !decisionAttested.value
    || decisionBusy.value || decisionUncertain.value || !session.canSubmit) return;
  const project = projectId();
  const currentSelection = selectionGeneration;
  const key = crypto.randomUUID();
  decisionKey.value = key; decisionBusy.value = true; decisionError.value = "";
  try {
    const receipt = await eligibility.set(project, before, view, target, justification, key);
    if (!mounted || currentSelection !== selectionGeneration || projectId() !== project
      || selected.value !== view || !mayRead()) return;
    decisionReceipt.value = receipt; decisionCurrent.value = null;
    unresolved.value = null;
  } catch (failure) {
    if (mounted && currentSelection === selectionGeneration) {
      decisionError.value = failure instanceof EvidenceEligibilityClientError
        ? failure.message : "资格提交结果暂无法确认，请核对当前状态和审计。";
      decisionUncertain.value = !(failure instanceof EvidenceEligibilityClientError)
        || failure.code === "EVIDENCE_ELIGIBILITY_UNCERTAIN";
      if (decisionUncertain.value) unresolved.value = {
        actorId: identity!.user.user_id, projectId: project, evidenceId: before.evidence_id, key,
      };
      else decisionKey.value = null;
    }
  } finally { if (mounted && currentSelection === selectionGeneration) decisionBusy.value = false; }
}
function clearPreview() {
  previewGeneration += 1;
  previewController?.abort(); previewController = null;
  if (pdfUrl.value) URL.revokeObjectURL(pdfUrl.value.split("#")[0]!);
  pdfUrl.value = null; previewBusy.value = false; previewError.value = "";
}
function pageNumber(view: EvidenceViewerDescriptor): number | null {
  const locator = view.locator.locator_type === "STRUCTURED_NODE"
    ? view.locator.source_locator : view.locator;
  if (!locator || typeof locator !== "object" || Array.isArray(locator)) return null;
  const source = locator as Record<string, unknown>;
  if ((source.locator_type === "PAGE" || source.locator_type === "TEXT_RANGE")
    && typeof source.page_no === "number" && Number.isSafeInteger(source.page_no)
    && source.page_no > 0) return source.page_no;
  return null;
}
async function previewPdf() {
  const view = selected.value;
  if (!mayRead() || !view || view.detected_mime !== "application/pdf" || previewBusy.value) return;
  clearPreview();
  if (view.size_bytes === 0 || view.size_bytes > 20_000_000) {
    previewError.value = "文件为空或超过 20 MB，暂不在浏览器预览；可下载固定版本查看。";
    return;
  }
  const current = ++previewGeneration;
  const project = projectId();
  const controller = new AbortController();
  previewController = controller; previewBusy.value = true;
  const timer = window.setTimeout(() => controller.abort(), 30_000);
  try {
    const response = await previewFetch(view.content_url, { method: "GET", credentials: "same-origin",
      cache: "no-store", redirect: "error", headers: { Accept: "application/pdf" },
      signal: controller.signal });
    const length = response.headers.get("content-length");
    if (!response.ok || response.status !== 200
      || response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/pdf"
      || length === null || Number(length) !== view.size_bytes || !response.body) {
      throw new Error("invalid PDF response");
    }
    const bytes = new Uint8Array(view.size_bytes);
    const reader = response.body.getReader();
    let received = 0;
    try {
      while (true) {
        const part = await reader.read();
        if (part.done) break;
        if (received + part.value.byteLength > bytes.byteLength) throw new Error("PDF response exceeds fixed size");
        bytes.set(part.value, received);
        received += part.value.byteLength;
      }
    } finally { reader.releaseLock(); }
    if (received !== view.size_bytes) throw new Error("PDF response length mismatch");
    if (!mounted || current !== previewGeneration || projectId() !== project
      || selected.value !== view || !mayRead()) return;
    const objectUrl = URL.createObjectURL(new Blob([bytes], { type: "application/pdf" }));
    const page = pageNumber(view);
    pdfUrl.value = page === null ? objectUrl : `${objectUrl}#page=${page}`;
  } catch {
    if (mounted && current === previewGeneration) {
      previewError.value = "PDF 页级预览不可用；请下载固定版本查看，勿将预览失败视为原文已核验失效。";
    }
  } finally {
    window.clearTimeout(timer);
    if (mounted && current === previewGeneration) {
      previewBusy.value = false; previewController = null;
    }
  }
}
async function load(refresh = false) {
  if (!mayRead() || busy.value) return;
  if (refresh) {
    generation += 1; items.value = []; cursor.value = null; loaded.value = false;
    clearSelection();
  } else if (loaded.value && !cursor.value) return;
  const project = projectId();
  const after = cursor.value;
  const current = ++generation;
  busy.value = true; error.value = "";
  try {
    const page = await lists.list({ kind: "PROJECT", projectId: project }, after);
    if (!mounted || current !== generation || projectId() !== project || !mayRead()) return;
    const previous = after ? items.value : [];
    if (page.items.some((item) => previous.some((older) => older.evidence_id === item.evidence_id))) {
      throw new EvidenceListError("EVIDENCE_LIST_UNAVAILABLE");
    }
    items.value = [...previous, ...page.items];
    cursor.value = page.next_cursor;
    loaded.value = true;
  } catch (failure) {
    if (!mounted || current !== generation || projectId() !== project) return;
    error.value = failure instanceof EvidenceListError ? failure.message : "暂时无法读取证据，请稍后重试。";
  } finally { if (mounted && current === generation) busy.value = false; }
}
async function locate(item: EvidenceSummary) {
  if (!mayRead() || !items.value.some((entry) => entry.evidence_id === item.evidence_id)) return;
  const project = projectId();
  clearPreview();
  clearDecision();
  const current = ++selectionGeneration;
  selected.value = null; selectedError.value = ""; selectedBusy.value = item.evidence_id;
  try {
    const view = await viewers.get({ kind: "PROJECT", projectId: project }, item.evidence_id);
    if (!mounted || current !== selectionGeneration || projectId() !== project || !mayRead()) return;
    if (view.document_id !== item.document_id || view.document_version_id !== item.document_version_id) {
      throw new EvidenceViewerClientError("EVIDENCE_CLIENT_UNAVAILABLE");
    }
    selected.value = view;
  } catch (failure) {
    if (!mounted || current !== selectionGeneration || projectId() !== project) return;
    selectedError.value = failure instanceof EvidenceViewerClientError
      ? failure.message : "暂时无法定位原文，请稍后重试。";
  } finally { if (mounted && current === selectionGeneration) selectedBusy.value = null; }
}
function position(view: EvidenceViewerDescriptor): string {
  const locator = view.locator.locator_type === "STRUCTURED_NODE"
    ? view.locator.source_locator : view.locator;
  if (!locator || typeof locator !== "object" || Array.isArray(locator)) return view.display_label;
  const source = locator as Record<string, unknown>;
  if (source.locator_type === "PAGE" || source.locator_type === "TEXT_RANGE" && typeof source.page_no === "number") {
    return `第 ${source.page_no} 页`;
  }
  if (source.locator_type === "SECTION") return `章节 ${source.section_path}`;
  if (source.locator_type === "SHEET_RANGE") return `工作表 ${source.sheet_name} · ${source.start_cell}:${source.end_cell}`;
  if (source.locator_type === "SLIDE_SHAPE") return `第 ${source.slide_no} 张幻灯片`;
  if (source.locator_type === "PARAGRAPH") return source.paragraph_index
    ? `第 ${source.paragraph_index} 段` : `段落锚点 ${source.stable_anchor}`;
  if (source.locator_type === "TABLE_CELL") return `表格 ${source.table_anchor} · 第 ${source.row_no} 行、第 ${source.column_no} 列`;
  if (source.locator_type === "DOCUMENT") return "整份文档";
  return view.display_label;
}
watch(() => route.params.projectId, () => {
  generation += 1; items.value = []; cursor.value = null; loaded.value = false;
  busy.value = false; error.value = ""; clearSelection();
  void load();
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; clearSelection(); });
</script>

<template>
  <section class="evidence-list" aria-labelledby="evidence-list-title" :aria-busy="busy">
    <p class="section-kicker">项目资料</p>
    <h1 id="evidence-list-title">项目证据</h1>
    <p>先查看证据的短提示。点击“定位原文”后，系统会重新核验权限、固定文档版本及来源指纹；短提示不是权威正文。</p>
    <p><RouterLink :to="{ name: 'project-detail', params: { projectId: route.params.projectId } }">返回项目</RouterLink></p>
    <template v-if="!identity">
      <p role="status">尚未读取当前身份。请先登录，或在账户页读取当前身份。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else-if="identity.password_change_required">
      <p role="status">当前账户须先修改密码，暂不能读取项目证据。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else>
      <button type="button" :disabled="busy" @click="load(true)">{{ busy ? '正在读取…' : '刷新证据列表' }}</button>
      <p v-if="busy" role="status">正在确认项目证据访问权限…</p>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="loaded && items.length === 0">暂无证据。</p>
      <ol v-if="items.length" aria-label="项目证据列表">
        <li v-for="item in items" :key="item.evidence_id">
          <strong>{{ item.display_label }}</strong>
          <span> · {{ item.eligibility_state === 'CANDIDATE' ? '待核定' : item.eligibility_state === 'ELIGIBLE'
            ? '可用' : item.eligibility_state === 'INELIGIBLE' ? '不可用' : '已撤销' }}</span>
          <p v-if="item.display_excerpt">{{ item.display_excerpt }}</p>
          <button type="button" :disabled="selectedBusy !== null" @click="locate(item)">
            {{ selectedBusy === item.evidence_id ? '正在核验原文…' : '定位原文' }}
          </button>
        </li>
      </ol>
      <button v-if="cursor" type="button" :disabled="busy" @click="load()">继续加载证据</button>
      <p v-if="unresolved && unresolved.projectId === projectId()
        && unresolved.actorId === session.view?.user.user_id" role="alert">
        一项资格提交结果尚未确认（证据 {{ unresolved.evidenceId }}，操作号 {{ unresolved.key }}）。
        刷新列表后提醒仍保留；请核对当前资格与审计，勿换新操作号重复提交。
      </p>
      <p v-if="selectedError" role="alert">{{ selectedError }}</p>
      <section v-if="selected" aria-labelledby="evidence-location-title">
        <h2 id="evidence-location-title">已核验的原文位置</h2>
        <dl>
          <dt>位置</dt><dd>{{ position(selected) }}</dd>
          <dt>固定文档版本</dt><dd>第 {{ selected.document_version_no }} 版</dd>
          <dt>来源证明</dt><dd>{{ selected.precision === 'DOCUMENT' ? '整文档已核验' : '解析节点已核验' }}</dd>
          <template v-if="selected.short_preview"><dt>短提示</dt><dd>{{ selected.short_preview }}</dd></template>
        </dl>
        <p>当前位置由来源定位证明；浏览器内的精确高亮尚未提供。下载时服务器会再次验证权限与文件完整性。</p>
        <template v-if="selected.detected_mime === 'application/pdf'">
          <button type="button" :disabled="previewBusy" @click="previewPdf()">
            {{ previewBusy ? '正在准备页级预览…' : '预览固定版本 PDF' }}
          </button>
          <p>浏览器支持时{{ pageNumber(selected) === null ? '从首页打开' : `尝试跳转至第 ${pageNumber(selected)} 页` }}；不保证精确高亮。</p>
          <p v-if="previewError" role="alert">{{ previewError }}</p>
          <iframe v-if="pdfUrl" :src="pdfUrl" title="固定版本 PDF 页级预览"
            sandbox="allow-same-origin" referrerpolicy="no-referrer" class="pdf-preview" />
        </template>
        <p><a :href="selected.content_url">下载固定版本原文</a></p>
        <p><RouterLink :to="{ name: 'project-document-detail', params: {
          projectId: route.params.projectId, documentId: selected.document_id } }">查看文档版本历史</RouterLink></p>
        <section v-if="mayDecide()" aria-labelledby="evidence-decision-title">
          <h3 id="evidence-decision-title">人工核定证据资格</h3>
          <p>先核对上方固定版本原文。业务表单模板只能作结构或问题参考，不能独立确认为客户现状；AI 建议和短提示均不是正式事实。</p>
          <button v-if="!decisionCurrent && !decisionReceipt && !decisionUncertain" type="button"
            :disabled="decisionBusy" @click="prepareDecision()">
            {{ decisionBusy ? '正在读取当前资格…' : '准备人工确认' }}
          </button>
          <form v-if="decisionCurrent" @submit.prevent="submitDecision()">
            <p>当前资格：待核定。请根据原文决定，说明具体核对依据；不要仅填写“已确认”。</p>
            <fieldset :disabled="decisionBusy || decisionUncertain">
              <legend>资格结论</legend>
              <label><input v-model="decisionTarget" type="radio" value="ELIGIBLE"> 可用：已核对实际来源</label>
              <label><input v-model="decisionTarget" type="radio" value="INELIGIBLE"> 不可用：来源或用途不足</label>
            </fieldset>
            <label for="evidence-decision-reason">人工确认理由</label>
            <textarea id="evidence-decision-reason" v-model="decisionReason" maxlength="1024" rows="4"
              placeholder="写明核对的实际调研记录、具体位置及可用/不可用原因；如与模板冲突，请说明实际记录。" />
            <label><input v-model="decisionAttested" type="checkbox"> 我已核对固定版本原文，以上是我的人工判断</label>
            <button type="submit" :disabled="decisionBusy || decisionUncertain || !decisionTarget
              || !decisionAttested || !decisionReason.trim() || !session.canSubmit">
              {{ decisionBusy ? '正在提交…' : '提交资格裁定' }}
            </button>
          </form>
          <p v-if="decisionReceipt" role="status">首次提交回执：{{ decisionReceipt.eligibility_state === 'ELIGIBLE' ? '可用' : '不可用' }}。
            回执不代表当前状态；请刷新证据列表并核对审计。</p>
          <p v-if="decisionError" role="alert">{{ decisionError }}</p>
          <p v-if="decisionUncertain && decisionKey" role="status">本次操作号：{{ decisionKey }}。请先重新读取资格和审计；不要换新操作号重复提交。</p>
        </section>
      </section>
    </template>
  </section>
</template>

<style scoped>
.evidence-list { max-width: 48rem; margin: 1rem auto; padding: 1.5rem; background: #fff; border-radius: 1rem; }
.evidence-list p { line-height: 1.65; }
.evidence-list ol { padding-left: 1.4rem; }
.evidence-list li { margin-block: 1rem; overflow-wrap: anywhere; }
.evidence-list dl { display: grid; grid-template-columns: minmax(8rem, auto) 1fr; gap: .65rem 1rem; }
.evidence-list dt { font-weight: 700; }
.evidence-list dd { margin: 0; overflow-wrap: anywhere; }
.evidence-list [role="alert"] { color: #a21d25; }
.pdf-preview { width: 100%; height: 36rem; border: 1px solid #b7c4d3; }
.evidence-list fieldset { display: grid; gap: .5rem; margin: 1rem 0; }
.evidence-list textarea { display: block; width: 100%; max-width: 100%; margin: .5rem 0 1rem; }
</style>
