<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { RequirementReadClient } from "@/modules/requirement/api/requirementReadClient";
import { loadProjectOutlineVersionCandidates, type OutlineVersionProjectCandidates } from
  "@/modules/solution/api/outlineVersionCandidates";
import { OutlineReadClient, type OutlineCurrent } from "@/modules/solution/api/outlineReadClient";
import { OutlineVersionCreateClient, OutlineVersionCreateError, type OutlineVersionDraft } from
  "@/modules/solution/api/outlineVersionCreateClient";
import { loadProjectGlobalReferenceCandidates, ProjectGlobalReferenceCandidateClient,
  type ProjectGlobalReferenceCandidate } from
  "@/modules/solution/api/projectGlobalReferenceCandidateClient";
import { ReferenceReadClient } from "@/modules/solution/api/referenceReadClient";
import { SectionReadClient } from "@/modules/solution/api/sectionReadClient";

type CandidateLoader = typeof loadProjectOutlineVersionCandidates;
type GlobalCandidateLoader = (projectId: string) => Promise<readonly ProjectGlobalReferenceCandidate[]>;
const props = defineProps<{ session?: SessionClient; outlineReader?: OutlineReadClient;
  creator?: OutlineVersionCreateClient; candidateLoader?: CandidateLoader;
  globalCandidateLoader?: GlobalCandidateLoader }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const outlineReader = toRaw(props.outlineReader ?? new OutlineReadClient());
const creator = toRaw(props.creator ?? new OutlineVersionCreateClient(session));
const candidateLoader = props.candidateLoader ?? ((project: string, outline: string) =>
  loadProjectOutlineVersionCandidates(project, outline, new SectionReadClient(),
    new RequirementReadClient(), new ReferenceReadClient()));
const globalCandidateLoader = props.globalCandidateLoader ?? ((project: string) =>
  loadProjectGlobalReferenceCandidates(project, new ProjectGlobalReferenceCandidateClient()));
const route = useRoute();
const projectId = () => typeof route.params.projectId === "string" ? route.params.projectId : "";
const outlineId = () => typeof route.params.outlineId === "string" ? route.params.outlineId : "";
const parent = ref<OutlineCurrent | null>(null);
const candidates = ref<OutlineVersionProjectCandidates | null>(null);
const globalCandidates = ref<readonly ProjectGlobalReferenceCandidate[] | null>(null);
const selectedSections = ref<string[]>([]); const selectedRequirements = ref<string[]>([]);
const selectedReferences = ref<string[]>([]);
const selectedGlobalReferences = ref<string[]>([]);
const missingText = ref(""); const conflictText = ref("");
const loading = ref(false); const busy = ref(false); const error = ref("");
const pending = ref<{ project: string; outline: string; actor: string; draft: OutlineVersionDraft;
  key: string } | null>(null);
