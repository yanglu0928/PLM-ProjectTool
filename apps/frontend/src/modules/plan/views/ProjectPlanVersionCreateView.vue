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
interface TaskDraft { key: string; name: string; code: string; category: string; entryText: string;
  acceptanceText: string; start: string; finish: string; risk: string; requirementIds: string[] }
const newTask = (index: number): TaskDraft => ({ key: crypto.randomUUID(), name: "", code: `TASK-${String(index).padStart(3, "0")}`,
  category: "IMPLEMENTATION", entryText: "", acceptanceText: "", start: "", finish: "", risk: "", requirementIds: [] });
const tasks = ref<TaskDraft[]>([newTask(1)]);
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
  tasks.value = [newTask(1)];
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
  const target = selectedId.value || candidates.value[0]?.outline.solution_outline_version_id;
  const found = candidates.value.filter(item => item.outline.solution_outline_version_id === target);
  if (found.length !== 1) throw new Error("请选择一个已批准且已核实的Solution固定版本。"); return found[0]!;
}
function visibleRequirements() {
  return candidates.value.find(item => item.outline.solution_outline_version_id === selectedId.value)?.requirements
    ?? candidates.value[0]?.requirements ?? [];
}
function draftFor(candidate: PlanApprovedSolution) {
  if (!tasks.value.length || tasks.value.length > 100) throw new Error("WBS任务数量需在1至100项之间。");
  const codes = tasks.value.map(task => task.code.trim());
  if (codes.some(code => !code || code.length > 64 || !/^[A-Z][A-Z0-9_-]*$/.test(code)) || new Set(codes).size !== codes.length)
    throw new Error("每项WBS编号必须唯一，并以大写字母开头，仅使用大写字母、数字、连字符或下划线。");
  const requirementKeys = candidate.requirements.map(item => `${item.requirement_id}|${item.requirement_version_id}`);
  const assigned = new Set(tasks.value.flatMap(task => task.requirementIds));
  if (requirementKeys.some(key => !assigned.has(key)) || [...assigned].some(key => !requirementKeys.includes(key)))
    throw new Error("请将每一项已批准需求至少分配到一个WBS任务；不可遗漏或引用其他需求。");
  const taskItems = tasks.value.map(task => {
    const startDate = task.start || null, finishDate = task.finish || null;
    if (!task.name.trim() || task.name.trim().length > 500) throw new Error("每项WBS任务都需要填写不超过500字的任务名称。");
    if ((startDate === null) !== (finishDate === null) || startDate && finishDate && finishDate < startDate)
      throw new Error("计划开始和结束日期需同时填写，且结束日期不得早于开始日期。");
    const requirementRefs = candidate.requirements.filter(item => task.requirementIds.includes(`${item.requirement_id}|${item.requirement_version_id}`))
      .map(item => ({ requirement_id: item.requirement_id, requirement_version_id: item.requirement_version_id }));
    return { wbs_item_id: crypto.randomUUID(), parent_item_id: null, wbs_code: task.code.trim(), name: task.name.trim(),
      level: 1, category: task.category, owner_ref: null, support_role_refs: [], planned_start: startDate,
      planned_finish: finishDate, duration_minutes: null, actual_start: null, actual_finish: null,
      item_state: "NOT_STARTED", entry_conditions: lines(task.entryText, false, "准入条件"),
      acceptance_criteria: lines(task.acceptanceText, true, "验收标准"), requirement_refs: requirementRefs,
      solution_refs: candidate.refs.map(ref => ({ ...ref })), prototype_refs: [], evidence_refs: [], output_refs: [],
      risk: task.risk.trim() || null, explicit_exclusion: null };
  });
  return Object.freeze({ approved_solution_refs: candidate.refs.map(ref => ({ ...ref })),
    wbs_items: taskItems, dependencies: [], milestones: [], calendar_ref: "CN_WORKDAY", exclusions: [] });
}
function showPreview() {
  if (!authorized() || pending.value || locked.value) return;
  try { draftFor(chosen()); error.value = ""; preview.value = true; }
  catch (failure) { error.value = failure instanceof Error ? failure.message : "计划版本内容无效。"; }
}
function sameRefs(a: readonly PlanSolutionFixedRef[], b: readonly PlanSolutionFixedRef[]) {
  const key = (item: PlanSolutionFixedRef) => [item.resource_kind, item.resource_id, item.version_id, item.spec_series_id, item.spec_type].join("|");
  const left = [...a].map(key).sort(), right = [...b].map(key).sort();
  return left.length === right.length && left.every((item, index) => item === right[index]);
}
function sameJson(a: unknown, b: unknown) { return JSON.stringify(a) === JSON.stringify(b); }
function sameRequirements(a: PlanApprovedSolution["requirements"], b: PlanApprovedSolution["requirements"]) {
  return sameJson(a.map(item => `${item.requirement_id}|${item.requirement_version_id}`).sort(),
    b.map(item => `${item.requirement_id}|${item.requirement_version_id}`).sort());
}
function readbackMatches(fixed: Awaited<ReturnType<PlanVersionReadClient["detail"]>>,
  created: string, draft: Readonly<Record<string, unknown>>) {
  const expectedItems = draft.wbs_items as readonly Record<string, unknown>[];
  if (fixed.plan_version_id !== created || fixed.version_state !== "DRAFT"
    || fixed.version_no < 1 || fixed.calendar_ref !== draft.calendar_ref || fixed.wbs_items.length !== expectedItems.length
    || fixed.dependencies.length || fixed.milestones.length || fixed.exclusions.length
    || !sameRefs(fixed.approved_solution_refs as readonly PlanSolutionFixedRef[], draft.approved_solution_refs as readonly PlanSolutionFixedRef[])) return false;
  const fields = ["wbs_item_id", "parent_item_id", "wbs_code", "name", "level", "category", "owner_ref",
    "support_role_refs", "planned_start", "planned_finish", "duration_minutes", "actual_start", "actual_finish",
    "item_state", "entry_conditions", "acceptance_criteria", "requirement_refs", "solution_refs",
    "prototype_refs", "evidence_refs", "output_refs", "risk", "explicit_exclusion"];
  return expectedItems.every((expected, index) => {
    const actual = fixed.wbs_items[index] as Record<string, unknown> | undefined;
    return !!actual && fields.every(field => sameJson(actual[field], expected[field]));
  });
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
      if (current.length !== 1 || !sameRefs(candidate.refs, current[0]!.refs)
        || !sameRequirements(candidate.requirements, current[0]!.requirements)) throw new Error("已批准方案或需求固定来源刚刚变化；请重新读取并确认新的固定来源。");
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
    <p v-if="error" role="alert">{{ error }}</p><p v-if="loading" role="status">正在核对已批准方案、需求、章节和专项的固定版本…</p>
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
        <fieldset :disabled="busy || loading || preview"><legend>2. 建立WBS任务并逐项映射已批准需求</legend>
          <p>每项固定需求必须至少分配给一项任务；可多选。系统不会自动判断归属，也不会替代正式排除或延期决定。</p>
          <article v-for="(task, index) in tasks" :key="task.key" class="task-card">
            <h3>任务 {{ index + 1 }}</h3>
            <label :for="`task-name-${index}`">任务名称</label><input :id="`task-name-${index}`" v-model="task.name" required maxlength="500" />
            <label :for="`task-code-${index}`">WBS编号</label><input :id="`task-code-${index}`" v-model="task.code" required maxlength="64" />
            <label :for="`task-category-${index}`">任务分类</label><select :id="`task-category-${index}`" v-model="task.category"><option v-for="item in ['ANALYSIS','DESIGN','IMPLEMENTATION','TEST','DEPLOYMENT','TRAINING','ACCEPTANCE','PROJECT_MANAGEMENT','OTHER']" :key="item" :value="item">{{ item }}</option></select>
            <fieldset class="requirement-map"><legend>关联需求（未覆盖将无法创建）</legend>
              <label v-for="req in visibleRequirements()" :key="`${req.requirement_id}|${req.requirement_version_id}`">
                <input v-model="task.requirementIds" type="checkbox" :value="`${req.requirement_id}|${req.requirement_version_id}`" />
                <span>{{ req.requirement_code }} · v{{ req.version_no }} · {{ req.title || req.statement }}</span>
                <RouterLink :to="{ name: 'project-requirement-detail', params: { projectId: projectId(), requirementId: req.requirement_id } }" target="_blank" rel="noopener">查看需求</RouterLink>
              </label><p v-if="!visibleRequirements().length">本方案没有固定需求引用；如不符合项目范围，请先完善并批准方案需求。</p>
            </fieldset>
            <label :for="`task-entry-${index}`">准入条件（每行一条，可选）</label><textarea :id="`task-entry-${index}`" v-model="task.entryText" rows="3" maxlength="200000" />
            <label :for="`task-acceptance-${index}`">验收标准（每行一条，必填）</label><textarea :id="`task-acceptance-${index}`" v-model="task.acceptanceText" aria-required="true" rows="4" maxlength="200000" />
            <label :for="`task-start-${index}`">计划开始日期（可选）</label><input :id="`task-start-${index}`" v-model="task.start" type="date" />
            <label :for="`task-finish-${index}`">计划完成日期（可选；须与开始日期配对）</label><input :id="`task-finish-${index}`" v-model="task.finish" type="date" />
            <label :for="`task-risk-${index}`">风险说明（可选）</label><textarea :id="`task-risk-${index}`" v-model="task.risk" rows="3" maxlength="2000" />
            <button v-if="tasks.length > 1" type="button" @click="tasks.splice(index, 1)">删除此任务</button>
          </article>
          <button type="button" :disabled="tasks.length >= 100" @click="tasks.push(newTask(tasks.length + 1))">增加WBS任务</button>
        </fieldset>
        <button type="button" :disabled="busy || loading || !selectedId" @click="showPreview">预览完整草稿</button>
        <div v-if="preview" class="preview" aria-label="草稿内容预览"><h2>创建前预览</h2>
          <p>Solution固定来源：{{ chosen().display.join("；") }}</p><p>固定需求：{{ chosen().requirements.length }}项 · 日历：CN_WORKDAY</p>
          <article v-for="(task, index) in tasks" :key="task.key"><h3>{{ task.code }} · {{ task.name }}</h3><p>分类：{{ task.category }}</p>
            <p>关联需求：{{ chosen().requirements.filter(req => task.requirementIds.includes(`${req.requirement_id}|${req.requirement_version_id}`)).map(req => req.requirement_code).join("、") || "无" }}</p>
            <h4>验收标准</h4><ul><li v-for="(item, i) in lines(task.acceptanceText, true, '验收标准')" :key="i">{{ item }}</li></ul>
          </article><p>将创建不可变DRAFT；无依赖、里程碑或人工排除声明。创建后需单独Validate与Review。</p>
          <button type="button" :disabled="busy" @click="preview = false">返回修改</button>
          <button type="button" :disabled="busy" @click="submit">{{ busy ? "正在核对并创建…" : "确认创建草稿版本" }}</button>
        </div>
      </template>
    </form>
  </template>
</section></template>
<style scoped>.plan-version-create{max-width:56rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}.plan-version-create form{display:grid;gap:.8rem}.plan-version-create fieldset{display:grid;gap:.6rem;border:1px solid #d8dee7;border-radius:.6rem;padding:1rem}.plan-version-create input:not([type=radio]):not([type=checkbox]),.plan-version-create select,.plan-version-create textarea{max-width:48rem;width:100%;padding:.55rem}.plan-version-create fieldset label{display:flex;gap:.5rem;align-items:flex-start}.plan-version-create .task-card{display:grid;gap:.5rem;border:1px solid #d8dee7;border-radius:.5rem;padding:1rem}.plan-version-create .requirement-map{margin:.5rem 0}.plan-version-create .warning{padding:.8rem 1rem;border-left:.3rem solid #d29b42;background:#fff8e9}.plan-version-create [role=alert]{color:#a21d25}.preview{padding:1rem;border:1px solid #8795a6;border-radius:.7rem;background:#f8fafc}</style>
