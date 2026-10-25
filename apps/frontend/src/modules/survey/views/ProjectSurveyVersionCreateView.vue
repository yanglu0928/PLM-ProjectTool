<script setup lang="ts">
import { computed, inject, onUnmounted, ref, shallowRef, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { ProjectDepartmentReadClient, type ProjectDepartmentView } from "@/modules/project/api/projectDepartmentReadClient";
import { SurveyReadClient, type SurveyView } from "@/modules/survey/api/surveyReadClient";
import { SurveyHandoverSourceClient, type SurveyHandoverSourceCandidate,
  type SurveyHandoverSourceCursor } from "@/modules/survey/api/surveyHandoverSourceClient";
import { SurveyVersionCreateClient, SurveyVersionCreateError, handoverItemSource,
  manualSurveySource, validateSurveyVersionCreateInput,
  type SurveyVersionCreateInput, type SurveyVersionQuestionDraft } from "@/modules/survey/api/surveyVersionCreateClient";

const props = defineProps<{ session?: SessionClient; surveys?: SurveyReadClient;
  handoverSources?: SurveyHandoverSourceClient; departments?: ProjectDepartmentReadClient;
  creator?: SurveyVersionCreateClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const surveys = toRaw(props.surveys ?? new SurveyReadClient());
const handoverSources = toRaw(props.handoverSources ?? new SurveyHandoverSourceClient(session));
const departments = toRaw(props.departments ?? new ProjectDepartmentReadClient());
const creator = toRaw(props.creator ?? new SurveyVersionCreateClient(session));
const identity = shallowRef(session.view); const route = useRoute();
const unsubscribeSession = session.subscribe(() => { identity.value = session.view; });
interface Card { id: string; topic: string; question: string; objective: string;
  expected: string; answerType: SurveyVersionQuestionDraft["answer_type"];
  required: boolean; evidenceRequired: boolean; optionLabels: string;
  sourceRows: string[]; manualNote: string; }
interface Pending { actor: string; project: string; survey: string; etag: string;
  key: string; input: SurveyVersionCreateInput; }
function newCard(): Card { return { id: crypto.randomUUID(), topic: "", question: "",
  objective: "", expected: "", answerType: "TEXT", required: true,
  evidenceRequired: false, optionLabels: "", sourceRows: [], manualNote: "" }; }
const cards = ref<Card[]>([newCard()]);
const selectedDepartments = ref<string[]>([]);
const survey = ref<SurveyView | null>(null);
const sources = ref<readonly SurveyHandoverSourceCandidate[]>([]);
const sourceCursor = ref<SurveyHandoverSourceCursor | null>(null);
const departmentsList = ref<readonly ProjectDepartmentView[]>([]);
const departmentCursor = ref<string | null>(null);
const busy = ref(false); const moreBusy = ref(false); const writing = ref(false);
const error = ref(""); const writeError = ref(""); const success = ref("");
const pending = ref<Pending | null>(null); const retryConfirmed = ref(false);
const locked = ref(false); let mounted = true; let generation = 0;
const ids = () => ({ project: typeof route.params.projectId === "string" ? route.params.projectId : "",
  survey: typeof route.params.surveyId === "string" ? route.params.surveyId : "" });
const canEdit = computed(() => mounted && !!identity.value && !identity.value.password_change_required
  && session.canSubmit && session.view?.user.user_id === identity.value.user.user_id
  && identity.value.authorized_projects.some(item => item.project_id === ids().project
    && (item.role === "PROJECT_MANAGER" || item.role === "IMPLEMENTATION_MEMBER")));
function storageKey() { const value = ids();
  return `plm.survey.version.create.pending.${identity.value?.user.user_id ?? "none"}.${value.project}.${value.survey}`; }
function restore() {
  pending.value = null; retryConfirmed.value = false; locked.value = false; writeError.value = "";
  if (!canEdit.value) return;
  try {
    const raw = sessionStorage.getItem(storageKey()); if (!raw) return;
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error();
    const record = value as Record<string, unknown>; const current = ids();
    if (Object.keys(record).length !== 6 || record.actor !== identity.value?.user.user_id
      || record.project !== current.project || record.survey !== current.survey
      || typeof record.etag !== "string" || !/^"v(0|[1-9][0-9]*)"$/.test(record.etag)
      || typeof record.key !== "string" || !/^[\x20-\x7e]{16,128}$/.test(record.key)
      || !record.input || typeof record.input !== "object" || Array.isArray(record.input)) throw new Error();
    validateSurveyVersionCreateInput(record.input);
    pending.value = record as unknown as Pending;
  } catch { locked.value = true; writeError.value = "原操作记录损坏，已停止提交；请核对版本列表和审计。"; }
}
async function load() {
  if (!canEdit.value || busy.value) return;
  const current = ++generation, request = ids(); busy.value = true; error.value = "";
  survey.value = null; sources.value = []; sourceCursor.value = null;
  departmentsList.value = []; departmentCursor.value = null;
  try {
    const [root, sourcePage, departmentPage] = await Promise.all([
      surveys.getSurvey(request.project, request.survey),
      handoverSources.list(request.project), departments.list(request.project),
    ]);
    if (!mounted || current !== generation || ids().project !== request.project
      || ids().survey !== request.survey || !canEdit.value) return;
    if (root.state !== "ACTIVE") throw new Error("调研定义已非 ACTIVE，不能创建版本。");
    survey.value = root; sources.value = sourcePage.items; sourceCursor.value = sourcePage.next_cursor;
    departmentsList.value = departmentPage.items; departmentCursor.value = departmentPage.next_cursor;
  } catch (failure) { if (mounted && current === generation) error.value = failure instanceof Error
    ? failure.message : "暂时无法读取调研版本来源和目标部门。";
  } finally { if (mounted && current === generation) busy.value = false; }
}
async function moreSources() {
  if (!canEdit.value || !sourceCursor.value || moreBusy.value || pending.value) return;
  const current = generation, request = ids(), next = sourceCursor.value; moreBusy.value = true; error.value = "";
  try { const page = await handoverSources.list(request.project, 50, next);
    if (!mounted || current !== generation || ids().project !== request.project) return;
    const known = new Set(sources.value.map(item => item.handover_item_row_id));
    if (page.items.some(item => known.has(item.handover_item_row_id))) throw new Error("交接来源页重复，已停止选择。");
    sources.value = Object.freeze([...sources.value, ...page.items]); sourceCursor.value = page.next_cursor;
  } catch (failure) { if (mounted) error.value = failure instanceof Error ? failure.message : "加载更多交接来源失败。";
  } finally { if (mounted) moreBusy.value = false; }
}
async function moreDepartments() {
  if (!canEdit.value || !departmentCursor.value || moreBusy.value || pending.value) return;
  const current = generation, request = ids(), next = departmentCursor.value; moreBusy.value = true; error.value = "";
  try { const page = await departments.list(request.project, next);
    if (!mounted || current !== generation || ids().project !== request.project) return;
    const known = new Set(departmentsList.value.map(item => item.department_id));
    if (page.items.some(item => known.has(item.department_id))) throw new Error("目标部门页重复，已停止选择。");
    departmentsList.value = Object.freeze([...departmentsList.value, ...page.items]); departmentCursor.value = page.next_cursor;
  } catch (failure) { if (mounted) error.value = failure instanceof Error ? failure.message : "加载更多目标部门失败。";
  } finally { if (mounted) moreBusy.value = false; }
}
function buildInput(): SurveyVersionCreateInput {
  const targets = selectedDepartments.value.filter(id => departmentsList.value.some(item =>
    item.department_id === id && item.state === "ACTIVE"));
  if (targets.length < 1 || targets.length !== selectedDepartments.value.length
    || cards.value.length < 1 || cards.value.length > 500) throw new Error("请先选择当前启用的目标部门和问题卡片。");
  const questions = cards.value.map(card => {
    const chosen = sources.value.filter(item => card.sourceRows.includes(item.handover_item_row_id));
    if (chosen.length !== card.sourceRows.length || chosen.length > 20) throw new Error("交接来源已变化，请重新读取并选择。");
    const note = card.manualNote.trim();
    if (!chosen.length && !note) throw new Error("每张问题卡片至少需要交接固定来源或明确的实际访谈记录说明。");
    if (note && (note !== card.manualNote || note.length > 2000)) throw new Error("访谈来源说明须为1～2000字且无首尾空格。");
    const options = card.answerType === "SINGLE_CHOICE" || card.answerType === "MULTIPLE_CHOICE"
      ? card.optionLabels.split("\n").map(label => label.trim()).filter(Boolean) : [];
    if ((card.answerType === "SINGLE_CHOICE" || card.answerType === "MULTIPLE_CHOICE")
      && (options.length < 2 || options.length > 20)) throw new Error("选择题需填写2～20个选项，每行一个。");
    const sourcesForQuestion = [...chosen.map(handoverItemSource),
      ...(note ? [manualSurveySource(note)] : [])];
    if (sourcesForQuestion.length > 20) throw new Error("每题最多20条来源。");
    return { question_id: card.id, topic: card.topic.trim(), question_text: card.question.trim(),
      objective: card.objective.trim(), answer_type: card.answerType, validation_rule: {},
      required: card.required, condition_rule: null, expected_output: card.expected.trim(),
      evidence_required: card.evidenceRequired, options: options.map((label, index) => ({
        option_code: String.fromCharCode(65 + index), label, description: null })),
      sources: sourcesForQuestion } satisfies SurveyVersionQuestionDraft;
  });
  return { questions, target_department_ids: targets };
}
async function submit() {
  if (!canEdit.value || !survey.value || writing.value || busy.value || locked.value || success.value
    || pending.value && !retryConfirmed.value) return;
  const request = ids(), actor = identity.value!.user.user_id;
  let attempt = pending.value;
  if (!attempt) {
    let input: SurveyVersionCreateInput;
    try { input = buildInput(); } catch (failure) { writeError.value = failure instanceof Error ? failure.message : "问题卡片无效。"; return; }
    attempt = { actor, project: request.project, survey: request.survey,
      etag: survey.value.etag, key: `survey-version-${crypto.randomUUID()}`, input };
    try { sessionStorage.setItem(storageKey(), JSON.stringify(attempt)); pending.value = attempt;
    } catch { writeError.value = "无法保存原操作号，本次未提交。"; return; }
  }
  if (attempt.actor !== actor || attempt.project !== request.project || attempt.survey !== request.survey) {
    locked.value = true; writeError.value = "原操作与当前项目或账户不一致，已停止写入。"; return;
  }
  retryConfirmed.value = false; writing.value = true; writeError.value = "";
  try {
    const result = await creator.create(request.project, request.survey,
      attempt.etag, attempt.input, attempt.key);
    if (!mounted || ids().project !== request.project || ids().survey !== request.survey
      || !canEdit.value) return;
    success.value = `已创建 DRAFT 版本 ${result.version_no}；不是客户确认事实。`;
    try { sessionStorage.removeItem(storageKey()); pending.value = null;
    } catch { locked.value = true; writeError.value = "版本已创建，但原操作记录清理失败；请勿再次提交。"; return; }
  } catch (failure) {
    if (!mounted || ids().project !== request.project || ids().survey !== request.survey) return;
    if (failure instanceof SurveyVersionCreateError && failure.code === "CONFLICT_IDEMPOTENCY") locked.value = true;
    else if (failure instanceof SurveyVersionCreateError && !failure.uncertain) {
      try { sessionStorage.removeItem(storageKey()); pending.value = null; }
      catch { locked.value = true; }
    }
    writeError.value = failure instanceof Error ? failure.message : "版本创建结果不明，请保留原操作号。";
  } finally { if (mounted) writing.value = false; }
}
watch(() => [route.params.projectId, route.params.surveyId, identity.value?.user.user_id, canEdit.value], () => {
  generation += 1; survey.value = null; sources.value = []; departmentsList.value = [];
  selectedDepartments.value = []; cards.value = [newCard()]; success.value = "";
  error.value = ""; busy.value = false; restore(); void load();
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; unsubscribeSession(); });
</script>

<template>
  <section class="survey-version-create" aria-labelledby="survey-version-create-title" :aria-busy="busy || writing">
    <p class="section-kicker">项目调研</p><h1 id="survey-version-create-title">建立调研问题版本</h1>
    <p><strong>实际面对面调研记录优先，业务表单仅作参考。</strong>交接来源只帮助定位；问题、访谈说明和客户答复均需人工核对，创建 DRAFT 不代表客户已确认。</p>
    <p><RouterLink :to="{ name: 'project-survey-detail', params: { projectId: route.params.projectId,
      surveyId: route.params.surveyId } }">返回调研定义与版本</RouterLink></p>
    <p v-if="!identity" role="status">尚未读取当前身份，请先登录。</p>
    <p v-else-if="!canEdit" role="status">当前账户无权创建此项目的调研版本。</p>
    <template v-else>
      <button type="button" :disabled="busy || writing || !!pending" @click="load">{{ busy ? "正在读取…" : "刷新当前来源与部门" }}</button>
      <p v-if="error" role="alert">{{ error }}</p>
      <template v-if="survey">
        <p>调研定义：{{ survey.name }} · 当前标记 {{ survey.etag }}</p>
        <fieldset :disabled="!!pending || writing"><legend>目标部门（至少一个）</legend>
          <label v-for="department in departmentsList.filter(item => item.state === 'ACTIVE')" :key="department.department_id">
            <input v-model="selectedDepartments" type="checkbox" :value="department.department_id" />
            {{ department.name }}（{{ department.code }}）
          </label>
          <p v-if="!departmentsList.some(item => item.state === 'ACTIVE')">暂无可选启用部门，请先核对项目部门。</p>
          <button v-if="departmentCursor" type="button" :disabled="moreBusy" @click="moreDepartments">加载更多部门</button>
        </fieldset>
        <section aria-labelledby="survey-source-title"><h2 id="survey-source-title">当前已批准交接问题来源</h2>
          <p>仅展示当前合格候选；选择后如来源变更，提交仍会被服务器拒绝。</p>
          <p v-if="!sources.length">暂无当前合格交接问题。可用 MANUAL 明确记录实际访谈来源，不得称为已批准交接引用。</p>
          <ul><li v-for="source in sources" :key="source.handover_item_row_id">
            {{ source.title }} · {{ source.state }} ·
            <RouterLink :to="{ name: 'project-handover-detail', params: { projectId: ids().project,
              analysisId: source.handover_analysis_id }, query: { fixedVersionId: source.handover_analysis_version_id } }">
              查看交接固定版本中的原问题
            </RouterLink>
          </li></ul>
          <button v-if="sourceCursor" type="button" :disabled="moreBusy || !!pending" @click="moreSources">加载更多交接问题</button>
        </section>
        <section aria-labelledby="survey-question-title"><h2 id="survey-question-title">人工问题卡片</h2>
          <article v-for="(card, index) in cards" :key="card.id" class="question-card">
            <header><h3>问题 {{ index + 1 }}</h3><button type="button" :disabled="!!pending || cards.length === 1"
              @click="cards.splice(index, 1)">移除问题</button></header>
            <label>主题<input v-model="card.topic" required maxlength="255" :disabled="!!pending" placeholder="例如：当前物料审批流程" /></label>
            <label>要向客户确认的问题<textarea v-model="card.question" required maxlength="4000" :disabled="!!pending"
              placeholder="写明确切的现场问题，不复制整篇资料" /></label>
            <label>调研目的<textarea v-model="card.objective" required maxlength="2000" :disabled="!!pending"
              placeholder="说明为什么需要询问及待澄清的边界" /></label>
            <label>预期维护的信息<textarea v-model="card.expected" required maxlength="2000" :disabled="!!pending"
              placeholder="例如：参与岗位、实际步骤、例外处理、待补证据" /></label>
            <label>回答形式<select v-model="card.answerType" :disabled="!!pending"><option value="TEXT">文本</option>
              <option value="SINGLE_CHOICE">单选</option><option value="MULTIPLE_CHOICE">多选</option>
              <option value="DATE">日期</option><option value="NUMBER">数字</option><option value="ATTACHMENT">附件</option></select></label>
            <label v-if="card.answerType === 'SINGLE_CHOICE' || card.answerType === 'MULTIPLE_CHOICE'">可选答案（每行一个，2～20项）
              <textarea v-model="card.optionLabels" :disabled="!!pending" placeholder="方案 A&#10;方案 B" /></label>
            <label><input v-model="card.required" type="checkbox" :disabled="!!pending" /> 回答必填</label>
            <label><input v-model="card.evidenceRequired" type="checkbox" :disabled="!!pending" /> 回答时需提供证据</label>
            <fieldset :disabled="!!pending"><legend>固定交接来源（可多选）</legend>
              <label v-for="source in sources" :key="source.handover_item_row_id">
                <input v-model="card.sourceRows" type="checkbox" :value="source.handover_item_row_id" />{{ source.title }}
              </label>
              <p v-if="!sources.length">没有当前固定来源；请在下方维护实际访谈来源说明。</p>
            </fieldset>
            <label>实际访谈或人工来源说明（无固定来源时必填）
              <textarea v-model="card.manualNote" maxlength="2000" :disabled="!!pending"
                placeholder="写明访谈日期、参与角色、记录位置与尚待客户核对的内容；不能冒充已批准交接" /></label>
          </article>
          <button type="button" :disabled="!!pending || cards.length >= 500" @click="cards.push(newCard())">增加问题卡片</button>
        </section>
        <p v-if="pending" role="status">原提交已保存。结果不明时请先核对版本列表；再次提交仅使用原问题快照、原标记和原操作号。</p>
        <label v-if="pending && !locked"><input v-model="retryConfirmed" type="checkbox" :disabled="writing" />我已核对版本列表，按原操作号重试</label>
        <p v-if="writeError" role="alert">{{ writeError }}</p><p v-if="success" role="status">{{ success }}</p>
        <button type="button" :disabled="busy || writing || locked || !!success || !!pending && !retryConfirmed"
          @click="submit">{{ writing ? "正在提交…" : pending ? "按原操作号重试" : "保存 DRAFT 调研问题版本" }}</button>
      </template>
    </template>
  </section>
</template>

<style scoped>
.survey-version-create { display: grid; gap: .9rem; max-width: 76rem; }
.survey-version-create fieldset, .question-card { border: 1px solid #b6c7d4; border-radius: .6rem; padding: 1rem; display: grid; gap: .6rem; }
.survey-version-create label { display: grid; gap: .25rem; }
.survey-version-create input:not([type="checkbox"]), .survey-version-create textarea,
.survey-version-create select { width: 100%; box-sizing: border-box; }
.survey-version-create textarea { min-height: 4.5rem; }
.survey-version-create button { justify-self: start; }
</style>
