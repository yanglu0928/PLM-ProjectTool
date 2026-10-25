<script setup lang="ts">
import { computed, inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";

import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { SurveyReadClient, SurveyReadError, type SurveyCursor,
  type SurveyView } from "@/modules/survey/api/surveyReadClient";
import { SurveyCreateClient, SurveyCreateError, normalizeSurveyName } from "@/modules/survey/api/surveyCreateClient";

const props = defineProps<{ session?: SessionClient; surveys?: SurveyReadClient; creator?: SurveyCreateClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const surveys = toRaw(props.surveys ?? new SurveyReadClient());
const creator = toRaw(props.creator ?? new SurveyCreateClient(session));
const identity = session.view; const route = useRoute(); const router = useRouter();
const items = ref<readonly SurveyView[]>([]); const cursor = ref<SurveyCursor | null>(null);
const loaded = ref(false); const busy = ref(false); const error = ref("");
interface PendingCreate { readonly actor: string; readonly project: string; readonly name: string; readonly key: string }
const draftName = ref(""); const pending = ref<PendingCreate | null>(null); const confirmRetry = ref(false);
const createBusy = ref(false); const createError = ref(""); const locked = ref(false); const createdId = ref("");
let generation = 0; let mounted = true;
const stateLabels = Object.freeze({ ACTIVE: "进行中", ARCHIVED: "已归档", RESTRICTED: "受限" });
const projectId = () => typeof route.params.projectId === "string" ? route.params.projectId : "";
const canCreate = computed(() => mayRead() && session.canSubmit
  && identity!.authorized_projects.some(item => item.project_id === projectId()
    && (item.role === "PROJECT_MANAGER" || item.role === "IMPLEMENTATION_MEMBER")));
function storageKey() { return `plm.survey.create.pending.${identity?.user.user_id ?? "none"}.${projectId()}`; }
function restore() {
  draftName.value = ""; pending.value = null; confirmRetry.value = false;
  createBusy.value = false; createError.value = ""; locked.value = false; createdId.value = "";
  if (!canCreate.value) return;
  try {
    const raw = window.sessionStorage.getItem(storageKey());
    if (!raw) return;
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("invalid");
    const entry = value as Record<string, unknown>;
    if (Object.keys(entry).length !== 4 || entry.actor !== identity?.user.user_id
      || entry.project !== projectId() || typeof entry.name !== "string"
      || entry.name !== normalizeSurveyName(entry.name)
      || typeof entry.key !== "string" || !/^[\x20-\x7e]{16,128}$/.test(entry.key)) {
      throw new Error("invalid");
    }
    pending.value = entry as unknown as PendingCreate;
    draftName.value = entry.name;
  } catch {
    locked.value = true;
    createError.value = "原创建记录无法安全读取，已停止提交；请核对调研列表和审计记录。";
  }
}

function mayRead() {
  return mounted && !!identity && !identity.password_change_required
    && session.view?.user.user_id === identity.user.user_id;
}
async function load(next: SurveyCursor | null = null, replace = false) {
  if (!mayRead() || busy.value) return;
  const projectId = typeof route.params.projectId === "string" ? route.params.projectId : "";
  const current = ++generation; busy.value = true; error.value = "";
  if (replace) { items.value = []; cursor.value = null; loaded.value = false; }
  try {
    const page = await surveys.listSurveys(projectId, 50, next);
    if (!mounted || current !== generation || route.params.projectId !== projectId || !mayRead()) return;
    const known = new Set(items.value.map(item => item.survey_id));
    if (page.items.some(item => known.has(item.survey_id))) throw new SurveyReadError("SURVEY_READ_UNAVAILABLE");
    items.value = Object.freeze([...items.value, ...page.items]); cursor.value = page.next_cursor; loaded.value = true;
  } catch (failure) {
    if (!mounted || current !== generation || route.params.projectId !== projectId) return;
    items.value = []; cursor.value = null; loaded.value = false;
    error.value = failure instanceof SurveyReadError ? failure.message : "暂时无法读取项目调研定义，请稍后重试。";
  } finally { if (mounted && current === generation) busy.value = false; }
}
watch(() => route.params.projectId, () => {
  generation += 1; items.value = []; cursor.value = null; loaded.value = false; error.value = ""; busy.value = false;
  restore();
  void load(null, true);
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; });

async function createSurvey() {
  if (!canCreate.value || createBusy.value || locked.value || createdId.value
    || pending.value && !confirmRetry.value) return;
  const project = projectId(), actor = identity!.user.user_id;
  let attempt = pending.value;
  if (!attempt) {
    let name: string;
    try { name = normalizeSurveyName(draftName.value); }
    catch (failure) { createError.value = failure instanceof Error ? failure.message : "调研名称无效。"; return; }
    attempt = { actor, project, name, key: `survey-create-${crypto.randomUUID()}` };
    try { window.sessionStorage.setItem(storageKey(), JSON.stringify(attempt)); }
    catch { createError.value = "无法保存原操作号，本次未提交。"; return; }
    pending.value = attempt; draftName.value = name;
  }
  if (attempt.actor !== actor || attempt.project !== project) { locked.value = true; return; }
  const savedKey = storageKey(); confirmRetry.value = false; createBusy.value = true; createError.value = "";
  try {
    const result = await creator.create(project, attempt.name, attempt.key);
    if (!mounted || !canCreate.value || project !== projectId()
      || actor !== session.view?.user.user_id) return;
    createdId.value = result.survey_id;
    try { window.sessionStorage.removeItem(savedKey); pending.value = null; }
    catch { locked.value = true; createError.value = "调研定义已创建，但原操作号清理失败；请勿再次提交。"; return; }
    await load(null, true);
    try { await router.push({ name: "project-survey-detail", params: { projectId: project,
      surveyId: result.survey_id } }); }
    catch { createError.value = "调研定义已创建，但自动跳转失败；请使用下方详情链接。"; }
  } catch (failure) {
    if (!mounted || project !== projectId()) return;
    if (failure instanceof SurveyCreateError && failure.code === "CONFLICT_IDEMPOTENCY") locked.value = true;
    else if (failure instanceof SurveyCreateError && !failure.uncertain) {
      try { window.sessionStorage.removeItem(savedKey); pending.value = null; }
      catch { locked.value = true; }
    }
    createError.value = failure instanceof Error ? failure.message : "创建结果无法确认，请保留原操作号。";
  } finally { if (mounted) createBusy.value = false; }
}
</script>

<template>
  <section class="survey-list" aria-labelledby="survey-list-title" :aria-busy="busy">
    <p class="section-kicker">项目调研</p>
    <h1 id="survey-list-title">调研定义与固定版本</h1>
    <p class="fact-warning"><strong>问题模板和来源说明不等于客户事实。</strong> 应以实际面对面调研记录、固定来源和人工评审为准。</p>
    <p>列表不复制资料原文。进入定义后可查看问题卡片、需要维护的信息和当前可用的受控来源入口。</p>
    <p><RouterLink :to="{ name: 'project-detail', params: { projectId: route.params.projectId } }">返回项目详情</RouterLink>
      · <RouterLink :to="{ name: 'project-survey-rounds', params: { projectId: route.params.projectId } }">进入调研轮次工作台</RouterLink></p>
    <template v-if="!identity">
      <p role="status">尚未读取当前身份。请先登录，或在账户页读取当前身份。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else-if="identity.password_change_required">
      <p role="status">当前账户须先修改密码，暂不能读取项目调研定义。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else>
      <section v-if="canCreate" aria-labelledby="survey-create-title" class="create-panel">
        <h2 id="survey-create-title">新建调研定义</h2>
        <p>先为实际调研建立名称。此操作不会生成问题、代替面对面访谈，也不会自动确认客户事实；业务表单仅供参考。</p>
        <p v-if="createError" role="alert">{{ createError }}</p>
        <p v-if="createdId"><RouterLink :to="{ name: 'project-survey-detail', params: {
          projectId: route.params.projectId, surveyId: createdId } }">查看新建调研定义</RouterLink></p>
        <form v-else @submit.prevent="createSurvey">
          <label for="survey-create-name">调研名称</label>
          <input id="survey-create-name" v-model="draftName" required maxlength="255"
            :disabled="createBusy || !!pending || locked" placeholder="例如：PLM 项目面对面业务调研" />
          <p v-if="pending" role="status">原名称与操作号已保存在本浏览器会话。结果未知时先核对列表，勿换号重复创建。</p>
          <label v-if="pending && !locked"><input v-model="confirmRetry" type="checkbox" :disabled="createBusy" />
            我已核对调研列表和原名称，按原操作号重试</label>
          <button type="submit" :disabled="createBusy || locked || !!(pending && !confirmRetry)">
            {{ createBusy ? '正在提交…' : pending ? '按原操作号重试' : '创建调研定义' }}
          </button>
        </form>
      </section>
      <button type="button" :disabled="busy" @click="load(null, true)">{{ busy ? "正在读取…" : "刷新调研定义" }}</button>
      <p v-if="busy" role="status">正在确认项目调研定义访问权限…</p>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="loaded && !items.length" role="status">当前项目没有可见的调研定义。</p>
      <ol v-if="items.length" aria-label="项目调研定义">
        <li v-for="item in items" :key="item.survey_id">
          <div class="survey-heading"><strong>{{ item.name }}</strong><span>{{ stateLabels[item.state] }}</span></div>
          <span>更新时间：<time :datetime="item.updated_at">{{ new Date(item.updated_at).toLocaleString("zh-CN") }}</time></span>
          <span>当前批准版本：{{ item.current_approved_version_ref ? "已形成" : "尚未形成" }}</span>
          <RouterLink :to="{ name: 'project-survey-detail', params: {
            projectId: item.project_id, surveyId: item.survey_id } }">查看版本、问题与来源说明</RouterLink>
        </li>
      </ol>
      <button v-if="cursor && loaded" type="button" :disabled="busy" @click="load(cursor)">加载更多调研定义</button>
    </template>
  </section>
</template>

<style scoped>
.survey-list { max-width: 54rem; margin: 1rem auto; padding: 1.5rem; background: #fff; border-radius: 1rem; }
.survey-list p { line-height: 1.65; }.survey-list ol { display: grid; gap: .8rem; padding: 0; list-style: none; }
.survey-list li { display: grid; gap: .4rem; padding: 1rem; border: 1px solid #d8dee7; border-radius: .75rem; overflow-wrap: anywhere; }
.survey-heading { display: flex; justify-content: space-between; gap: 1rem; }
.create-panel { margin: 1rem 0; padding: 1rem; border: 1px solid #d8dee7; border-radius: .75rem; }
.create-panel input[type="text"], .create-panel input:not([type]) { display: block; width: min(100%, 32rem); margin: .4rem 0 .8rem; }
.fact-warning { padding: .8rem 1rem; border-left: .3rem solid #d29b42; background: #fff8e9; }
.survey-list [role="alert"] { color: #a21d25; }
</style>
