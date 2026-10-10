<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { EvidenceViewerClient, EvidenceViewerClientError, type EvidenceViewerDescriptor } from "@/modules/evidence/api/evidenceViewerClient";
import { SurveyReadClient, SurveyReadError, type SurveyQuestionView, type SurveySourceView,
  type SurveyVersionCursor, type SurveyVersionView, type SurveyView } from "@/modules/survey/api/surveyReadClient";
import { SurveySourceLocationClient, SurveySourceLocationClientError, type SurveySourceLocation,
  type SurveySourceLocationView } from "@/modules/survey/api/surveySourceLocationClient";

const props = defineProps<{ session?: SessionClient; surveys?: SurveyReadClient;
  sourceLocations?: SurveySourceLocationClient; evidence?: EvidenceViewerClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const surveys = toRaw(props.surveys ?? new SurveyReadClient());
const sourceLocations = toRaw(props.sourceLocations ?? new SurveySourceLocationClient());
const evidence = toRaw(props.evidence ?? new EvidenceViewerClient());
const identity = session.view; const route = useRoute();
const survey = ref<SurveyView | null>(null); const versions = ref<readonly SurveyVersionView[]>([]);
const versionCursor = ref<SurveyVersionCursor | null>(null); const selectedVersion = ref<SurveyVersionView | null>(null);
const busy = ref(false); const versionBusy = ref(false); const detailBusy = ref(false);
const error = ref(""); const versionError = ref(""); const detailError = ref("");
const locatedSources = ref<Readonly<Record<string, SurveySourceLocationView>>>({});
const locationErrors = ref<Readonly<Record<string, string>>>({}); const locationBusy = ref("");
const selectedEvidence = ref<EvidenceViewerDescriptor | null>(null); const selectedEvidenceSource = ref("");
const evidenceError = ref(""); const evidenceBusy = ref(false);
let generation = 0; let detailGeneration = 0; let locationGeneration = 0; let evidenceGeneration = 0; let mounted = true;
const answerLabels = Object.freeze({ TEXT: "文本", SINGLE_CHOICE: "单选", MULTIPLE_CHOICE: "多选",
  DATE: "日期", NUMBER: "数字", ATTACHMENT: "附件" });
const versionLabels = Object.freeze({ DRAFT: "草稿", IN_REVIEW: "评审中", APPROVED: "已批准", RETURNED: "已退回",
  SUPERSEDED: "已被替代", RESTRICTED: "受限" });

function ids() { return { projectId: typeof route.params.projectId === "string" ? route.params.projectId : "",
  surveyId: typeof route.params.surveyId === "string" ? route.params.surveyId : "" }; }
function mayRead() { return mounted && !!identity && !identity.password_change_required
  && session.view?.user.user_id === identity.user.user_id; }
function clearLocations() { locationGeneration += 1; evidenceGeneration += 1; locatedSources.value = {};
  locationErrors.value = {}; locationBusy.value = ""; selectedEvidence.value = null; selectedEvidenceSource.value = "";
  evidenceError.value = ""; evidenceBusy.value = false; }
function clearSelection() { detailGeneration += 1; selectedVersion.value = null; detailError.value = ""; detailBusy.value = false;
  clearLocations(); }
async function load() {
  if (!mayRead() || busy.value) return;
  const request = ids(); const current = ++generation;
  survey.value = null; versions.value = []; versionCursor.value = null; clearSelection();
  error.value = ""; versionError.value = ""; busy.value = true;
  try {
    const [root, page] = await Promise.all([surveys.getSurvey(request.projectId, request.surveyId),
      surveys.listVersions(request.projectId, request.surveyId)]);
    const latest = ids();
    if (!mounted || current !== generation || latest.projectId !== request.projectId
      || latest.surveyId !== request.surveyId || !mayRead()) return;
    survey.value = root; versions.value = page.items; versionCursor.value = page.next_cursor;
  } catch (failure) {
    const latest = ids();
    if (!mounted || current !== generation || latest.projectId !== request.projectId || latest.surveyId !== request.surveyId) return;
    error.value = failure instanceof SurveyReadError ? failure.message : "暂时无法读取调研定义。";
  } finally { if (mounted && current === generation) busy.value = false; }
}
async function loadMoreVersions() {
  if (!mayRead() || versionBusy.value || !versionCursor.value) return;
  const request = ids(); const next = versionCursor.value; const current = ++generation;
  versionBusy.value = true; versionError.value = "";
  try {
    const page = await surveys.listVersions(request.projectId, request.surveyId, 50, next);
    if (!mounted || current !== generation || ids().projectId !== request.projectId || ids().surveyId !== request.surveyId || !mayRead()) return;
    const known = new Set(versions.value.map(value => value.survey_version_id));
    if (page.items.some(value => known.has(value.survey_version_id))) throw new SurveyReadError("SURVEY_READ_UNAVAILABLE");
    versions.value = Object.freeze([...versions.value, ...page.items]); versionCursor.value = page.next_cursor;
  } catch (failure) {
    if (mounted && current === generation) { versions.value = []; versionCursor.value = null; clearSelection();
      versionError.value = failure instanceof SurveyReadError ? failure.message : "暂时无法读取调研版本。"; }
  } finally { if (mounted && current === generation) versionBusy.value = false; }
}
async function choose(summary: SurveyVersionView) {
  if (!mayRead() || detailBusy.value) return;
  const request = ids(); const current = ++detailGeneration;
  selectedVersion.value = null; detailError.value = ""; detailBusy.value = true; clearLocations();
  try {
    const detail = await surveys.getVersion(request.projectId, request.surveyId, summary.survey_version_id);
    if (!mounted || current !== detailGeneration || ids().projectId !== request.projectId
      || ids().surveyId !== request.surveyId || !mayRead()) return;
    selectedVersion.value = detail;
  } catch (failure) {
    if (mounted && current === detailGeneration) detailError.value = failure instanceof SurveyReadError
      ? failure.message : "暂时无法读取固定调研版本。";
  } finally { if (mounted && current === detailGeneration) detailBusy.value = false; }
}
function validationSummary(question: SurveyQuestionView): string {
  const rule = question.validation_rule;
  if (question.answer_type === "TEXT") return `文本长度 ${String(rule.min_length ?? 0)}～${String(rule.max_length ?? 4000)} 字符`;
  if (question.answer_type === "NUMBER") return `数值范围 ${String(rule.minimum ?? "不限")}～${String(rule.maximum ?? "不限")}${rule.integer ? "，仅整数" : ""}`;
  if (question.answer_type === "DATE") return `日期范围 ${String(rule.minimum ?? "不限")}～${String(rule.maximum ?? "不限")}`;
  if (question.answer_type === "MULTIPLE_CHOICE") return `选择 ${String(rule.min_selections ?? 0)}～${String(rule.max_selections ?? question.options.length)} 项`;
  if (question.answer_type === "ATTACHMENT") return `上传 ${String(rule.min_files ?? 0)}～${String(rule.max_files ?? 20)} 个文件`;
  return "选择一个选项";
}
function conditionSummary(rule: Readonly<Record<string, unknown>> | null): string {
  if (rule === null) return "始终显示";
  const children = Array.isArray(rule.all) ? rule.all : Array.isArray(rule.any) ? rule.any : null;
  if (children) return `${Array.isArray(rule.all) ? "全部" : "任一"} ${children.length} 条前置回答条件满足时显示`;
  return "前置回答条件满足时显示";
}
function sourceLabel(source: SurveySourceView): string {
  return source.source_kind === "HANDOVER_ITEM" ? "已批准的项目交接事实"
    : source.source_kind === "CAPABILITY_ITEM" ? "标准能力参考"
      : source.source_kind === "TEMPLATE_DOCUMENT_VERSION" ? "业务表单/模板参考" : "面对面调研或人工来源说明";
}
function sourceAvailability(source: SurveySourceView): string {
  return source.source_kind === "MANUAL" ? "当前只有人工来源说明；请维护访谈时间、参与人、结论及后续固定证据。"
    : "点击后由服务器重新核验当前权限并解析固定来源；页面不会猜测内部标识。";
}
function sourceKey(question: SurveyQuestionView, source: SurveySourceView): string {
  return `${question.question_id}:${source.ordinal}`;
}
function locationMessage(view: SurveySourceLocationView): string {
  if (view.unavailable_reason === "MANUAL_SOURCE_NOT_FIXED") return "人工来源尚未绑定固定原文；请按上方提示补充并在后续形成受控记录。";
  if (view.unavailable_reason === "NO_AUTHORIZED_LOCATION") return "来源记录可追溯，但当前项目身份无权展开其全局原文位置。";
  if (view.unavailable_reason === "SOURCE_TARGET_UNAVAILABLE") return "原固定目标已不可用；请保留历史说明并发起来源修订。";
  return "服务器已返回可用定位入口。";
}
function documentContentUrl(location: SurveySourceLocation): string {
  return location.location_kind === "DOCUMENT_VERSION"
    ? `/api/v1/projects/${location.project_id}/documents/${location.document_id}/versions/${location.document_version_id}/content` : "";
}
async function locateSource(question: SurveyQuestionView, source: SurveySourceView) {
  if (!mayRead() || !selectedVersion.value || locationBusy.value) return;
  const version = selectedVersion.value; const request = ids(); const key = sourceKey(question, source);
  if (!version.questions.some(item => item.question_id === question.question_id
      && item.sources.some(entry => entry.ordinal === source.ordinal && entry.source_kind === source.source_kind))) return;
  const current = ++locationGeneration; locationBusy.value = key; selectedEvidence.value = null;
  selectedEvidenceSource.value = ""; evidenceError.value = "";
  locationErrors.value = Object.freeze({ ...locationErrors.value, [key]: "" });
  try {
    const result = await sourceLocations.get(request.projectId, request.surveyId,
      version.survey_version_id, question.question_id, source.ordinal, source.source_kind);
    if (!mounted || current !== locationGeneration || selectedVersion.value?.survey_version_id !== version.survey_version_id
        || ids().projectId !== request.projectId || ids().surveyId !== request.surveyId || !mayRead()) return;
    locatedSources.value = Object.freeze({ ...locatedSources.value, [key]: result });
  } catch (failure) {
    if (mounted && current === locationGeneration) locationErrors.value = Object.freeze({ ...locationErrors.value,
      [key]: failure instanceof SurveySourceLocationClientError ? failure.message : "暂时无法定位该来源。" });
  } finally { if (mounted && current === locationGeneration) locationBusy.value = ""; }
}
async function locateEvidence(location: SurveySourceLocation, key: string) {
  if (!mayRead() || evidenceBusy.value || location.location_kind !== "EVIDENCE"
      || !locatedSources.value[key]?.locations.includes(location)) return;
  const request = ids(); const current = ++evidenceGeneration; selectedEvidence.value = null;
  selectedEvidenceSource.value = key; evidenceError.value = ""; evidenceBusy.value = true;
  try {
    const result = await evidence.get({ kind: "PROJECT", projectId: request.projectId }, location.evidence_id);
    if (!mounted || current !== evidenceGeneration || ids().projectId !== request.projectId
        || ids().surveyId !== request.surveyId || !locatedSources.value[key]?.locations.includes(location) || !mayRead()) return;
    selectedEvidence.value = result; selectedEvidenceSource.value = key;
  } catch (failure) { if (mounted && current === evidenceGeneration) evidenceError.value = failure instanceof EvidenceViewerClientError
    ? failure.message : "暂时无法定位原文。";
  } finally { if (mounted && current === evidenceGeneration) evidenceBusy.value = false; }
}
watch(() => [route.params.projectId, route.params.surveyId], () => {
  generation += 1; clearSelection(); busy.value = false; void load();
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; detailGeneration += 1; locationGeneration += 1; evidenceGeneration += 1; });
</script>

<template>
  <section class="survey-detail" aria-labelledby="survey-detail-title" :aria-busy="busy">
    <p class="section-kicker">项目调研</p><h1 id="survey-detail-title">调研版本与问题卡片</h1>
    <p class="fact-warning"><strong>实际调研记录优先，模板仅供参考。</strong> 来源说明、问题或建议均不自动成为客户确认事实。</p>
    <p><RouterLink :to="{ name: 'project-surveys', params: { projectId: route.params.projectId } }">返回调研定义列表</RouterLink></p>
    <template v-if="!identity"><p role="status">尚未读取当前身份。请先登录。</p></template>
    <template v-else-if="identity.password_change_required"><p role="status">当前账户须先修改密码，暂不能读取调研定义。</p></template>
    <template v-else>
      <button type="button" :disabled="busy" @click="load()">{{ busy ? "正在读取…" : "刷新定义与版本" }}</button>
      <p v-if="error" role="alert">{{ error }}</p>
      <dl v-if="survey"><dt>名称</dt><dd>{{ survey.name }}</dd><dt>状态</dt><dd>{{ survey.state }}</dd>
        <dt>当前批准版本</dt><dd>{{ survey.current_approved_version_ref ? "已形成" : "尚未形成" }}</dd>
        <dt>版本标记</dt><dd>{{ survey.etag }}</dd></dl>
      <section v-if="survey" aria-labelledby="survey-versions-title"><h2 id="survey-versions-title">固定版本</h2>
        <p v-if="!versions.length">暂无可见版本。</p><p v-if="versionError" role="alert">{{ versionError }}</p>
        <ol><li v-for="value in versions" :key="value.survey_version_id"><strong>版本 {{ value.version_no }}</strong>
          <span> · {{ versionLabels[value.state] }} · {{ value.declared_question_count }} 个问题</span>
          <button type="button" :disabled="detailBusy" @click="choose(value)">查看版本 {{ value.version_no }} 的问题卡片</button></li></ol>
        <button v-if="versionCursor" type="button" :disabled="versionBusy" @click="loadMoreVersions">加载更多版本</button>
      </section>
      <section v-if="selectedVersion || detailBusy || detailError" aria-labelledby="survey-questions-title">
        <h2 id="survey-questions-title">问题卡片</h2>
        <p v-if="detailBusy" role="status">正在重新核验并读取固定版本…</p><p v-if="detailError" role="alert">{{ detailError }}</p>
        <template v-if="selectedVersion">
          <p>固定版本 {{ selectedVersion.version_no }} · {{ versionLabels[selectedVersion.state] }}；共 {{ selectedVersion.questions.length }} 个问题。</p>
          <p>目标部门：{{ selectedVersion.target_departments.length }} 个受控引用 ·
            <RouterLink :to="{ name: 'project-departments', params: { projectId: route.params.projectId } }">核对项目部门历史</RouterLink></p>
          <article v-for="question in selectedVersion.questions" :key="question.question_id" class="question-card">
            <header><strong>{{ question.sequence_no + 1 }}. {{ question.topic }}</strong><span>{{ answerLabels[question.answer_type] }}</span></header>
            <p class="question-text">{{ question.question_text }}</p>
            <dl><dt>调研目的</dt><dd>{{ question.objective }}</dd><dt>需要维护</dt>
              <dd>{{ question.required ? "必填" : "选填" }}的{{ answerLabels[question.answer_type] }}回答；{{ validationSummary(question) }}</dd>
              <dt>预期输出</dt><dd>{{ question.expected_output }}</dd><dt>证据要求</dt>
              <dd>{{ question.evidence_required ? "回答时需提供证据" : "当前未强制证据" }}</dd>
              <dt>显示条件</dt><dd>{{ conditionSummary(question.condition_rule) }}</dd></dl>
            <ul v-if="question.options.length" aria-label="问题选项"><li v-for="option in question.options" :key="option.option_code">
              {{ option.label }}<template v-if="option.description">：{{ option.description }}</template></li></ul>
            <section class="source-guide" aria-label="问题来源"><h3>来源与定位</h3>
              <article v-for="source in question.sources" :key="source.ordinal" class="source-item">
                <strong>{{ sourceLabel(source) }}</strong><p v-if="source.manual_source_note">{{ source.manual_source_note }}</p>
                <p v-if="source.source_kind === 'TEMPLATE_DOCUMENT_VERSION'" class="template-warning">模板仅供问题结构参考，不是客户事实。</p>
                <p>{{ sourceAvailability(source) }}</p>
                <button type="button" :disabled="!!locationBusy || evidenceBusy"
                  @click="locateSource(question, source)">{{ locationBusy === sourceKey(question, source) ? "正在定位…" : "定位该固定来源" }}</button>
                <p v-if="locationErrors[sourceKey(question, source)]" role="alert">{{ locationErrors[sourceKey(question, source)] }}</p>
                <section v-if="locatedSources[sourceKey(question, source)]" class="location-result">
                  <p>{{ locationMessage(locatedSources[sourceKey(question, source)]!) }}</p>
                  <p v-if="!locatedSources[sourceKey(question, source)]!.current_eligibility" class="history-warning">
                    此来源仍可用于历史追溯，但已不再满足当前来源资格，不能当作当前确认事实。</p>
                  <ul v-if="locatedSources[sourceKey(question, source)]!.locations.length">
                    <li v-for="location in locatedSources[sourceKey(question, source)]!.locations"
                      :key="`${location.location_kind}:${location.location_kind === 'EVIDENCE' ? location.evidence_id : location.location_kind === 'DOCUMENT_VERSION' ? location.document_version_id : location.analysis_item_id}`">
                      <RouterLink v-if="location.location_kind === 'BUSINESS_RECORD'"
                        :to="{ name: 'project-handover-detail', params: { projectId: location.project_id,
                          analysisId: location.handover_analysis_id }, query: { version: location.handover_analysis_version_id,
                          item: location.analysis_item_id } }">打开交接分析中的固定问题</RouterLink>
                      <template v-else-if="location.location_kind === 'DOCUMENT_VERSION'">
                        <RouterLink :to="{ name: 'project-document-detail', params: { projectId: location.project_id,
                          documentId: location.document_id }, query: { version: location.document_version_id } }">查看固定文档版本历史</RouterLink>
                        <span> · <a :href="documentContentUrl(location)" target="_blank" rel="noopener noreferrer">打开受权固定版本原文</a></span>
                      </template>
                      <button v-else type="button" :disabled="evidenceBusy"
                        @click="locateEvidence(location, sourceKey(question, source))">{{ evidenceBusy ? "正在核验原文…" : "定位原文证据" }}</button>
                    </li>
                  </ul>
                  <section v-if="selectedEvidence && selectedEvidenceSource === sourceKey(question, source)" class="located-evidence">
                    <h4>已核验的原文位置</h4><p>{{ selectedEvidence.display_label }} · 固定文档版本 {{ selectedEvidence.document_version_no }}</p>
                    <p v-if="selectedEvidence.short_preview">短提示：{{ selectedEvidence.short_preview }}（不是权威正文）</p>
                    <a :href="selectedEvidence.content_url" target="_blank" rel="noopener noreferrer">打开受权固定版本</a>
                  </section>
                  <p v-if="evidenceError && selectedEvidenceSource === sourceKey(question, source)" role="alert">{{ evidenceError }}</p>
                </section>
              </article>
            </section>
          </article>
        </template>
      </section>
    </template>
  </section>
