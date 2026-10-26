<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { PlanVersionReadClient } from "@/modules/plan/api/planVersionReadClient";
import { PlanVersionWriteClient, PlanVersionWriteError } from "@/modules/plan/api/planVersionWriteClient";
import { loadPlanApprovedSolutions, type PlanApprovedSolution, type PlanSolutionFixedRef } from "@/modules/plan/api/planVersionApprovedSolutions";

const props = defineProps<{ session?: SessionClient; reader?: PlanVersionReadClient;
  creator?: PlanVersionWriteClient; candidateLoader?: typeof loadPlanApprovedSolutions }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const reader = toRaw(props.reader ?? new PlanVersionReadClient());
const creator = toRaw(props.creator ?? new PlanVersionWriteClient(session));
const candidateLoader = props.candidateLoader ?? loadPlanApprovedSolutions;
const route = useRoute(); const router = useRouter();
const candidates = ref<readonly PlanApprovedSolution[]>([]); const selectedId = ref("");
const name = ref(""); const code = ref("TASK-001"); const category = ref("IMPLEMENTATION");
const entryText = ref(""); const acceptanceText = ref(""); const start = ref(""); const finish = ref(""); const risk = ref("");
const loading = ref(false); const busy = ref(false); const error = ref(""); const preview = ref(false);
const createdId = ref(""); const locked = ref(false); const confirmRetry = ref(false);
const pending = ref<{ project: string; plan: string; actor: string; draft: Readonly<Record<string, unknown>>; key: string } | null>(null);
let mounted = true; let generation = 0;
const projectId = () => typeof route.params.projectId === "string" ? route.params.projectId : "";
const planId = () => typeof route.params.planId === "string" ? route.params.planId : "";
function authorized() { return mounted && !!session.view && !session.view.password_change_required && session.canSubmit
  && session.view.authorized_projects.some(p => p.project_id === projectId()
    && (p.role === "PROJECT_MANAGER" || p.role === "IMPLEMENTATION_MEMBER")); }