const locked = ref(false); const confirmRetry = ref(false); const confirmCreate = ref(false);
const createdId = ref("");
let mounted = true; let generation = 0;
function authorized() {
  return mounted && !!session.view && !session.view.password_change_required && session.canSubmit
    && session.view.authorized_projects.some(item => item.project_id === projectId()
      && (item.role === "PROJECT_MANAGER" || item.role === "IMPLEMENTATION_MEMBER"));
}
function storageKey() {
  return `plm.sol.outline.version.create.pending.${session.view?.user.user_id ?? "none"}.${projectId()}.${outlineId()}`;
}
function restore() {
  pending.value = null; locked.value = false; confirmRetry.value = false; confirmCreate.value = false;
  createdId.value = ""; error.value = "";
  if (!authorized()) return;
  try {
    const raw = window.sessionStorage.getItem(storageKey());
    if (!raw) return;
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("invalid");
    const item = value as Record<string, unknown>;
    if (item.project !== projectId() || item.outline !== outlineId()
      || item.actor !== session.view?.user.user_id
      || typeof item.key !== "string" || !/^[\x20-\x7e]{16,128}$/.test(item.key)
      || !item.draft || typeof item.draft !== "object" || Array.isArray(item.draft)
      || new TextEncoder().encode(JSON.stringify(item.draft)).length > 512 * 1024) throw new Error("invalid");
    pending.value = item as unknown as typeof pending.value;
  } catch {
    locked.value = true;
    error.value = "原版本操作记录无法读取，已停止提交；请核对方案版本和审计记录。";
  }
}
async function load() {
  if (!authorized() || loading.value) return;
  const project = projectId(), outline = outlineId(), run = ++generation;
  if (!pending.value) {
    selectedSections.value = []; selectedRequirements.value = []; selectedReferences.value = [];
    selectedGlobalReferences.value = []; confirmCreate.value = false;
  }
  loading.value = true; parent.value = null; candidates.value = null; globalCandidates.value = null;
  if (!locked.value) error.value = "";
  try {
    const [current, available, globalAvailable] = await Promise.all([
      outlineReader.current(project, outline), candidateLoader(project, outline,
        new SectionReadClient(), new RequirementReadClient(), new ReferenceReadClient()),
      globalCandidateLoader(project),
    ]);
    if (!mounted || run !== generation || project !== projectId() || outline !== outlineId()) return;
    if (current.project_id !== project || current.solution_outline_id !== outline) throw new Error("方案目录身份不匹配。");
    if (globalAvailable.length > 500
      || new Set(globalAvailable.map(item => item.reference_solution_id)).size !== globalAvailable.length) {
      throw new Error("GLOBAL 候选无法完整核对，已停止创建。请刷新后重试。");
    }
    parent.value = current; candidates.value = available; globalCandidates.value = globalAvailable;
  } catch (failure) {
    if (mounted && run === generation && !locked.value) error.value = failure instanceof Error
      ? failure.message : "暂时无法核对方案来源。";
  } finally { if (mounted && run === generation) loading.value = false; }
}
watch(() => [route.params.projectId, route.params.outlineId], () => {
  if (route.name !== "project-outline-version-create") return;
  generation += 1; loading.value = false; parent.value = null; candidates.value = null;
  globalCandidates.value = null;
  selectedSections.value = []; selectedRequirements.value = []; selectedReferences.value = [];
  selectedGlobalReferences.value = [];
  missingText.value = ""; conflictText.value = "";
  restore(); void load();
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; });
function canCreate() {
  if (pending.value) return authorized();
  return authorized() && parent.value?.outline_state === "ACTIVE"
    && parent.value.project_id === projectId() && parent.value.solution_outline_id === outlineId()
    && !!candidates.value && globalCandidates.value !== null;
}
function statements(raw: string, label: string): readonly Record<string, unknown>[] {
  const lines = raw.split(/\r?\n/).map(value => value.trim()).filter(Boolean);
  if (lines.length > 100 || lines.some(value => value.length > 2000 || /\p{C}/u.test(value))) {
    throw new Error(`${label}最多 100 条，每条最多 2000 字且不能包含控制字符。`);
  }
  return lines.map(description => ({ description }));
}
function draftFromSelection(): OutlineVersionDraft {
  const available = candidates.value, availableGlobal = globalCandidates.value;
  if (!available || selectedSections.value.length < 1 || selectedSections.value.length > 100
    || new Set(selectedSections.value).size !== selectedSections.value.length
    || new Set(selectedRequirements.value).size !== selectedRequirements.value.length
    || new Set(selectedReferences.value).size !== selectedReferences.value.length
    || availableGlobal === null
    || new Set(selectedGlobalReferences.value).size !== selectedGlobalReferences.value.length
    || selectedReferences.value.length + selectedGlobalReferences.value.length > 500) {
    throw new Error("至少选择一个当前方案章节，且不得重复选择来源。");
  }
  const sections = selectedSections.value.map(identity => {
    const item = available.sections.find(value => value.solution_section_id === identity);
    if (!item) throw new Error("章节候选已变化，请刷新后重新核对。");
    return item.solution_section_id;
  });
  const requirements = selectedRequirements.value.map(identity => {
    const item = available.requirements.find(value => value.requirement_id === identity);
    if (!item?.current_approved_version_ref) throw new Error("需求候选已变化，请刷新后重新核对。");
    return { requirement_id: item.requirement_id, requirement_version_id: item.current_approved_version_ref };
  });
  const references = selectedReferences.value.map(identity => {
    const item = available.references.find(value => value.reference_solution_id === identity);
    if (!item) throw new Error("参考候选已变化，请刷新后重新核对。");
    return { scope: "PROJECT" as const, reference_solution_id: item.reference_solution_id,
      reference_version_id: item.reference_version_id };
  });
  const globalReferences = selectedGlobalReferences.value.map(identity => {
    const item = availableGlobal.find(value => value.reference_solution_id === identity);
    if (!item) throw new Error("GLOBAL 候选已变化，请刷新后重新核对。");
    return { scope: "GLOBAL" as const, reference_solution_id: item.reference_solution_id,
      reference_version_id: item.reference_version_id };
  });
  const missing = statements(missingText.value, "缺失声明");
  const conflicts = statements(conflictText.value, "冲突声明");
  if (!requirements.length && !references.length && !globalReferences.length && !missing.length) {
    throw new Error("未选择需求或参考方案时，必须填写至少一条缺失声明。");
  }
  return { section_ids: sections, requirement_refs: requirements,
    reference_refs: [...references, ...globalReferences],
    missing_declarations: missing, conflict_declarations: conflicts };
}
async function submit() {
  if (!canCreate() || busy.value || locked.value || createdId.value
    || (pending.value ? !confirmRetry.value : !confirmCreate.value)) return;
  const project = projectId(), outline = outlineId(), actor = session.view!.user.user_id;
  let attempt = pending.value;
  if (!attempt) {
    let draft: OutlineVersionDraft;
    try { draft = draftFromSelection(); }
    catch (failure) { error.value = failure instanceof Error ? failure.message : "来源无效。"; return; }
    attempt = { project, outline, actor, draft, key: crypto.randomUUID() };
    try { window.sessionStorage.setItem(storageKey(), JSON.stringify(attempt)); }
    catch { error.value = "无法保存原操作号，本次未提交。"; return; }
    pending.value = attempt;
  }
  if (attempt.project !== project || attempt.outline !== outline || attempt.actor !== actor) {
    locked.value = true; return;
  }
  confirmRetry.value = false; busy.value = true; error.value = "";
  try {
    const result = await creator.create(project, outline, attempt.draft, attempt.key);
    if (!mounted || project !== projectId() || outline !== outlineId()
      || actor !== session.view?.user.user_id) return;
    createdId.value = result.solution_outline_version_id;
    try { window.sessionStorage.removeItem(storageKey()); pending.value = null; }
    catch { locked.value = true; error.value = "版本已创建，但原操作号清理失败；请停止再次提交。"; }
  } catch (failure) {
    if (!mounted) return;
    if (failure instanceof OutlineVersionCreateError && failure.code === "CONFLICT_IDEMPOTENCY") locked.value = true;
    error.value = failure instanceof Error ? failure.message : "创建结果无法确认，请保留原操作号。";
  } finally { if (mounted) busy.value = false; }
}
</script>