</template>

<style scoped>
.survey-detail { max-width: 62rem; margin: 1rem auto; padding: 1.5rem; background: #fff; border-radius: 1rem; }
.survey-detail dl { display: grid; grid-template-columns: 8rem 1fr; gap: .5rem 1rem; }.survey-detail dd { margin: 0; overflow-wrap: anywhere; }
.survey-detail ol { display: grid; gap: .6rem; }.survey-detail ol li { display: flex; flex-wrap: wrap; gap: .5rem; align-items: center; }
.question-card { display: grid; gap: .5rem; margin: 1rem 0; padding: 1rem; border: 1px solid #d8dee7; border-radius: .75rem; overflow-wrap: anywhere; }
.question-card > header { display: flex; justify-content: space-between; gap: 1rem; }.question-text { font-size: 1.05rem; }
.source-guide { padding: .8rem; background: #f4f7fb; border-radius: .5rem; }.source-item { padding: .55rem 0; border-top: 1px solid #d8dee7; }
.source-item:first-of-type { border-top: 0; }.template-warning { color: #7a4b00; font-weight: 600; }
.location-result { margin-top: .5rem; padding: .7rem; background: #eef7f1; border-radius: .4rem; }.location-result li { margin: .4rem 0; }
.history-warning { color: #7a4b00; font-weight: 600; }.located-evidence { margin-top: .6rem; padding: .6rem; border-left: .25rem solid #39724f; }
.fact-warning { padding: .8rem 1rem; border-left: .3rem solid #d29b42; background: #fff8e9; }.survey-detail [role="alert"] { color: #a21d25; }
</style>