function storageKey() { return `plm.plan.version.create.pending.${session.view?.user.user_id ?? "none"}.${projectId()}.${planId()}`; }
function restore() {
  pending.value = null; locked.value = false; confirmRetry.value = false; preview.value = false;
  error.value = ""; createdId.value = ""; selectedId.value = "";
  if (!authorized()) return;
  try {
    const raw = window.sessionStorage.getItem(storageKey()); if (!raw) return;
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("invalid");
    const item = value as Record<string, unknown>;
    if (Object.keys(item).length !== 5 || !["project", "plan", "actor", "draft", "key"].every(k => Object.hasOwn(item, k))
      || item.project !== projectId() || item.plan !== planId() || item.actor !== session.view?.user.user_id
      || typeof item.key !== "string" || !/^[\x20-\x7e]{16,128}$/.test(item.key)
      || !item.draft || typeof item.draft !== "object" || Array.isArray(item.draft)
      || new TextEncoder().encode(JSON.stringify(item.draft)).length > 8 * 1024 * 1024) throw new Error("invalid");
    pending.value = item as unknown as typeof pending.value;
  } catch { locked.value = true; error.value = "原操作记录无法安全读取，已停止创建；请先核对计划版本和操作记录。"; }
}
async function loadCandidates() {
  if (!authorized() || loading.value || pending.value || locked.value) return;
  const project = projectId(), run = ++generation; loading.value = true; error.value = ""; candidates.value = [];
  try { const values = await candidateLoader(project);
    if (!mounted || run !== generation || project !== projectId()) return;
    candidates.value = values;
    if (!values.some(item => item.outline.solution_outline_version_id === selectedId.value)) selectedId.value = "";
  } catch (failure) { if (mounted && run === generation) error.value = failure instanceof Error ? failure.message : "暂时无法读取已批准方案固定来源。"; }
  finally { if (mounted && run === generation) loading.value = false; }
}
watch(() => [route.params.projectId, route.params.planId], () => {
  generation++; candidates.value = []; selectedId.value = ""; loading.value = false; busy.value = false;
  name.value = ""; code.value = "TASK-001"; category.value = "IMPLEMENTATION";
  entryText.value = ""; acceptanceText.value = ""; start.value = ""; finish.value = ""; risk.value = "";
  restore(); void loadCandidates();
}, { immediate: true });
onUnmounted(() => { mounted = false; generation++; });
function lines(value: string, required: boolean, label: string): string[] {
  const rows = value.split(/\r?\n/).map(x => x.trim()).filter(Boolean);
  if (rows.length > 100 || required && !rows.length || rows.some(x => x.length > 2000 || /\p{C}/u.test(x))) {
    throw new Error(`${label}${required ? "至少填写一条；" : ""}最多100条，每条不超过2000字。`);
  }
  return rows;
}
function chosen(): PlanApprovedSolution {
  const found = candidates.value.filter(item => item.outline.solution_outline_version_id === selectedId.value);
  if (found.length !== 1) throw new Error("请选择一个已批准且已核实的Solution固定版本。"); return found[0]!;
}
function draftFor(candidate: PlanApprovedSolution) {
  const taskId = crypto.randomUUID(); const taskRefs = candidate.refs.map(ref => ({ ...ref }));
  const startDate = start.value || null, finishDate = finish.value || null;
  if ((startDate === null) !== (finishDate === null) || startDate && finishDate && finishDate < startDate)
    throw new Error("计划开始和结束日期需同时填写，且结束日期不得早于开始日期。");
  return Object.freeze({ approved_solution_refs: candidate.refs.map(ref => ({ ...ref })),
    wbs_items: [{ wbs_item_id: taskId, parent_item_id: null, wbs_code: code.value.trim(), name: name.value.trim(),
      level: 1, category: category.value, owner_ref: null, support_role_refs: [], planned_start: startDate,
      planned_finish: finishDate, duration_minutes: null, actual_start: null, actual_finish: null,
      item_state: "NOT_STARTED", entry_conditions: lines(entryText.value, false, "准入条件"),
      acceptance_criteria: lines(acceptanceText.value, true, "验收标准"), requirement_refs: [],
      solution_refs: taskRefs, prototype_refs: [], evidence_refs: [], output_refs: [], risk: risk.value.trim() || null,
      explicit_exclusion: null }], dependencies: [], milestones: [], calendar_ref: "CN_WORKDAY", exclusions: [] });
}
function showPreview() {
  if (!authorized() || pending.value || locked.value) return;
  if (!name.value.trim() || name.value.trim().length > 500 || !code.value.trim() || code.value.trim().length > 64
    || !/^[A-Z][A-Z0-9_]*$/.test(category.value)) { error.value = "请输入计划任务名称、任务编号和有效分类。"; return; }
  try { draftFor(chosen()); error.value = ""; preview.value = true; }
  catch (failure) { error.value = failure instanceof Error ? failure.message : "计划版本内容无效。"; }
}
function sameRefs(a: readonly PlanSolutionFixedRef[], b: readonly PlanSolutionFixedRef[]) {
  const key = (item: PlanSolutionFixedRef) => [item.resource_kind, item.resource_id, item.version_id, item.spec_series_id, item.spec_type].join("|");
  const left = [...a].map(key).sort(), right = [...b].map(key).sort();
  return left.length === right.length && left.every((item, index) => item === right[index]);
}
function sameJson(a: unknown, b: unknown) { return JSON.stringify(a) === JSON.stringify(b); }
function readbackMatches(fixed: Awaited<ReturnType<PlanVersionReadClient["detail"]>>,
  created: string, draft: Readonly<Record<string, unknown>>) {
  const expected = (draft.wbs_items as readonly Record<string, unknown>[])[0];
  const actual = fixed.wbs_items[0] as Record<string, unknown> | undefined;
  if (!expected || !actual || fixed.plan_version_id !== created || fixed.version_state !== "DRAFT"
    || fixed.version_no < 1 || fixed.calendar_ref !== draft.calendar_ref || fixed.wbs_items.length !== 1
    || fixed.dependencies.length || fixed.milestones.length || fixed.exclusions.length
    || !sameRefs(fixed.approved_solution_refs as readonly PlanSolutionFixedRef[], draft.approved_solution_refs as readonly PlanSolutionFixedRef[])) return false;
  return ["wbs_item_id", "parent_item_id", "wbs_code", "name", "level", "category", "owner_ref",
    "support_role_refs", "planned_start", "planned_finish", "duration_minutes", "actual_start", "actual_finish",
    "item_state", "entry_conditions", "acceptance_criteria", "requirement_refs", "solution_refs",
    "prototype_refs", "evidence_refs", "output_refs", "risk", "explicit_exclusion"]
    .every(field => sameJson(actual[field], expected[field]));
}
async function submit() {
  if (!authorized() || busy.value || locked.value || createdId.value || (pending.value && !confirmRetry.value)) return;
  const project = projectId(), plan = planId(), actor = session.view!.user.user_id, run = generation;
  let attempt = pending.value;
  if (!attempt) {
    let candidate: PlanApprovedSolution; let draft: Readonly<Record<string, unknown>>;
    try { candidate = chosen(); draft = draftFor(candidate); }
    catch (failure) { error.value = failure instanceof Error ? failure.message : "计划版本内容无效。"; return; }
    busy.value = true; error.value = "";
    try {
      const refreshed = await candidateLoader(project);
      const current = refreshed.filter(item => item.outline.solution_outline_version_id === candidate.outline.solution_outline_version_id);
      if (current.length !== 1 || !sameRefs(candidate.refs, current[0]!.refs)) throw new Error("已批准方案来源刚刚变化；请重新读取并确认新的固定来源。");
      draft = draftFor(current[0]!);
    } catch (failure) { if (mounted && run === generation) error.value = failure instanceof Error ? failure.message : "来源复核失败。"; busy.value = false; return; }
    if (!mounted || run !== generation || project !== projectId() || plan !== planId()) { busy.value = false; return; }
    attempt = { project, plan, actor, draft, key: crypto.randomUUID() };
    try { window.sessionStorage.setItem(storageKey(), JSON.stringify(attempt)); }
    catch { busy.value = false; error.value = "无法安全保存原操作号，本次未提交。"; return; }
    pending.value = attempt; preview.value = false;
  }
  if (attempt.project !== project || attempt.plan !== plan || attempt.actor !== actor) { locked.value = true; busy.value = false; return; }
  confirmRetry.value = false; busy.value = true; error.value = "";
  try {
    const created = await creator.create(project, plan, attempt.draft, attempt.key);
    if (!mounted || run !== generation || project !== projectId() || plan !== planId() || actor !== session.view?.user.user_id) return;
    createdId.value = created.plan_version_id;
    try { window.sessionStorage.removeItem(storageKey()); pending.value = null; }
    catch { locked.value = true; error.value = "草稿已创建，但本地操作记录未清理；请勿重复提交。"; return; }
    try {
      const fixed = await reader.detail(project, plan, created.plan_version_id);
      if (!readbackMatches(fixed, created.plan_version_id, attempt.draft)) {
        locked.value = true; error.value = "草稿已创建，但固定版本读回未与提交内容匹配；已停止重试，请查看该版本。"; return;
      }
      await router.push({ name: "project-plan-version-detail", params: { projectId: project, planId: plan, versionId: created.plan_version_id } });
    } catch (failure) { error.value = failure instanceof Error ? `草稿已创建；固定版本读回暂不可用，请稍后查看该版本。${failure.message}` : "草稿已创建；固定版本读回暂不可用。"; }
  } catch (failure) {
    if (!mounted || run !== generation || project !== projectId() || plan !== planId()) return;
    if (failure instanceof PlanVersionWriteError && failure.code === "CONFLICT_IDEMPOTENCY") locked.value = true;
    error.value = failure instanceof Error ? failure.message : "创建结果无法确认；请保留原操作号和内容。";
  } finally { if (mounted && run === generation) busy.value = false; }
}
</script>
<template><section class="plan-version-create" aria-labelledby="plan-version-create-title" :aria-busy="loading || busy">
  <p class="section-kicker">项目实施</p><h1 id="plan-version-create-title">创建计划草稿版本</h1>
  <p class="warning">本操作只创建不可变 DRAFT。新版本须单独执行Validate和Review；创建不代表已批准、客户确认或交付。</p>
  <p><RouterLink :to="{ name: 'project-plan-detail', params: { projectId: route.params.projectId, planId: route.params.planId } }">返回计划详情</RouterLink></p>
  <p v-if="!authorized()" role="status">仅当前项目负责人或实施成员可创建；请确认会话与项目权限。</p><template v-else>
    <p v-if="error" role="alert">{{ error }}</p><p v-if="loading" role="status">正在核对已批准方案及其章节/专项固定版本…</p>
    <button v-if="!pending && !locked" type="button" :disabled="loading || busy" @click="loadCandidates">{{ loading ? "正在核对…" : "刷新已批准方案" }}</button>
    <p v-if="!loading && !candidates.length && !pending" role="status">没有可完整核对的当前已批准方案；请先完成方案批准并刷新。</p>
    <p v-if="createdId" role="status">草稿版本已创建：<RouterLink :to="{ name: 'project-plan-version-detail', params: { projectId: projectId(), planId: planId(), versionId: createdId } }">查看固定版本</RouterLink></p>
    <form v-else @submit.prevent="pending ? submit() : showPreview()">
      <template v-if="pending"><p class="warning">存在原创建操作。结果不确定时不可更改内容或更换操作号。</p>
        <label><input v-model="confirmRetry" type="checkbox" :disabled="busy || locked" /> 我已核对原操作，确认按原内容和原操作号重试</label>
        <button type="submit" :disabled="busy || locked || !confirmRetry">{{ busy ? "正在提交…" : "按原操作号重试" }}</button>
      </template><template v-else>
        <fieldset :disabled="busy || loading || preview"><legend>1. 选择一个当前已批准方案固定版本</legend>
          <label v-for="item in candidates" :key="item.outline.solution_outline_version_id"><input v-model="selectedId" type="radio" name="approved-solution" :value="item.outline.solution_outline_version_id" />
            <span>{{ item.display[0] }} · 固定版本 {{ item.outline.solution_outline_version_id }}</span>
            <details><summary>查看固定章节与专项来源</summary><ul><li v-for="source in item.display.slice(1)" :key="source">{{ source }}</li></ul></details>
          </label>
        </fieldset>
        <fieldset :disabled="busy || loading || preview"><legend>2. 填写计划WBS根任务</legend>
          <label for="plan-version-task-name">任务名称</label><input id="plan-version-task-name" v-model="name" required maxlength="500" />
          <label for="plan-version-task-code">WBS编号</label><input id="plan-version-task-code" v-model="code" required maxlength="64" />
          <label for="plan-version-task-category">任务分类</label><select id="plan-version-task-category" v-model="category"><option v-for="item in ['ANALYSIS','DESIGN','IMPLEMENTATION','TEST','DEPLOYMENT','TRAINING','ACCEPTANCE','PROJECT_MANAGEMENT','OTHER']" :key="item" :value="item">{{ item }}</option></select>
          <label for="plan-version-entry">准入条件（每行一条，可选）</label><textarea id="plan-version-entry" v-model="entryText" rows="3" maxlength="200000" />
          <label for="plan-version-acceptance">验收标准（每行一条，必填）</label><textarea id="plan-version-acceptance" v-model="acceptanceText" aria-required="true" rows="4" maxlength="200000" />
          <label for="plan-version-start">计划开始日期（可选）</label><input id="plan-version-start" v-model="start" type="date" />
          <label for="plan-version-finish">计划完成日期（可选；须与开始日期配对）</label><input id="plan-version-finish" v-model="finish" type="date" />
          <label for="plan-version-risk">风险说明（可选）</label><textarea id="plan-version-risk" v-model="risk" rows="3" maxlength="2000" />
        </fieldset>
        <button type="button" :disabled="busy || loading || !selectedId" @click="showPreview">预览完整草稿</button>
        <div v-if="preview" class="preview" aria-label="草稿内容预览"><h2>创建前预览</h2>
          <p>Solution固定来源：{{ chosen().display.join("；") }}</p><p>WBS根任务：{{ code }} · {{ name }}</p><p>分类：{{ category }} · 日历：CN_WORKDAY</p>
          <h3>准入条件</h3><ul><li v-for="(item, i) in lines(entryText, false, '准入条件')" :key="i">{{ item }}</li></ul>
          <h3>验收标准</h3><ul><li v-for="(item, i) in lines(acceptanceText, true, '验收标准')" :key="i">{{ item }}</li></ul>
          <p>将创建不可变 DRAFT；无依赖、里程碑或排除项。创建后需单独Validate与Review。</p>
          <button type="button" :disabled="busy" @click="preview = false">返回修改</button>
          <button type="button" :disabled="busy" @click="submit">{{ busy ? "正在核对并创建…" : "确认创建草稿版本" }}</button>
        </div>
      </template>
    </form>
  </template>
</section></template>
<style scoped>.plan-version-create{max-width:56rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}.plan-version-create form{display:grid;gap:.8rem}.plan-version-create fieldset{display:grid;gap:.6rem;border:1px solid #d8dee7;border-radius:.6rem;padding:1rem}.plan-version-create input:not([type=radio]):not([type=checkbox]),.plan-version-create select,.plan-version-create textarea{max-width:48rem;width:100%;padding:.55rem}.plan-version-create fieldset label{display:flex;gap:.5rem;align-items:flex-start}.plan-version-create .warning{padding:.8rem 1rem;border-left:.3rem solid #d29b42;background:#fff8e9}.plan-version-create [role=alert]{color:#a21d25}.preview{padding:1rem;border:1px solid #8795a6;border-radius:.7rem;background:#f8fafc}</style>
