<script setup lang="ts">
import { computed, inject, onUnmounted, reactive, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { PrototypeIdentityReadClient, PrototypeLinkReadClient, PrototypeReadError, PrototypeVersionReadClient,
  type PrototypeCursor, type PrototypeLinkCursor, type PrototypeLinkView, type PrototypeVersionView,
  type PrototypeView } from "@/modules/prototype/api/prototypeReadClient";
import { PrototypeWriteClient, PrototypeWriteError, type PrototypeLinkInput } from "@/modules/prototype/api/prototypeWriteClient";
import { RequirementReadClient, type RequirementCursor, type RequirementVersionView,
  type RequirementView } from "@/modules/requirement/api/requirementReadClient";

type Purpose = PrototypeLinkInput["purpose"];
type CriterionDraft = { readonly ref: string; readonly ordinal: number; readonly observable: string;
  status: "" | "COVERED" | "UNCOVERED"; reason: string };
type Pending = Readonly<{ kind: "create"; input: PrototypeLinkInput; key: string }>
  | Readonly<{ kind: "revoke"; linkId: string; key: string }>
  | Readonly<{ kind: "supersede"; linkId: string; input: PrototypeLinkInput; key: string }>;

const props = defineProps<{ session?: SessionClient; identities?: PrototypeIdentityReadClient;
  versions?: PrototypeVersionReadClient; links?: PrototypeLinkReadClient; requirements?: RequirementReadClient;
  writer?: PrototypeWriteClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const identitiesApi = toRaw(props.identities ?? new PrototypeIdentityReadClient());
const versionsApi = toRaw(props.versions ?? new PrototypeVersionReadClient());
const linksApi = toRaw(props.links ?? new PrototypeLinkReadClient());
const requirementsApi = toRaw(props.requirements ?? new RequirementReadClient());
const writer = toRaw(props.writer ?? new PrototypeWriteClient(session));
const route = useRoute(); const identity = session.view;
const requirements = ref<readonly RequirementView[]>([]); const prototypes = ref<readonly PrototypeView[]>([]);
const links = ref<readonly PrototypeLinkView[]>([]); const criteria = ref<CriterionDraft[]>([]);
const fixedRequirement = ref<RequirementVersionView | null>(null); const fixedPrototype = ref<PrototypeVersionView | null>(null);
const editing = ref<PrototypeLinkView | null>(null); const revokeTarget = ref<PrototypeLinkView | null>(null);
const pending = ref<Pending | null>(null); const preparedSignature = ref("");
const busy = ref(false); const loaded = ref(false); const error = ref(""); const notice = ref("");
const confirmed = ref(false); const revokeConfirmed = ref(false);
const form = reactive<{ requirementId: string; prototypeId: string; purpose: Purpose }>({
  requirementId: "", prototypeId: "", purpose: "VALIDATES",
});
let generation = 0; let mounted = true;
const projectId = () => typeof route.params.projectId === "string" ? route.params.projectId : "";
const role = computed(() => identity?.authorized_projects.find(item => item.project_id === projectId())?.role ?? null);
const live = computed(() => !!identity && !identity.password_change_required && session.canSubmit
  && session.view?.user.user_id === identity.user.user_id);
const canWrite = computed(() => live.value && ["PROJECT_MANAGER", "IMPLEMENTATION_MEMBER"].includes(role.value ?? ""));
const requirementChoices = computed(() => requirements.value.filter(item => item.state === "ACTIVE"
  && item.current_approved_version_ref !== null));
const prototypeChoices = computed(() => prototypes.value.filter(item => item.state === "ACTIVE"
  && item.current_approved_version_ref !== null));
const signature = computed(() => `${form.requirementId}:${form.prototypeId}:${form.purpose}`);
const prepared = computed(() => !!fixedRequirement.value && !!fixedPrototype.value && criteria.value.length > 0
  && preparedSignature.value === signature.value);
const partitionReady = computed(() => prepared.value && criteria.value.every(item => item.status
  && (item.status !== "UNCOVERED" || item.reason.trim())) && criteria.value.some(item => item.status === "COVERED"));
function requirementFor(id: string) { return requirements.value.find(item => item.requirement_id === id) ?? null; }
function prototypeFor(id: string) { return prototypes.value.find(item => item.prototype_id === id) ?? null; }
function resetPrepared() { fixedRequirement.value = null; fixedPrototype.value = null; criteria.value = [];
  preparedSignature.value = ""; confirmed.value = false; }

async function load() {
  if (!identity || identity.password_change_required || busy.value) return;
  const project = projectId(), run = ++generation; busy.value = true; loaded.value = false;
  error.value = ""; notice.value = ""; pending.value = null; editing.value = null; revokeTarget.value = null; resetPrepared();
  try {
    const [requirementFirst, prototypeFirst, linkFirst] = await Promise.all([
      requirementsApi.listRequirements(project, 200), identitiesApi.list(project, 50), linksApi.list(project, 50),
    ]);
    const requirementItems = [...requirementFirst.items]; let requirementCursor = requirementFirst.next_cursor; let requirementPages = 1;
    while (requirementCursor && requirementPages < 20) { const page = await requirementsApi.listRequirements(project, 200, requirementCursor as RequirementCursor);
      requirementItems.push(...page.items); requirementCursor = page.next_cursor; requirementPages += 1; }
    const prototypeItems = [...prototypeFirst.items]; let prototypeCursor = prototypeFirst.next_cursor; let prototypePages = 1;
    while (prototypeCursor && prototypePages < 20) { const page = await identitiesApi.list(project, 50, prototypeCursor as PrototypeCursor);
      prototypeItems.push(...page.items); prototypeCursor = page.next_cursor; prototypePages += 1; }
    const linkItems = [...linkFirst.items]; let linkCursor = linkFirst.next_cursor; let linkPages = 1;
    while (linkCursor && linkPages < 20) { const page = await linksApi.list(project, 50, linkCursor as PrototypeLinkCursor);
      linkItems.push(...page.items); linkCursor = page.next_cursor; linkPages += 1; }
    if (requirementCursor || prototypeCursor || linkCursor
      || new Set(requirementItems.map(item => item.requirement_id)).size !== requirementItems.length
      || new Set(prototypeItems.map(item => item.prototype_id)).size !== prototypeItems.length
      || new Set(linkItems.map(item => item.requirement_prototype_link_id)).size !== linkItems.length) {
      throw new PrototypeReadError("PROTOTYPE_READ_UNAVAILABLE");
    }
    if (!mounted || run !== generation || project !== projectId()) return;
    requirements.value = Object.freeze(requirementItems); prototypes.value = Object.freeze(prototypeItems);
    links.value = Object.freeze(linkItems); form.requirementId = requirementChoices.value[0]?.requirement_id ?? "";
    form.prototypeId = prototypeChoices.value[0]?.prototype_id ?? ""; form.purpose = "VALIDATES"; loaded.value = true;
  } catch (failure) { if (mounted && run === generation) { requirements.value = []; prototypes.value = []; links.value = [];
    error.value = failure instanceof Error ? failure.message : "暂时无法准备需求原型关联。"; } }
  finally { if (mounted && run === generation) busy.value = false; }
}

async function prepareCoverage(source: PrototypeLinkView | null = editing.value) {
  if (!canWrite.value || busy.value || pending.value) return;
  const requirement = requirementChoices.value.find(item => item.requirement_id === form.requirementId);
  const prototype = prototypeChoices.value.find(item => item.prototype_id === form.prototypeId);
  if (!requirement?.current_approved_version_ref || !prototype?.current_approved_version_ref) {
    error.value = "只能选择当前仍为ACTIVE且具有已批准版本的需求和原型。"; resetPrepared(); return;
  }
  if (source && (source.requirement_id !== requirement.requirement_id || source.prototype_id !== prototype.prototype_id
    || source.purpose !== form.purpose)) { error.value = "替换必须保持原需求、原型和用途不变。"; resetPrepared(); return; }
  const project = projectId(), expected = signature.value, run = ++generation; busy.value = true;
  error.value = ""; notice.value = ""; resetPrepared();
  try {
    const [requirementVersion, prototypeVersion] = await Promise.all([
      requirementsApi.getVersion(project, requirement.requirement_id, requirement.current_approved_version_ref),
      versionsApi.get(project, prototype.prototype_id, prototype.current_approved_version_ref),
    ]);
    if (!mounted || run !== generation || project !== projectId() || expected !== signature.value) return;
    if (requirementVersion.state !== "APPROVED" || prototypeVersion.state !== "APPROVED"
      || !prototypeVersion.requirement_refs.some(item => item.requirement_id === requirement.requirement_id
        && item.requirement_version_id === requirementVersion.requirement_version_id)) {
      throw new Error("当前批准原型未固定引用所选批准需求，不能建立覆盖关联。");
    }
    const refs = requirementVersion.acceptance_criteria.map(item => item.acceptance_criterion_ref);
    if (!refs.length || refs.some(item => item === null) || new Set(refs).size !== refs.length) {
      throw new Error("当前需求版本未提供完整、唯一的稳定验收标准引用；不能手工填写UUID代替。请先升级服务端投影。");
    }
    const covered = new Set(source?.coverage.covered_acceptance_criterion_refs ?? []);
    const gaps = new Map((source?.coverage.uncovered_acceptance_criteria ?? [])
      .map(item => [item.acceptance_criterion_ref, item.reason] as const));
    criteria.value = requirementVersion.acceptance_criteria.map(item => ({ ref: item.acceptance_criterion_ref!, ordinal: item.ordinal,
      observable: item.observable_result, status: covered.has(item.acceptance_criterion_ref!) ? "COVERED"
        : gaps.has(item.acceptance_criterion_ref!) ? "UNCOVERED" : "", reason: gaps.get(item.acceptance_criterion_ref!) ?? "" }));
    fixedRequirement.value = requirementVersion; fixedPrototype.value = prototypeVersion; preparedSignature.value = expected;
    notice.value = "已固定读取双端当前批准版本。请逐条标记覆盖状态；空白或部分标记不会被推断为完整覆盖。";
  } catch (failure) { if (mounted && run === generation) { resetPrepared();
    error.value = failure instanceof Error ? failure.message : "暂时无法核对双端当前批准版本。"; } }
  finally { if (mounted && run === generation) busy.value = false; }
}

function linkInput(): PrototypeLinkInput {
  if (!prepared.value || !partitionReady.value || !fixedRequirement.value || !fixedPrototype.value) {
    throw new PrototypeWriteError("PROTOTYPE_WRITE_INVALID_INPUT");
  }
  const covered = criteria.value.filter(item => item.status === "COVERED").map(item => item.ref).sort();
  const gaps = criteria.value.filter(item => item.status === "UNCOVERED").map(item => Object.freeze({
    acceptance_criterion_ref: item.ref, reason: item.reason.trim(),
  })).sort((left, right) => left.acceptance_criterion_ref.localeCompare(right.acceptance_criterion_ref));
  return Object.freeze({ requirement_id: fixedRequirement.value.requirement_id,
    requirement_version_id: fixedRequirement.value.requirement_version_id,
    prototype_id: fixedPrototype.value.prototype_id, prototype_version_id: fixedPrototype.value.prototype_version_id,
    purpose: form.purpose, coverage: Object.freeze({ covered_acceptance_criterion_refs: Object.freeze(covered),
      uncovered_acceptance_criteria: Object.freeze(gaps) }) });
}

async function save(attempt: Extract<Pending, { kind: "create" | "supersede" }> | null = null) {
  if (!canWrite.value || busy.value || (!confirmed.value && attempt === null)) return;
  let value: Extract<Pending, { kind: "create" | "supersede" }>;
  try { value = attempt ?? (editing.value
    ? Object.freeze({ kind: "supersede" as const, linkId: editing.value.requirement_prototype_link_id,
      input: linkInput(), key: `prototype-link-supersede-${crypto.randomUUID()}` })
    : Object.freeze({ kind: "create" as const, input: linkInput(), key: `prototype-link-create-${crypto.randomUUID()}` })); }
  catch (failure) { error.value = failure instanceof Error ? failure.message : "覆盖分区输入不完整。"; return; }
  const project = projectId(), run = ++generation; busy.value = true; error.value = ""; notice.value = ""; pending.value = value;
  try {
    const result = value.kind === "create" ? await writer.createLink(project, value.input, value.key)
      : await writer.supersedeLink(project, value.linkId, value.input, value.key);
    if (!mounted || run !== generation || project !== projectId()) return;
    const replacedId = value.kind === "supersede" ? value.linkId : null;
    links.value = Object.freeze([result, ...links.value.filter(item => item.requirement_prototype_link_id !== result.requirement_prototype_link_id)
      .map(item => item.requirement_prototype_link_id === replacedId
        ? { ...item, state: "SUPERSEDED" as const, superseded_by_ref: result.requirement_prototype_link_id } : item)]);
    pending.value = null; editing.value = null; confirmed.value = false; resetPrepared();
    notice.value = replacedId ? "原关联已被新关联替换；替换记录不等于评审批准。" : "关联已创建；覆盖分区是人工声明，不等于评审批准。";
  } catch (failure) { if (mounted && run === generation) { error.value = failure instanceof Error ? failure.message : "暂时无法确认关联写入结果。";
    if (!(failure instanceof PrototypeWriteError) || !failure.uncertain) pending.value = null; } }
  finally { if (mounted && run === generation) busy.value = false; }
}

function beginSupersede(item: PrototypeLinkView) {
  if (!canWrite.value || busy.value || pending.value || item.state !== "ACTIVE") return;
  editing.value = item; revokeTarget.value = null; form.requirementId = item.requirement_id;
  form.prototypeId = item.prototype_id; form.purpose = item.purpose; error.value = ""; notice.value = ""; resetPrepared();
}
function beginRevoke(item: PrototypeLinkView) { if (!canWrite.value || busy.value || pending.value || item.state !== "ACTIVE") return;
  revokeTarget.value = item; editing.value = null; revokeConfirmed.value = false; error.value = ""; notice.value = ""; resetPrepared(); }
function cancelAction() { if (busy.value || pending.value) return; editing.value = null; revokeTarget.value = null;
  revokeConfirmed.value = false; resetPrepared(); }
async function revoke(attempt: Extract<Pending, { kind: "revoke" }> | null = null) {
  if (!canWrite.value || busy.value || (!revokeConfirmed.value && attempt === null)) return;
  const target = attempt?.linkId ?? revokeTarget.value?.requirement_prototype_link_id; if (!target) return;
  const value = attempt ?? Object.freeze({ kind: "revoke" as const, linkId: target,
    key: `prototype-link-revoke-${crypto.randomUUID()}` });
  const project = projectId(), run = ++generation; busy.value = true; error.value = ""; notice.value = ""; pending.value = value;
  try { const result = await writer.revokeLink(project, value.linkId, value.key);
    if (!mounted || run !== generation || project !== projectId()) return;
    links.value = Object.freeze(links.value.map(item => item.requirement_prototype_link_id === value.linkId ? result : item));
    pending.value = null; revokeTarget.value = null; revokeConfirmed.value = false; notice.value = "关联已撤销；历史记录继续保留。";
  } catch (failure) { if (mounted && run === generation) { error.value = failure instanceof Error ? failure.message : "暂时无法确认撤销结果。";
    if (!(failure instanceof PrototypeWriteError) || !failure.uncertain) pending.value = null; } }
  finally { if (mounted && run === generation) busy.value = false; }
}

watch(() => route.params.projectId, () => { generation += 1; requirements.value = []; prototypes.value = []; links.value = [];
  pending.value = null; editing.value = null; revokeTarget.value = null; busy.value = false; error.value = ""; notice.value = "";
  resetPrepared(); void load(); }, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; });
</script>

<template>
  <section class="link-page" aria-labelledby="link-title" :aria-busy="busy">
    <p class="section-kicker">项目原型</p><h1 id="link-title">需求与原型覆盖关联</h1>
    <p class="warning"><strong>关联和覆盖声明都不是评审批准。</strong>缺少关联、空白或部分映射均不能推断为完整覆盖；每条验收标准必须明确选择“已覆盖”或填写“未覆盖原因”。</p>
    <p><RouterLink :to="{ name: 'project-prototypes', params: { projectId: route.params.projectId } }">返回项目原型</RouterLink></p>
    <p v-if="!identity" role="status">尚未读取当前身份，请先登录。</p><p v-else-if="identity.password_change_required" role="status">当前账户须先修改密码。</p>
    <template v-else><button type="button" :disabled="busy" @click="load">{{ busy ? "正在读取…" : "刷新关联和业务候选" }}</button>
      <p v-if="error" role="alert">{{ error }}</p><p v-if="notice" role="status">{{ notice }}</p>
      <section><h2>全部关联历史</h2><p v-if="loaded && !links.length">尚无关联记录；这不代表需求无需原型覆盖。</p>
        <ol class="links"><li v-for="item in links" :key="item.requirement_prototype_link_id">
          <div><strong>{{ requirementFor(item.requirement_id)?.requirement_code ?? '历史需求' }} → {{ prototypeFor(item.prototype_id)?.name ?? '历史原型' }}</strong>
            <span>{{ item.purpose }} · {{ item.state }} · 已覆盖 {{ item.coverage.covered_acceptance_criterion_refs.length }} 条 · 未覆盖 {{ item.coverage.uncovered_acceptance_criteria.length }} 条</span></div>
          <template v-if="item.state === 'ACTIVE' && canWrite"><button type="button" :disabled="busy || !!pending" @click="beginSupersede(item)">替换关联</button>
            <button type="button" :disabled="busy || !!pending" @click="beginRevoke(item)">撤销关联</button></template></li></ol></section>
      <form v-if="canWrite && !revokeTarget" @submit.prevent="save()"><h2>{{ editing ? '替换现有覆盖关联' : '创建覆盖关联' }}</h2>
        <p v-if="editing">替换保持需求、原型和用途不变，只允许更新到双端当前批准版本并重做完整覆盖分区。</p>
        <label>当前已批准需求<select v-model="form.requirementId" required :disabled="!!editing"><option disabled value="">请选择</option>
          <option v-for="item in requirementChoices" :key="item.requirement_id" :value="item.requirement_id">{{ item.requirement_code }}</option></select></label>
        <label>当前已批准原型<select v-model="form.prototypeId" required :disabled="!!editing"><option disabled value="">请选择</option>
          <option v-for="item in prototypeChoices" :key="item.prototype_id" :value="item.prototype_id">{{ item.name }}</option></select></label>
        <label>关联用途<select v-model="form.purpose" :disabled="!!editing"><option value="ILLUSTRATES">ILLUSTRATES</option><option value="VALIDATES">VALIDATES</option><option value="ACCEPTANCE_REFERENCE">ACCEPTANCE_REFERENCE</option></select></label>
        <button type="button" :disabled="busy || !!pending || !form.requirementId || !form.prototypeId" @click="prepareCoverage()">加载验收标准并核对双端批准版本</button>
        <p v-if="prepared">固定需求版本 {{ fixedRequirement?.version_no }}；固定原型版本 {{ fixedPrototype?.version_no }}。</p>
        <fieldset v-if="criteria.length"><legend>逐条验收覆盖分区</legend><article v-for="item in criteria" :key="item.ref" class="criterion">
          <strong>验收标准 {{ item.ordinal + 1 }}</strong><p>{{ item.observable }}</p>
          <label><input v-model="item.status" type="radio" :name="`criterion-${item.ref}`" value="COVERED">已覆盖</label>
          <label><input v-model="item.status" type="radio" :name="`criterion-${item.ref}`" value="UNCOVERED">未覆盖</label>
          <label v-if="item.status === 'UNCOVERED'">未覆盖原因<textarea v-model="item.reason" required maxlength="1000"></textarea></label>
        </article></fieldset>
        <p v-if="criteria.length && !partitionReady">必须完成全部验收标准分区，未覆盖项填写原因，并至少有一条已覆盖。</p>
        <label class="confirm"><input v-model="confirmed" type="checkbox">我已人工核对双端批准版本及逐条覆盖分区；未把AI建议或部分映射当作已确认事实。</label>
        <div class="actions"><button :disabled="busy || !!pending || !confirmed || !partitionReady">{{ editing ? '创建替换关联' : '创建关联' }}</button>
          <button v-if="editing" type="button" :disabled="busy || !!pending" @click="cancelAction">取消替换</button></div></form>
      <section v-if="revokeTarget" class="danger"><h2>撤销关联</h2><p>将撤销 {{ requirementFor(revokeTarget.requirement_id)?.requirement_code ?? '历史需求' }} 与 {{ prototypeFor(revokeTarget.prototype_id)?.name ?? '历史原型' }} 的活动关联，历史记录不会删除。</p>
        <label class="confirm"><input v-model="revokeConfirmed" type="checkbox">确认撤销此活动关联。</label><div class="actions">
          <button type="button" :disabled="busy || !!pending || !revokeConfirmed" @click="revoke()">确认撤销</button>
          <button type="button" :disabled="busy || !!pending" @click="cancelAction">取消</button></div></section>
      <p v-if="!canWrite">当前角色可查看关联历史，但只有项目负责人或实施成员可以创建、替换或撤销。</p>
      <aside v-if="pending" class="pending"><strong>上次{{ pending.kind === 'create' ? '创建' : pending.kind === 'revoke' ? '撤销' : '替换' }}结果未知。</strong>
        <p>不要修改输入或生成新操作号；请用完全相同的固定输入和操作号恢复首次结果。</p>
        <button v-if="pending.kind === 'revoke'" type="button" :disabled="busy" @click="revoke(pending)">恢复原撤销</button>
        <button v-else type="button" :disabled="busy" @click="save(pending)">恢复原{{ pending.kind === 'create' ? '创建' : '替换' }}</button></aside>
    </template>
  </section>
</template>

<style scoped>
.link-page{max-width:76rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}.link-page>section,.link-page form,.pending{display:grid;gap:.75rem;margin:1rem 0;padding:1rem;border:1px solid #d8dee7;border-radius:.8rem}.links{display:grid;gap:.7rem;padding:0;list-style:none}.links li{display:flex;align-items:center;gap:.7rem;flex-wrap:wrap;padding:.8rem;border:1px solid #d8dee7;border-radius:.7rem}.links li div{display:grid;gap:.25rem;margin-right:auto}.link-page form>label,.link-page fieldset,.criterion{display:grid;gap:.45rem}.criterion{padding:.8rem;border-top:1px solid #d8dee7}.criterion textarea{min-height:4rem}.criterion>label,.confirm{display:flex;align-items:flex-start;gap:.4rem}.criterion>label:has(textarea){display:grid}.warning,.pending{padding:.8rem 1rem;border-left:.3rem solid #d29b42;background:#fff8e9}.danger{border-left:.3rem solid #a21d25!important}.actions{display:flex;gap:.7rem;flex-wrap:wrap}.link-page [role=alert]{color:#a21d25}
</style>
