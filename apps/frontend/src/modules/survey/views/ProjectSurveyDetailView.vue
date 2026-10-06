<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { SurveyReadClient, SurveyReadError, type SurveyQuestionView, type SurveySourceView,
  type SurveyVersionCursor, type SurveyVersionView, type SurveyView } from "@/modules/survey/api/surveyReadClient";

const props = defineProps<{ session?: SessionClient; surveys?: SurveyReadClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const surveys = toRaw(props.surveys ?? new SurveyReadClient());
const identity = session.view; const route = useRoute();
const survey = ref<SurveyView | null>(null); const versions = ref<readonly SurveyVersionView[]>([]);
const versionCursor = ref<SurveyVersionCursor | null>(null); const selectedVersion = ref<SurveyVersionView | null>(null);
const busy = ref(false); const versionBusy = ref(false); const detailBusy = ref(false);
const error = ref(""); const versionError = ref(""); const detailError = ref("");
let generation = 0; let detailGeneration = 0; let mounted = true;
const answerLabels = Object.freeze({ TEXT: "文本", SINGLE_CHOICE: "单选", MULTIPLE_CHOICE: "多选",
  DATE: "日期", NUMBER: "数字", ATTACHMENT: "附件" });
const versionLabels = Object.freeze({ DRAFT: "草稿", IN_REVIEW: "评审中", APPROVED: "已批准", RETURNED: "已退回",
  SUPERSEDED: "已被替代", RESTRICTED: "受限" });

function ids() { return { projectId: typeof route.params.projectId === "string" ? route.params.projectId : "",
  surveyId: typeof route.params.surveyId === "string" ? route.params.surveyId : "" }; }
function mayRead() { return mounted && !!identity && !identity.password_change_required
  && session.view?.user.user_id === identity.user.user_id; }
function clearSelection() { detailGeneration += 1; selectedVersion.value = null; detailError.value = ""; detailBusy.value = false; }
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
  selectedVersion.value = null; detailError.value = ""; detailBusy.value = true;
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
  return source.source_kind === "TEMPLATE_DOCUMENT_VERSION" ? "可打开受权文档历史核对固定模板版本。"
    : source.source_kind === "MANUAL" ? "当前只有人工来源说明；未绑定受控文档或Evidence，不能一键定位原文。"
      : "当前固定来源已记录，但受控原文定位入口尚未接入；页面不会猜测内部标识。";
}
watch(() => [route.params.projectId, route.params.surveyId], () => {
  generation += 1; clearSelection(); busy.value = false; void load();
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; detailGeneration += 1; });
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
                <RouterLink v-if="source.source_kind === 'TEMPLATE_DOCUMENT_VERSION' && source.template_document_id"
                  :to="{ name: 'project-document-detail', params: { projectId: route.params.projectId,
                    documentId: source.template_document_id } }">打开受权文档历史并核对固定模板版本</RouterLink>
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
.fact-warning { padding: .8rem 1rem; border-left: .3rem solid #d29b42; background: #fff8e9; }.survey-detail [role="alert"] { color: #a21d25; }
</style>
