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
import { StructuredSpecCreateClient, StructuredSpecCreateError,
  type SpecType, type StructuredSpecDraft } from "@/modules/solution/api/structuredSpecCreateClient";
import { buildStructuredSpecPayload, emptyStructuredSpecForm } from "./structuredSpecForm";

type CandidateLoader = typeof loadStructuredSpecCandidates;
const props = defineProps<{ session?: SessionClient; creator?: StructuredSpecCreateClient;
  candidateLoader?: CandidateLoader }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const creator = toRaw(props.creator ?? new StructuredSpecCreateClient(session));
const candidateLoader = props.candidateLoader ?? loadStructuredSpecCandidates;
const route = useRoute();
const projectId = () => typeof route.params.projectId === "string" ? route.params.projectId : "";
const candidates = ref<StructuredSpecCandidates | null>(null);
const selectedRequirements = ref<string[]>([]);
const selectedSections = ref<string[]>([]);
const selectedEvidence = ref<string[]>([]);
const specType = ref<SpecType>("MIGRATION_SPEC");
const form = reactive(emptyStructuredSpecForm());
const loading = ref(false); const busy = ref(false); const error = ref("");
const confirmCreate = ref(false); const confirmRetry = ref(false); const locked = ref(false);
const createdId = ref(""); const createdSeries = ref("");
const pending = ref<{ project: string; actor: string; draft: StructuredSpecDraft; key: string } | null>(null);
let mounted = true; let generation = 0;
function authorized() {
  return mounted && !!session.view && !session.view.password_change_required && session.canSubmit
    && session.view.authorized_projects.some(item => item.project_id === projectId()
      && (item.role === "PROJECT_MANAGER" || item.role === "IMPLEMENTATION_MEMBER"));
}
function storageKey() {
  return `plm.sol.spec.create.pending.${session.view?.user.user_id ?? "none"}.${projectId()}`;
}
function restore() {
  pending.value = null; locked.value = false; confirmRetry.value = false; confirmCreate.value = false;
  createdId.value = ""; createdSeries.value = ""; error.value = "";
  if (!authorized()) return;
  try {
    const raw = window.sessionStorage.getItem(storageKey());
    if (!raw) return;
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("invalid");
    const item = value as Record<string, unknown>;
    if (item.project !== projectId() || item.actor !== session.view?.user.user_id
      || typeof item.key !== "string" || !/^[\x20-\x7e]{16,128}$/.test(item.key)
      || !item.draft || typeof item.draft !== "object" || Array.isArray(item.draft)
      || new TextEncoder().encode(JSON.stringify(item.draft)).length > 512 * 1024) throw new Error("invalid");
    const draft = item.draft as Record<string, unknown>;
    if (typeof draft.spec_type !== "string" || !Array.isArray(draft.requirement_refs)
      || !Array.isArray(draft.section_refs) || !Array.isArray(draft.evidence_ids)
      || !Array.isArray(draft.artifact_ids) || draft.artifact_ids.length !== 0
      || !draft.payload || typeof draft.payload !== "object" || Array.isArray(draft.payload)) {
      throw new Error("invalid");
    }
    pending.value = item as unknown as typeof pending.value;
  } catch {
    locked.value = true;
    error.value = "原操作记录无法读取，已停止提交；请核对专项历史与审计记录。";
  }
}
async function load() {
  if (!authorized() || loading.value) return;
  const project = projectId(), run = ++generation;
  loading.value = true; candidates.value = null;
  if (!locked.value) error.value = "";
  try {
    const available = await candidateLoader(project, new RequirementReadClient(),
      new SectionReadClient(), new SectionVersionReadClient(), new EvidenceListClient());
    if (!mounted || run !== generation || project !== projectId()) return;
    candidates.value = available;
  } catch (failure) {
    if (mounted && run === generation && !locked.value) error.value = failure instanceof Error
      ? failure.message : "暂时无法核对来源候选。";
  } finally { if (mounted && run === generation) loading.value = false; }
}
watch(() => [route.name, route.params.projectId], () => {
  if (route.name !== "project-structured-spec-create") return;
  generation += 1; loading.value = false; candidates.value = null;
  selectedRequirements.value = []; selectedSections.value = []; selectedEvidence.value = [];
  specType.value = "MIGRATION_SPEC"; Object.assign(form, emptyStructuredSpecForm());
  restore(); void load();
}, { immediate: true });
watch(() => JSON.stringify([specType.value, form, selectedRequirements.value,
  selectedSections.value, selectedEvidence.value]), () => { confirmCreate.value = false; });
