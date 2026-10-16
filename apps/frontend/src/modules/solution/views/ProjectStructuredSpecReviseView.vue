<script setup lang="ts">
import { inject, onUnmounted, reactive, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { RequirementReadClient } from "@/modules/requirement/api/requirementReadClient";
import { EvidenceListClient } from "@/modules/evidence/api/evidenceListClient";
import { SectionReadClient } from "@/modules/solution/api/sectionReadClient";
import { SectionVersionReadClient } from "@/modules/solution/api/sectionVersionReadClient";
import { loadStructuredSpecCandidates, type StructuredSpecCandidates } from
  "@/modules/solution/api/structuredSpecCandidates";
import { isStructuredSpecDraft, type StructuredSpecDraft } from
  "@/modules/solution/api/structuredSpecCreateClient";
import { StructuredSpecReadClient, type StructuredSpecDetail } from
  "@/modules/solution/api/structuredSpecReadClient";
import { StructuredSpecReviseClient, StructuredSpecReviseError } from
  "@/modules/solution/api/structuredSpecReviseClient";
import { buildStructuredSpecPayload, emptyStructuredSpecForm,
  structuredSpecFormFromPayload } from "./structuredSpecForm";

type CandidateLoader = typeof loadStructuredSpecCandidates;
const props = defineProps<{ session?: SessionClient; reader?: StructuredSpecReadClient;
  reviser?: StructuredSpecReviseClient; candidateLoader?: CandidateLoader }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const reader = toRaw(props.reader ?? new StructuredSpecReadClient());
const reviser = toRaw(props.reviser ?? new StructuredSpecReviseClient(session));
const candidateLoader = props.candidateLoader ?? loadStructuredSpecCandidates;
const route = useRoute();
const projectId = () => typeof route.params.projectId === "string" ? route.params.projectId : "";
const specId = () => typeof route.params.specId === "string" ? route.params.specId : "";
const current = ref<StructuredSpecDetail | null>(null);
const candidates = ref<StructuredSpecCandidates | null>(null);
const selectedRequirements = ref<string[]>([]); const selectedSections = ref<string[]>([]);
const selectedEvidence = ref<string[]>([]); const unavailableSources = ref(0);
const form = reactive(emptyStructuredSpecForm());
const loading = ref(false); const busy = ref(false); const error = ref("");
const confirmRevise = ref(false); const confirmRetry = ref(false); const locked = ref(false);
const revisedId = ref(""); const revisedVersion = ref(0);
const pending = ref<{ project: string; predecessor: string; actor: string;
  draft: StructuredSpecDraft; key: string } | null>(null);
let mounted = true; let generation = 0;
function authorized() {
  return mounted && !!session.view && !session.view.password_change_required && session.canSubmit
    && session.view.authorized_projects.some(item => item.project_id === projectId()
      && (item.role === "PROJECT_MANAGER" || item.role === "IMPLEMENTATION_MEMBER"));
}
function storageKey() {
  return `plm.sol.spec.revise.pending.${session.view?.user.user_id ?? "none"}.${projectId()}.${specId()}`;
}
function allowedState(item: StructuredSpecDetail | null) {
  return !!item && ["DRAFT", "RETURNED", "APPROVED"].includes(item.version_state);
}
function restore() {
  pending.value = null; locked.value = false; confirmRetry.value = false;
  confirmRevise.value = false; revisedId.value = ""; revisedVersion.value = 0; error.value = "";
  if (!authorized()) return;
  try {
    const raw = window.sessionStorage.getItem(storageKey());
    if (!raw) return;
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("invalid");
    const item = value as Record<string, unknown>;
    if (item.project !== projectId() || item.predecessor !== specId()
      || item.actor !== session.view?.user.user_id || typeof item.key !== "string"
      || !/^[\x20-\x7e]{16,128}$/.test(item.key) || !isStructuredSpecDraft(item.draft)
      || new TextEncoder().encode(JSON.stringify(item.draft)).length > 512 * 1024) {
      throw new Error("invalid");
    }
    pending.value = item as unknown as typeof pending.value;
  } catch {
    locked.value = true;
    error.value = "原修订操作记录无法读取，已停止提交；请核对专项历史与审计记录。";
  }
}
function selectOriginalSources(item: StructuredSpecDetail, available: StructuredSpecCandidates) {
  selectedRequirements.value = []; selectedSections.value = []; selectedEvidence.value = [];
  let missing = 0;
  for (const original of item.requirement_refs) {
    const candidate = available.requirements.find(value => value.requirement_id === original.requirement_id
      && value.current_approved_version_ref === original.requirement_version_id);
    if (candidate) selectedRequirements.value.push(candidate.requirement_id); else missing += 1;
  }
  for (const original of item.section_refs) {
    const candidate = available.sections.find(value =>
      value.section.solution_section_id === original.solution_section_id
      && value.version.solution_section_version_id === original.solution_section_version_id);
    if (candidate) selectedSections.value.push(candidate.section.solution_section_id); else missing += 1;
  }
  for (const original of item.evidence_ids) {
    const candidate = available.evidence.find(value => value.evidence_id === original);
    if (candidate) selectedEvidence.value.push(candidate.evidence_id); else missing += 1;
  }
  unavailableSources.value = missing;
}
async function load() {
  if (!authorized() || loading.value) return;
  const project = projectId(), predecessor = specId(), run = ++generation;
  loading.value = true; current.value = null; candidates.value = null;
  if (!locked.value) error.value = "";
  try {
    const [fixed, available] = await Promise.all([reader.detail(project, predecessor),
      candidateLoader(project, new RequirementReadClient(), new SectionReadClient(),
        new SectionVersionReadClient(), new EvidenceListClient())]);
    if (!mounted || run !== generation || project !== projectId() || predecessor !== specId()) return;
    current.value = fixed; candidates.value = available;
    if (!pending.value) {
      if (!allowedState(fixed)) {
        error.value = `当前版本状态 ${fixed.version_state} 不允许修订；请从专项历史选择最新可修订版本。`;
        return;
      }
      Object.assign(form, structuredSpecFormFromPayload(fixed.spec_type, fixed.payload));
      selectOriginalSources(fixed, available);
    }
  } catch (failure) {
    if (mounted && run === generation && !locked.value) error.value = failure instanceof Error
      ? failure.message : "暂时无法核对固定版本与当前来源。";
  } finally { if (mounted && run === generation) loading.value = false; }
}
watch(() => [route.name, route.params.projectId, route.params.specId], () => {
  if (route.name !== "project-structured-spec-revise") return;
  generation += 1; loading.value = false; current.value = null; candidates.value = null;
  selectedRequirements.value = []; selectedSections.value = []; selectedEvidence.value = [];
  unavailableSources.value = 0; Object.assign(form, emptyStructuredSpecForm());
  restore(); void load();
}, { immediate: true });
watch(() => JSON.stringify([form, selectedRequirements.value, selectedSections.value,
  selectedEvidence.value]), () => { confirmRevise.value = false; });
onUnmounted(() => { mounted = false; generation += 1; });
function canRevise() {
  if (pending.value) return authorized();
  return authorized() && !!candidates.value && allowedState(current.value) && !loading.value;
}
function draftFromSelection(): StructuredSpecDraft {
  const available = candidates.value, fixed = current.value;
  if (!available || !fixed || !selectedRequirements.value.length || !selectedSections.value.length
    || selectedRequirements.value.length > 500 || selectedSections.value.length > 500
    || selectedEvidence.value.length > 500
    || new Set(selectedRequirements.value).size !== selectedRequirements.value.length
    || new Set(selectedSections.value).size !== selectedSections.value.length
    || new Set(selectedEvidence.value).size !== selectedEvidence.value.length) {
    throw new Error("请选择至少一条当前已批准需求和一个当前章节版本；来源不得重复。");
  }
  const requirement_refs = selectedRequirements.value.map(identity => {
    const item = available.requirements.find(value => value.requirement_id === identity);
    if (!item?.current_approved_version_ref) throw new Error("需求候选已变化，请刷新后核对。");
    return { requirement_id: item.requirement_id,
      requirement_version_id: item.current_approved_version_ref };
  });
  const section_refs = selectedSections.value.map(identity => {
    const item = available.sections.find(value => value.section.solution_section_id === identity);
    if (!item) throw new Error("章节候选已变化，请刷新后核对。");
    return { solution_section_id: item.section.solution_section_id,
      solution_section_version_id: item.version.solution_section_version_id };
  });
  const evidence_ids = selectedEvidence.value.map(identity => {
    const item = available.evidence.find(value => value.evidence_id === identity);
    if (!item) throw new Error("证据候选已变化，请刷新后核对。");
    return item.evidence_id;
  });
  return { spec_type: fixed.spec_type,
    payload: buildStructuredSpecPayload(fixed.spec_type, form), requirement_refs, section_refs,
    evidence_ids, artifact_ids: [] };
}
function clearStoredOperation() {
  try { window.sessionStorage.removeItem(storageKey()); pending.value = null; }
  catch { locked.value = true; error.value = "服务已确认未创建新版本，但原操作号清理失败；请停止再次提交。"; }
}
async function submit() {
  if (!canRevise() || busy.value || locked.value || revisedId.value
    || (pending.value ? !confirmRetry.value : !confirmRevise.value)) return;
  const project = projectId(), predecessor = specId(), actor = session.view!.user.user_id;
  let attempt = pending.value;
  if (!attempt) {
    let draft: StructuredSpecDraft;
    try { draft = draftFromSelection(); }
    catch (failure) { error.value = failure instanceof Error ? failure.message : "来源或专项内容无效。"; return; }
    attempt = { project, predecessor, actor, draft, key: crypto.randomUUID() };
    try { window.sessionStorage.setItem(storageKey(), JSON.stringify(attempt)); }
    catch { error.value = "无法保存原操作号，本次未提交。"; return; }
    pending.value = attempt;
  }
  if (attempt.project !== project || attempt.predecessor !== predecessor || attempt.actor !== actor) {
    locked.value = true; return;
  }
  confirmRetry.value = false; busy.value = true; error.value = "";
  try {
    const result = await reviser.revise(project, predecessor, attempt.draft, attempt.key);
    if (!mounted || project !== projectId() || predecessor !== specId()
      || actor !== session.view?.user.user_id) return;
    revisedId.value = result.structured_solution_spec_id; revisedVersion.value = result.version_no;
    try { window.sessionStorage.removeItem(storageKey()); pending.value = null; }
    catch { locked.value = true; error.value = "修订草案已创建，但原操作号清理失败；请停止再次提交。"; }
  } catch (failure) {
    if (!mounted) return;
    if (failure instanceof StructuredSpecReviseError && !failure.uncertain) {
      if (["CONFLICT_VERSION", "CONFLICT_STATE", "CONFLICT_IDEMPOTENCY", "RESOURCE_NOT_FOUND"]
        .includes(failure.code)) locked.value = true;
      clearStoredOperation();
    }
    error.value = failure instanceof Error ? failure.message : "修订结果无法确认，请保留原操作号。";
  } finally { if (mounted) busy.value = false; }
}
</script>

<template>
  <section class="spec-revise" aria-labelledby="spec-revise-title" :aria-busy="loading || busy">
    <p class="section-kicker">项目方案 · 新建修订版本</p><h1 id="spec-revise-title">修订结构化专项</h1>
    <p class="warning">修订不会覆盖原历史，只会基于所选版本创建新的 DRAFT。服务器会重新核对最新版本及所有固定来源；新版本不代表已批准。</p>
    <p><RouterLink :to="{ name: 'project-structured-spec-detail', params: { projectId: route.params.projectId, specId: route.params.specId } }">返回原固定版本</RouterLink>
      · <RouterLink :to="{ name: 'project-structured-specs', params: { projectId: route.params.projectId } }">查看专项版本历史</RouterLink></p>
    <p v-if="!authorized()" role="status">仅当前项目负责人或实施成员可修订；请确认会话与项目权限。</p>
    <template v-else>
      <button type="button" :disabled="loading || busy || !!pending || locked" @click="load()">{{ loading ? "正在核对…" : "刷新原版本与当前来源" }}</button>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="revisedId" role="status">已创建版本 {{ revisedVersion }} 的修订草案。当前仅为 DRAFT；<RouterLink :to="{ name: 'project-structured-spec-detail', params: { projectId: route.params.projectId, specId: revisedId } }">查看新版本</RouterLink>。</p>
      <p v-else-if="loading" role="status">正在读取原固定版本并核对当前可用来源…</p>
      <form v-else-if="canRevise()" @submit.prevent="submit">
        <template v-if="pending">
          <p class="warning" role="status">存在原修订操作。结果不确定时请先核对专项历史与审计，不得改正文、来源或操作号。</p>
          <p>原内容：{{ pending.draft.spec_type }}；需求 {{ pending.draft.requirement_refs.length }} 项，章节 {{ pending.draft.section_refs.length }} 项。重试保持原正文和原操作号。</p>
          <label><input v-model="confirmRetry" type="checkbox" :disabled="busy || locked" /> 我已核对原操作，确认按原内容与原操作号重试</label>
        </template>
        <template v-else-if="current">
          <p>原固定版本：版本 {{ current.version_no }}（{{ current.version_state }}）；专项类型：{{ current.spec_type }}</p>
          <p v-if="unavailableSources" class="warning" role="status">原版本有 {{ unavailableSources }} 个来源已不是当前可选来源，系统没有自动替换。请在下方显式选择当前有效来源后再提交。</p>
          <fieldset :disabled="busy"><legend>1. 当前已批准需求版本（至少选择一项）</legend>
            <p v-if="!candidates?.requirements.length">暂无当前已批准需求；请先完成需求评审。</p>
            <label v-for="item in candidates?.requirements" :key="item.requirement_id"><input v-model="selectedRequirements" type="checkbox" :value="item.requirement_id" /> {{ item.requirement_code }}
              <RouterLink :to="{ name: 'project-requirement-detail', params: { projectId: item.project_id, requirementId: item.requirement_id } }">查看需求</RouterLink></label>
          </fieldset>
          <fieldset :disabled="busy"><legend>2. 当前章节固定版本（至少选择一项）</legend>
            <p v-if="!candidates?.sections.length">暂无可用章节版本；请先创建章节草案并确认其正文来源。</p>
            <label v-for="item in candidates?.sections" :key="item.section.solution_section_id"><input v-model="selectedSections" type="checkbox" :value="item.section.solution_section_id" /> {{ item.section.section_key }} · 版本 {{ item.version.version_no }} · {{ item.version.title }}（{{ item.version.version_state }}）
              <RouterLink :to="{ name: 'project-section-version-detail', params: { projectId: item.section.project_id, sectionId: item.section.solution_section_id, versionId: item.version.solution_section_version_id } }">查看固定章节</RouterLink></label>
          </fieldset>
          <fieldset :disabled="busy"><legend>3. 当前合格项目证据（可选）</legend>
            <p v-if="!candidates?.evidence.length">暂无当前合格证据。</p>
            <label v-for="item in candidates?.evidence" :key="item.evidence_id"><input v-model="selectedEvidence" type="checkbox" :value="item.evidence_id" /> {{ item.display_label }}</label>
            <p><RouterLink :to="{ name: 'project-evidence', params: { projectId: route.params.projectId } }">查看项目证据列表</RouterLink></p>
          </fieldset>
          <fieldset v-if="current.spec_type === 'MIGRATION_SPEC' || current.spec_type === 'INTERFACE_SPEC'" :disabled="busy"><legend>系统与字段</legend>
            <label for="revise-source">源系统</label><input id="revise-source" v-model="form.sourceSystem" maxlength="500" />
            <label for="revise-target">目标系统</label><input id="revise-target" v-model="form.targetSystem" maxlength="500" />
            <label for="revise-mappings">字段映射（每行“来源字段 → 目标字段”，至少一行）</label><textarea id="revise-mappings" v-model="form.fieldMappings" rows="4" />
          </fieldset>
          <fieldset v-if="current.spec_type === 'MIGRATION_SPEC'" :disabled="busy"><legend>迁移计划</legend>
            <label for="revise-scope">迁移范围</label><input id="revise-scope" v-model="form.scope" maxlength="2000" />
            <label for="revise-cleansing">清洗规则（每行一条）</label><textarea id="revise-cleansing" v-model="form.cleansingRules" rows="3" />
            <label for="revise-trial">试迁移计划</label><textarea id="revise-trial" v-model="form.trialPlan" rows="2" />
            <label for="revise-reconcile">对账计划</label><textarea id="revise-reconcile" v-model="form.reconciliationPlan" rows="2" />
            <label for="revise-rollback">回滚计划</label><textarea id="revise-rollback" v-model="form.rollbackPlan" rows="2" />
            <label for="revise-acceptance">验收标准</label><textarea id="revise-acceptance" v-model="form.acceptanceCriteria" rows="2" />
          </fieldset>
          <fieldset v-if="current.spec_type === 'INTERFACE_SPEC'" :disabled="busy"><legend>接口运行规则</legend>
            <label for="revise-direction">数据方向</label><select id="revise-direction" v-model="form.direction"><option value="INBOUND">流入</option><option value="OUTBOUND">流出</option><option value="BIDIRECTIONAL">双向</option></select>
            <label for="revise-owner">数据责任方</label><input id="revise-owner" v-model="form.dataOwner" maxlength="2000" />
            <label for="revise-frequency">交换频率</label><input id="revise-frequency" v-model="form.frequency" maxlength="2000" />
            <label for="revise-error">异常处理</label><textarea id="revise-error" v-model="form.errorHandling" rows="2" />
            <label for="revise-retry">重试策略</label><input id="revise-retry" v-model="form.retryPolicy" maxlength="2000" />
            <label for="revise-auth">认证方式</label><input id="revise-auth" v-model="form.authentication" maxlength="2000" />
          </fieldset>
          <fieldset v-if="current.spec_type === 'PROCESS_MODEL'" :disabled="busy"><legend>线性流程</legend>
            <p>只允许无损编辑线性流程。复杂分支不会被自动展平。</p>
            <label for="revise-start-role">发起角色</label><input id="revise-start-role" v-model="form.startRole" maxlength="128" />
            <label for="revise-steps">步骤（每行“节点标识 | 责任角色 | 输入字段（逗号分隔） | 输出字段（逗号分隔）”）</label><textarea id="revise-steps" v-model="form.processSteps" rows="5" />
            <label for="revise-end-role">结束角色</label><input id="revise-end-role" v-model="form.endRole" maxlength="128" />
          </fieldset>
          <fieldset v-if="current.spec_type === 'PERMISSION_DESIGN'" :disabled="busy"><legend>权限与职责分离</legend>
            <label for="revise-roles">角色（每行一个）</label><textarea id="revise-roles" v-model="form.roles" rows="3" />
            <label for="revise-resources">资源（每行一个）</label><textarea id="revise-resources" v-model="form.resources" rows="3" />
            <label for="revise-grants">授予权限（每行“角色 | 资源 | 操作 | 范围”）</label><textarea id="revise-grants" v-model="form.grants" rows="4" />
            <label for="revise-separation">默认拒绝/职责分离策略</label><textarea id="revise-separation" v-model="form.separationPolicy" rows="2" />
            <label for="revise-duties">互斥角色（每行“角色 A | 角色 B”）</label><textarea id="revise-duties" v-model="form.separationOfDuties" rows="2" />
          </fieldset>
          <label for="revise-assumptions">4. 假设（每行一条，可选）</label><textarea id="revise-assumptions" v-model="form.assumptions" rows="3" />
          <label for="revise-exclusions">5. 排除项（每行一条，可选）</label><textarea id="revise-exclusions" v-model="form.exclusions" rows="3" />
          <label><input v-model="confirmRevise" type="checkbox" :disabled="busy" /> 我已核对原版本、当前固定来源与修订内容，确认只创建新的 DRAFT</label>
        </template>
        <button type="submit" :disabled="busy || locked || (pending ? !confirmRetry : !confirmRevise)">{{ busy ? "正在提交…" : pending ? "按原操作号重试" : "创建修订 DRAFT" }}</button>
      </form>
    </template>
  </section>
</template>

<style scoped>
.spec-revise{max-width:64rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}
.spec-revise form,.spec-revise fieldset{display:grid;gap:.7rem}.spec-revise fieldset{border:1px solid #aaa;border-radius:.5rem}
.spec-revise textarea,.spec-revise select,.spec-revise input:not([type=checkbox]){width:100%;box-sizing:border-box}
.spec-revise [role=alert]{color:#a21d25}.warning{padding:.8rem 1rem;border-left:.3rem solid #d29b42;background:#fff8e9}
</style>