<template>
  <section class="outline-version-create" aria-labelledby="outline-version-create-title" :aria-busy="loading || busy">
    <p class="section-kicker">项目方案</p><h1 id="outline-version-create-title">创建方案草案版本</h1>
    <p class="warning">仅建立待评审 DRAFT，不代表已批准或已交付。所有候选在提交时仍由服务器重验当前资格。</p>
    <p><RouterLink :to="{ name: 'project-outline-detail', params: { projectId: route.params.projectId,
      outlineId: route.params.outlineId } }">返回方案目录</RouterLink></p>
    <p v-if="!authorized()" role="status">仅当前项目负责人或实施成员可创建；请确认会话与项目权限。</p>
    <template v-else>
      <button type="button" :disabled="loading || busy || !!pending || locked" @click="load()">
        {{ loading ? "正在核对…" : "刷新当前候选" }}</button>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="createdId" role="status">草案版本已创建：<code>{{ createdId }}</code>。
        <RouterLink :to="{ name: 'project-outline-version-detail', params: { projectId: route.params.projectId,
          outlineId: route.params.outlineId, versionId: createdId } }">查看固定版本详情</RouterLink></p>
      <p v-else-if="loading" role="status">正在读取方案目录与固定来源候选…</p>
      <p v-else-if="parent?.outline_state === 'ARCHIVED' && !pending" role="status">方案目录已归档，不可创建草案。</p>
      <form v-else-if="canCreate()" @submit.prevent="submit">
        <template v-if="pending">
          <p class="warning" role="status">存在原创建操作。结果不确定时，不得更改来源或换操作号；请先核对记录，再按原内容与原号重试。</p>
          <p>原记录：章节 {{ pending.draft.section_ids.length }}、需求 {{ pending.draft.requirement_refs.length }}、参考 {{ pending.draft.reference_refs.length }}。重试保持首次固定来源与原操作号。</p>
          <label v-if="!locked"><input v-model="confirmRetry" type="checkbox" :disabled="busy" /> 我已核对原操作，确认按原内容和原操作号重试</label>
        </template>
        <template v-else>
          <fieldset :disabled="busy"><legend>1. 选择本目录的活动章节（至少一项）</legend>
            <p v-if="!candidates?.sections.length">当前没有活动章节；请先创建章节并刷新。</p>
            <label v-for="item in candidates?.sections" :key="item.solution_section_id">
              <input v-model="selectedSections" type="checkbox" :value="item.solution_section_id" /> {{ item.section_key }}
              <RouterLink :to="{ name: 'project-section-detail', params: { projectId: item.project_id,
                sectionId: item.solution_section_id } }">查看章节</RouterLink>
            </label>
          </fieldset>
          <fieldset :disabled="busy"><legend>2. 选择当前已批准需求版本（可选）</legend>
            <label v-for="item in candidates?.requirements" :key="item.requirement_id">
              <input v-model="selectedRequirements" type="checkbox" :value="item.requirement_id" /> {{ item.requirement_code }}
              <RouterLink :to="{ name: 'project-requirement-detail', params: { projectId: item.project_id,
                requirementId: item.requirement_id } }">查看需求</RouterLink>
            </label>
          </fieldset>
          <fieldset :disabled="busy"><legend>3. 选择当前标为合格的本项目参考版本（可选）</legend>
            <label v-for="item in candidates?.references" :key="item.reference_solution_id">
              <input v-model="selectedReferences" type="checkbox" :value="item.reference_solution_id" /> {{ item.name }} · v{{ item.version_no }}
              <RouterLink :to="{ name: 'project-reference-detail', params: { projectId: item.project_id,
                referenceId: item.reference_solution_id } }">查看参考与来源</RouterLink>
            </label>
          </fieldset>
          <fieldset :disabled="busy"><legend>4. 选择已人工审定且当前合格的 GLOBAL 参考版本（可选）</legend>
            <p class="warning">仅展示审定标签，不展示原始名称或客户来源。选择当前候选不替代提交时服务器再次核对资格与来源。</p>
            <p v-if="!globalCandidates?.length">当前没有可用的已发布 GLOBAL 候选。</p>
            <label v-for="item in globalCandidates" :key="item.reference_solution_id">
              <input v-model="selectedGlobalReferences" type="checkbox" :value="item.reference_solution_id" />
              {{ item.display_label }} · v{{ item.version_no }} · <code>{{ item.reference_solution_id }}</code>
            </label>
          </fieldset>
          <label for="outline-missing">5. 缺失声明（每行一条；如果需求和参考均为空则必填）</label>
          <textarea id="outline-missing" v-model="missingText" rows="3" maxlength="64000" :disabled="busy"
            placeholder="例如：客户尚未确认接口字段清单，需在评审前补齐。" />
          <label for="outline-conflict">6. 冲突声明（每行一条，可选）</label>
          <textarea id="outline-conflict" v-model="conflictText" rows="3" maxlength="64000" :disabled="busy"
            placeholder="例如：调研记录与技术协议对交付范围表述不一致，待确认。" />
          <label><input v-model="confirmCreate" type="checkbox" :disabled="busy" /> 我已逐项核对上述候选及缺失/冲突说明，确认仅创建待评审草案</label>
        </template>
        <button type="submit" :disabled="busy || locked || (pending ? !confirmRetry : !confirmCreate)">
          {{ busy ? "正在提交…" : pending ? "按原操作号重试" : "创建 DRAFT 草案" }}
        </button>
      </form>
    </template>
  </section>
</template>

<style scoped>
.outline-version-create{max-width:64rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}
.outline-version-create form{display:grid;gap:.9rem}.outline-version-create fieldset{display:grid;gap:.5rem;border:1px solid #aaa;border-radius:.5rem}
.outline-version-create textarea{width:100%;box-sizing:border-box}.outline-version-create [role=alert]{color:#a21d25}
.warning{padding:.8rem 1rem;border-left:.3rem solid #d29b42;background:#fff8e9}
</style>