onUnmounted(() => { mounted = false; generation += 1; });
function canCreate() {
  if (pending.value) return authorized();
  return authorized() && !!candidates.value && !loading.value;
}
function draftFromSelection(): StructuredSpecDraft {
  const available = candidates.value;
  if (!available || !selectedRequirements.value.length || !selectedSections.value.length
    || selectedRequirements.value.length > 500 || selectedSections.value.length > 500
    || selectedEvidence.value.length > 500
    || new Set(selectedRequirements.value).size !== selectedRequirements.value.length
    || new Set(selectedSections.value).size !== selectedSections.value.length
    || new Set(selectedEvidence.value).size !== selectedEvidence.value.length) {
    throw new Error("请选择至少一条已批准需求和一个当前章节版本；来源不得重复。");
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
  return { spec_type: specType.value, payload: buildStructuredSpecPayload(specType.value, form),
    requirement_refs, section_refs, evidence_ids, artifact_ids: [] };
}
async function submit() {
  if (!canCreate() || busy.value || locked.value || createdId.value
    || (pending.value ? !confirmRetry.value : !confirmCreate.value)) return;
  const project = projectId(), actor = session.view!.user.user_id;
  let attempt = pending.value;
  if (!attempt) {
    let draft: StructuredSpecDraft;
    try { draft = draftFromSelection(); }
    catch (failure) { error.value = failure instanceof Error ? failure.message : "来源或专项内容无效。"; return; }
    attempt = { project, actor, draft, key: crypto.randomUUID() };
    try { window.sessionStorage.setItem(storageKey(), JSON.stringify(attempt)); }
    catch { error.value = "无法保存原操作号，本次未提交。"; return; }
    pending.value = attempt;
  }
  if (attempt.project !== project || attempt.actor !== actor) { locked.value = true; return; }
  confirmRetry.value = false; busy.value = true; error.value = "";
  try {
    const result = await creator.create(project, attempt.draft, attempt.key);
    if (!mounted || project !== projectId() || actor !== session.view?.user.user_id) return;
    createdId.value = result.structured_solution_spec_id;
    createdSeries.value = result.spec_series_id;
    try { window.sessionStorage.removeItem(storageKey()); pending.value = null; }
    catch { locked.value = true; error.value = "草案已创建，但原操作号清理失败；请停止再次提交。"; }
  } catch (failure) {
    if (!mounted) return;
    if (failure instanceof StructuredSpecCreateError && failure.code === "CONFLICT_IDEMPOTENCY") locked.value = true;
    error.value = failure instanceof Error ? failure.message : "创建结果无法确认，请保留原操作号。";
  } finally { if (mounted) busy.value = false; }
}
</script>

<template>
  <section class="spec-create" aria-labelledby="spec-create-title" :aria-busy="loading || busy">
    <p class="section-kicker">项目方案</p><h1 id="spec-create-title">创建结构化专项草案</h1>
    <p class="warning">此处只建立待评审 DRAFT，不代表已批准或已交付。提交时服务器会重新核对固定需求、章节、文档和证据。</p>
    <p><RouterLink :to="{ name: 'project-structured-specs', params: { projectId: route.params.projectId } }">查看专项版本历史</RouterLink></p>
    <p v-if="!authorized()" role="status">仅当前项目负责人或实施成员可创建；请确认会话与项目权限。</p>
    <template v-else>
      <button type="button" :disabled="loading || busy || !!pending || locked" @click="load()">{{ loading ? "正在核对…" : "刷新当前候选" }}</button>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="createdId" role="status">专项草案已创建（版本编号 {{ createdId }}，系列编号 {{ createdSeries }}）。当前仅为 DRAFT；<RouterLink :to="{ name: 'project-structured-spec-detail', params: { projectId: route.params.projectId, specId: createdId } }">查看专项详情</RouterLink>。送审尚未开放。</p>
      <p v-else-if="loading" role="status">正在读取已批准需求、当前章节和项目证据…</p>
      <form v-else-if="canCreate()" @submit.prevent="submit">
        <template v-if="pending">
          <p class="warning" role="status">存在原创建操作。结果不确定时请先核对专项历史与审计，不得改内容或换操作号。</p>
          <p>原内容：{{ pending.draft.spec_type }}；需求 {{ pending.draft.requirement_refs.length }} 项，章节 {{ pending.draft.section_refs.length }} 项。重试保持原正文和原操作号。</p>
          <label><input v-model="confirmRetry" type="checkbox" :disabled="busy || locked" /> 我已核对原操作，确认按原内容与原操作号重试</label>
        </template>
        <template v-else>
          <fieldset :disabled="busy"><legend>1. 当前已批准需求版本（至少选择一项）</legend>
            <p v-if="!candidates?.requirements.length">暂无当前已批准需求；请先完成需求评审。</p>
            <label v-for="item in candidates?.requirements" :key="item.requirement_id"><input v-model="selectedRequirements" type="checkbox" :value="item.requirement_id" /> {{ item.requirement_code }}
              <RouterLink :to="{ name: 'project-requirement-detail', params: { projectId: item.project_id,
                requirementId: item.requirement_id } }">查看需求</RouterLink></label>
          </fieldset>
          <fieldset :disabled="busy"><legend>2. 当前章节固定版本（至少选择一项）</legend>
            <p v-if="!candidates?.sections.length">暂无可用章节版本；请先创建章节草案并确认其正文来源。</p>
            <label v-for="item in candidates?.sections" :key="item.section.solution_section_id"><input v-model="selectedSections" type="checkbox" :value="item.section.solution_section_id" /> {{ item.section.section_key }} · 版本 {{ item.version.version_no }} · {{ item.version.title }}（{{ item.version.version_state }}）
              <RouterLink :to="{ name: 'project-section-version-detail', params: { projectId: item.section.project_id,
                sectionId: item.section.solution_section_id,
                versionId: item.version.solution_section_version_id } }">查看固定章节</RouterLink></label>
          </fieldset>
          <fieldset :disabled="busy"><legend>3. 当前合格项目证据（可选）</legend>
            <p v-if="!candidates?.evidence.length">暂无当前合格证据。</p>
            <label v-for="item in candidates?.evidence" :key="item.evidence_id"><input v-model="selectedEvidence" type="checkbox" :value="item.evidence_id" /> {{ item.display_label }}</label>
            <p><RouterLink :to="{ name: 'project-evidence', params: { projectId: route.params.projectId } }">查看项目证据列表</RouterLink></p>
          </fieldset>
          <label for="spec-type">4. 专项类型</label>
          <select id="spec-type" v-model="specType" :disabled="busy">
            <option value="MIGRATION_SPEC">数据迁移设计</option>
            <option value="INTERFACE_SPEC">接口设计</option>
            <option value="PROCESS_MODEL">业务流程模型</option>
            <option value="PERMISSION_DESIGN">权限设计</option>
          </select>
          <fieldset v-if="specType === 'MIGRATION_SPEC' || specType === 'INTERFACE_SPEC'" :disabled="busy"><legend>系统与字段</legend>
            <label for="spec-source">源系统</label><input id="spec-source" v-model="form.sourceSystem" maxlength="500" placeholder="例如：原 PLM 系统" />
            <label for="spec-target">目标系统</label><input id="spec-target" v-model="form.targetSystem" maxlength="500" placeholder="例如：新 PLM 系统" />
            <label for="spec-mappings">字段映射（每行“来源字段 → 目标字段”，至少一行）</label>
            <textarea id="spec-mappings" v-model="form.fieldMappings" rows="4" placeholder="旧料号 → 零件编号" />
          </fieldset>
          <fieldset v-if="specType === 'MIGRATION_SPEC'" :disabled="busy"><legend>迁移计划</legend>
            <label for="spec-scope">迁移范围</label><input id="spec-scope" v-model="form.scope" maxlength="2000" placeholder="例如：零件主数据及分类" />
            <label for="spec-cleansing">清洗规则（每行一条）</label><textarea id="spec-cleansing" v-model="form.cleansingRules" rows="3" placeholder="按料号去重" />
            <label for="spec-trial">试迁移计划</label><textarea id="spec-trial" v-model="form.trialPlan" rows="2" placeholder="说明试点范围、时间与责任人" />
            <label for="spec-reconcile">对账计划</label><textarea id="spec-reconcile" v-model="form.reconciliationPlan" rows="2" placeholder="说明源/目标数据如何比对" />
            <label for="spec-rollback">回滚计划</label><textarea id="spec-rollback" v-model="form.rollbackPlan" rows="2" placeholder="说明失败时如何恢复" />
            <label for="spec-acceptance">验收标准</label><textarea id="spec-acceptance" v-model="form.acceptanceCriteria" rows="2" placeholder="例如：关键字段差异为零" />
          </fieldset>
          <fieldset v-if="specType === 'INTERFACE_SPEC'" :disabled="busy"><legend>接口运行规则</legend>
            <label for="spec-direction">数据方向</label><select id="spec-direction" v-model="form.direction"><option value="INBOUND">流入</option><option value="OUTBOUND">流出</option><option value="BIDIRECTIONAL">双向</option></select>
            <label for="spec-owner">数据责任方</label><input id="spec-owner" v-model="form.dataOwner" maxlength="2000" placeholder="部门或岗位" />
            <label for="spec-frequency">交换频率</label><input id="spec-frequency" v-model="form.frequency" maxlength="2000" placeholder="例如：每小时" />
            <label for="spec-error">异常处理</label><textarea id="spec-error" v-model="form.errorHandling" rows="2" placeholder="失败时告警、人工处理流程" />
            <label for="spec-retry">重试策略</label><input id="spec-retry" v-model="form.retryPolicy" maxlength="2000" placeholder="例如：最多三次，间隔五分钟" />
            <label for="spec-auth">认证方式</label><input id="spec-auth" v-model="form.authentication" maxlength="2000" placeholder="说明认证机制，不填写口令或密钥" />
          </fieldset>
          <fieldset v-if="specType === 'PROCESS_MODEL'" :disabled="busy"><legend>线性流程</legend>
            <p>按顺序写步骤，系统连接“开始 → 各步骤 → 结束”。复杂分支图暂不能在此页面编辑。</p>
            <label for="spec-start-role">发起角色</label><input id="spec-start-role" v-model="form.startRole" maxlength="128" placeholder="例如：业务申请人" />
            <label for="spec-steps">步骤（每行“节点标识 | 责任角色 | 输入字段（逗号分隔） | 输出字段（逗号分隔）”；无输入/输出可留空）</label>
            <textarea id="spec-steps" v-model="form.processSteps" rows="5" placeholder="review | 项目负责人 | 申请单 | 审核结果" />
            <label for="spec-end-role">结束角色</label><input id="spec-end-role" v-model="form.endRole" maxlength="128" placeholder="例如：业务申请人" />
          </fieldset>
          <fieldset v-if="specType === 'PERMISSION_DESIGN'" :disabled="busy"><legend>权限与职责分离</legend>
            <p>默认拒绝所有未列出的操作。请只填写角色、资源和权限规则，不填写账户口令。</p>
            <label for="spec-roles">角色（每行一个）</label><textarea id="spec-roles" v-model="form.roles" rows="3" placeholder="项目负责人" />
            <label for="spec-resources">资源（每行一个）</label><textarea id="spec-resources" v-model="form.resources" rows="3" placeholder="项目方案" />
            <label for="spec-grants">授予权限（每行“角色 | 资源 | 操作 | 范围”）</label>
            <textarea id="spec-grants" v-model="form.grants" rows="4" placeholder="项目负责人 | 项目方案 | 编辑 | 当前项目" />
            <label for="spec-separation">默认拒绝/职责分离策略</label><textarea id="spec-separation" v-model="form.separationPolicy" rows="2" placeholder="说明申请人与审批人如何分离" />
            <label for="spec-duties">互斥角色（可选，每行“角色 A | 角色 B”）</label><textarea id="spec-duties" v-model="form.separationOfDuties" rows="2" placeholder="申请人 | 审批人" />
          </fieldset>
          <label for="spec-assumptions">5. 假设（每行一条，可选）</label><textarea id="spec-assumptions" v-model="form.assumptions" rows="3" placeholder="例如：字段清单将在联调前确认" />
          <label for="spec-exclusions">6. 排除项（每行一条，可选）</label><textarea id="spec-exclusions" v-model="form.exclusions" rows="3" placeholder="例如：本阶段不包含历史附件迁移" />
          <label><input v-model="confirmCreate" type="checkbox" :disabled="busy" /> 我已核对固定来源与专项内容，确认仅创建待评审草案</label>
        </template>
        <button type="submit" :disabled="busy || locked || (pending ? !confirmRetry : !confirmCreate)">{{ busy ? "正在提交…" : pending ? "按原操作号重试" : "创建 DRAFT 草案" }}</button>
      </form>
    </template>
  </section>
</template>

<style scoped>
.spec-create{max-width:64rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}
.spec-create form,.spec-create fieldset{display:grid;gap:.7rem}.spec-create fieldset{border:1px solid #aaa;border-radius:.5rem}
.spec-create textarea,.spec-create select,.spec-create input:not([type=checkbox]){width:100%;box-sizing:border-box}
.spec-create [role=alert]{color:#a21d25}.warning{padding:.8rem 1rem;border-left:.3rem solid #d29b42;background:#fff8e9}
</style>
