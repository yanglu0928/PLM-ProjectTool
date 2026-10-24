<script setup lang="ts">
import { computed, inject, onUnmounted, reactive, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { DocumentReadClient, type DocumentView } from "@/modules/document/api/documentReadClient";
import { ProjectMemberReadClient, type ProjectMemberView } from "@/modules/project/api/projectMemberReadClient";
import { PrototypeIdentityReadClient, PrototypeReadError, PrototypeTemplateReadClient, PrototypeVersionReadClient,
  type PrototypeTemplateCursor, type PrototypeTemplateView, type PrototypeVersionCursor, type PrototypeVersionView,
  type PrototypeView } from "@/modules/prototype/api/prototypeReadClient";
import { PrototypeWriteClient, PrototypeWriteError, type PrototypeReviewSubmission,
  type PrototypeValidationReport, type PrototypeVersionCreateInput } from "@/modules/prototype/api/prototypeWriteClient";
import { RequirementReadClient, type RequirementCursor, type RequirementView } from "@/modules/requirement/api/requirementReadClient";

type Pending = Readonly<{ kind: "create"; etag: string; input: PrototypeVersionCreateInput; key: string }>
  | Readonly<{ kind: "validate"; versionId: string; key: string }>
  | Readonly<{ kind: "review"; versionId: string; reviewers: readonly string[]; key: string }>;
const props = defineProps<{ session?: SessionClient; identities?: PrototypeIdentityReadClient;
  versions?: PrototypeVersionReadClient; templates?: PrototypeTemplateReadClient; documents?: DocumentReadClient;
  requirements?: RequirementReadClient; members?: ProjectMemberReadClient; writer?: PrototypeWriteClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const identities = toRaw(props.identities ?? new PrototypeIdentityReadClient());
const versionsApi = toRaw(props.versions ?? new PrototypeVersionReadClient());
const templatesApi = toRaw(props.templates ?? new PrototypeTemplateReadClient());
const documentsApi = toRaw(props.documents ?? new DocumentReadClient());
const requirementsApi = toRaw(props.requirements ?? new RequirementReadClient());
const membersApi = toRaw(props.members ?? new ProjectMemberReadClient());
const writer = toRaw(props.writer ?? new PrototypeWriteClient(session));
const identity = session.view; const route = useRoute();
const root = ref<PrototypeView | null>(null); const versions = ref<readonly PrototypeVersionView[]>([]);
const templates = ref<readonly PrototypeTemplateView[]>([]); const documents = ref<readonly DocumentView[]>([]);
const requirements = ref<readonly RequirementView[]>([]); const reviewers = ref<readonly ProjectMemberView[]>([]);
const selected = ref<PrototypeVersionView | null>(null); const selectedReviewers = ref<string[]>([]);
const report = ref<PrototypeValidationReport | null>(null); const submission = ref<PrototypeReviewSubmission | null>(null);
const pending = ref<Pending | null>(null); const busy = ref(false); const loaded = ref(false);
const error = ref(""); const notice = ref(""); const confirmed = ref(false);
const form = reactive({ templateKey: "", artifactVersions: [] as string[], requirementVersions: [] as string[],
  interactionMode: "CLICK_THROUGH", navigationMode: "LINEAR", interactionDescription: "" });
let generation = 0; let mounted = true;
const projectId = () => typeof route.params.projectId === "string" ? route.params.projectId : "";
const prototypeId = () => typeof route.params.prototypeId === "string" ? route.params.prototypeId : "";
const directVersionId = () => typeof route.params.versionId === "string" ? route.params.versionId : null;
const role = computed(() => identity?.authorized_projects.find(item => item.project_id === projectId())?.role ?? null);
const live = computed(() => !!identity && !identity.password_change_required && session.canSubmit
  && session.view?.user.user_id === identity.user.user_id);
const canWrite = computed(() => live.value && ["PROJECT_MANAGER", "IMPLEMENTATION_MEMBER"].includes(role.value ?? ""));
const canSubmit = computed(() => live.value && role.value === "PROJECT_MANAGER");
const approvedRequirements = computed(() => requirements.value.filter(item => item.state === "ACTIVE"
  && item.current_approved_version_ref !== null));
const availableDocuments = computed(() => documents.value.filter(item => item.state === "ACTIVE"
  && (item.effective_version_ref ?? item.latest_version_ref)));
const availableTemplates = computed(() => templates.value.filter(item => item.state === "ACTIVE" && item.is_current));
function documentVersion(item: DocumentView) { return item.effective_version_ref ?? item.latest_version_ref!; }
function templateKey(item: PrototypeTemplateView) { return `${item.prototype_template_id}:${item.prototype_template_version_id}`; }
function templateFor(item: PrototypeVersionView) { return templates.value.find(value => value.prototype_template_id === item.template_id
  && value.prototype_template_version_id === item.template_version_id) ?? null; }
function requirementFor(versionId: string) { return requirements.value.find(value => value.current_approved_version_ref === versionId) ?? null; }
function documentFor(versionId: string) { return documents.value.find(value => documentVersion(value) === versionId) ?? null; }

async function load() {
  if (!identity || identity.password_change_required || busy.value) return;
  const project = projectId(), prototype = prototypeId(), exactVersion = directVersionId(), run = ++generation;
  busy.value = true; loaded.value = false; error.value = ""; notice.value = ""; pending.value = null;
  try {
    const [rootValue, versionFirst, templateFirst, documentFirst, requirementFirst, memberFirst, direct] = await Promise.all([
      identities.get(project, prototype), versionsApi.list(project, prototype, 100), templatesApi.listProject(project),
      documentsApi.list({ kind: "PROJECT", projectId: project }), requirementsApi.listRequirements(project, 200),
      membersApi.list(project), exactVersion ? versionsApi.get(project, prototype, exactVersion) : Promise.resolve(null),
    ]);
    const versionItems = [...versionFirst.items]; let versionCursor = versionFirst.next_cursor; let versionPages = 1;
    while (versionCursor && versionPages < 20) { const page = await versionsApi.list(project, prototype, 100, versionCursor as PrototypeVersionCursor);
      versionItems.push(...page.items); versionCursor = page.next_cursor; versionPages += 1; }
    const templateItems = [...templateFirst.items]; let templateCursor = templateFirst.next_cursor; let templatePages = 1;
    while (templateCursor && templatePages < 20) { const page = await templatesApi.listProject(project, 50, templateCursor as PrototypeTemplateCursor);
      templateItems.push(...page.items); templateCursor = page.next_cursor; templatePages += 1; }
    const documentItems = [...documentFirst.items]; let documentCursor = documentFirst.next_cursor; let documentPages = 1;
    while (documentCursor && documentPages < 20) { const page = await documentsApi.list({ kind: "PROJECT", projectId: project }, documentCursor);
      documentItems.push(...page.items); documentCursor = page.next_cursor; documentPages += 1; }
    const requirementItems = [...requirementFirst.items]; let requirementCursor = requirementFirst.next_cursor; let requirementPages = 1;
    while (requirementCursor && requirementPages < 20) { const page = await requirementsApi.listRequirements(project, 200, requirementCursor as RequirementCursor);
      requirementItems.push(...page.items); requirementCursor = page.next_cursor; requirementPages += 1; }
    const memberItems = [...memberFirst.items]; let memberCursor = memberFirst.next_cursor; let memberPages = 1;
    while (memberCursor && memberPages < 20) { const page = await membersApi.list(project, memberCursor); memberItems.push(...page.items);
      memberCursor = page.next_cursor; memberPages += 1; }
    if (versionCursor || templateCursor || documentCursor || requirementCursor || memberCursor
      || new Set(versionItems.map(item => item.prototype_version_id)).size !== versionItems.length
      || new Set(templateItems.map(item => item.prototype_template_id)).size !== templateItems.length
      || new Set(documentItems.map(item => item.document_id)).size !== documentItems.length
      || new Set(requirementItems.map(item => item.requirement_id)).size !== requirementItems.length
      || new Set(memberItems.map(item => item.member_id)).size !== memberItems.length) throw new PrototypeReadError("PROTOTYPE_READ_UNAVAILABLE");
    if (!mounted || run !== generation || project !== projectId() || prototype !== prototypeId()
      || exactVersion !== directVersionId()) return;
    root.value = rootValue; versions.value = Object.freeze(versionItems); templates.value = Object.freeze(templateItems);
    documents.value = Object.freeze(documentItems); requirements.value = Object.freeze(requirementItems);
    reviewers.value = Object.freeze(memberItems.filter(item => item.state === "ACTIVE" && item.user.user_id !== identity.user.user_id));
    selected.value = direct ?? null; report.value = null; submission.value = null; selectedReviewers.value = [];
    form.templateKey = availableTemplates.value[0] ? templateKey(availableTemplates.value[0]) : "";
    form.artifactVersions = []; form.requirementVersions = []; form.interactionMode = "CLICK_THROUGH";
    form.navigationMode = "LINEAR"; form.interactionDescription = ""; confirmed.value = false; loaded.value = true;
  } catch (failure) { if (mounted && run === generation) { root.value = null; versions.value = []; templates.value = [];
    documents.value = []; requirements.value = []; reviewers.value = []; selected.value = null;
    error.value = failure instanceof Error ? failure.message : "暂时无法准备原型版本。"; } }
  finally { if (mounted && run === generation) busy.value = false; }
}
function createInput(): PrototypeVersionCreateInput {
  const template = availableTemplates.value.find(item => templateKey(item) === form.templateKey);
  if (!template) throw new PrototypeWriteError("PROTOTYPE_WRITE_INVALID_INPUT");
  const artifacts = [...new Set(form.artifactVersions)].sort().map(target_id => Object.freeze({
    artifact_kind: "DOCUMENT_VERSION" as const, target_id }));
  const requirementRefs = [...new Set(form.requirementVersions)].sort().map(requirement_version_id => {
    const requirement = approvedRequirements.value.find(item => item.current_approved_version_ref === requirement_version_id);
    if (!requirement) throw new PrototypeWriteError("PROTOTYPE_WRITE_INVALID_INPUT");
    return Object.freeze({ requirement_id: requirement.requirement_id, requirement_version_id });
  });
  return Object.freeze({ template_id: template.prototype_template_id,
    template_version_id: template.prototype_template_version_id, artifact_refs: Object.freeze(artifacts),
    requirement_refs: Object.freeze(requirementRefs), interaction_spec: Object.freeze({ mode: form.interactionMode,
      navigation: form.navigationMode, description: form.interactionDescription.trim() }),
    coverage_summary: Object.freeze({ basis: "APPROVED_REQUIREMENTS", requirement_count: requirementRefs.length,
      artifact_count: artifacts.length, maintained_by: "HUMAN" }) });
}
async function create(attempt: Extract<Pending, { kind: "create" }> | null = null) {
  if (!canWrite.value || !root.value || root.value.state !== "ACTIVE" || busy.value
    || (!confirmed.value && attempt === null)) return;
  let value: Extract<Pending, { kind: "create" }>;
  try { value = attempt ?? Object.freeze({ kind: "create" as const, etag: root.value.etag, input: createInput(),
    key: `prototype-version-create-${crypto.randomUUID()}` }); }
  catch (failure) { error.value = failure instanceof Error ? failure.message : "版本输入不完整。"; return; }
  const project = projectId(), prototype = prototypeId(), run = ++generation; busy.value = true;
  error.value = ""; notice.value = ""; pending.value = value;
  try { const created = await writer.createVersion(project, prototype, value.etag, value.input, value.key);
    if (!mounted || run !== generation || project !== projectId() || prototype !== prototypeId()) return;
    const { prototype_etag, ...version } = created; root.value = { ...root.value, etag: prototype_etag };
    versions.value = Object.freeze([version, ...versions.value.filter(item => item.prototype_version_id !== version.prototype_version_id)]);
    selected.value = version; report.value = null; submission.value = null; pending.value = null; confirmed.value = false;
    notice.value = "不可变DRAFT版本已创建；创建和后续校验都不代表批准。";
  } catch (failure) { if (mounted && run === generation) { error.value = failure instanceof Error ? failure.message : "暂时无法确认版本创建结果。";
    if (!(failure instanceof PrototypeWriteError) || !failure.uncertain) pending.value = null; } }
  finally { if (mounted && run === generation) busy.value = false; }
}
function choose(item: PrototypeVersionView) { if (busy.value || pending.value) return; selected.value = item;
  report.value = null; submission.value = null; selectedReviewers.value = []; error.value = ""; notice.value = ""; }
async function validate(attempt: Extract<Pending, { kind: "validate" }> | null = null) {
  if (!canWrite.value || !selected.value || selected.value.state !== "DRAFT" || busy.value) return;
  const value = attempt ?? Object.freeze({ kind: "validate" as const, versionId: selected.value.prototype_version_id,
    key: `prototype-version-validate-${crypto.randomUUID()}` });
  const project = projectId(), prototype = prototypeId(), run = ++generation; busy.value = true;
  error.value = ""; notice.value = ""; pending.value = value; if (attempt === null) { report.value = null; submission.value = null; }
  try { const result = await writer.validateVersion(project, prototype, value.versionId, value.key);
    if (!mounted || run !== generation || selected.value?.prototype_version_id !== value.versionId) return;
    report.value = result; submission.value = null; pending.value = null; notice.value = result.valid
      ? "服务端当前事实校验通过；这不是批准结论，仍须选择评审人并正式送审。"
      : "校验未通过；固定版本不可覆盖，请修正输入后创建新版本。";
  } catch (failure) { if (mounted && run === generation) { error.value = failure instanceof Error ? failure.message : "暂时无法确认校验结果。";
    if (!(failure instanceof PrototypeWriteError) || !failure.uncertain) pending.value = null; } }
  finally { if (mounted && run === generation) busy.value = false; }
}
async function submit(attempt: Extract<Pending, { kind: "review" }> | null = null) {
  if (!canSubmit.value || !selected.value || selected.value.state !== "DRAFT" || !report.value?.valid || busy.value
    || (!selectedReviewers.value.length && attempt === null)) return;
  const value = attempt ?? Object.freeze({ kind: "review" as const, versionId: selected.value.prototype_version_id,
    reviewers: Object.freeze([...selectedReviewers.value].sort()), key: `prototype-version-review-${crypto.randomUUID()}` });
  const project = projectId(), prototype = prototypeId(), run = ++generation; busy.value = true;
  error.value = ""; notice.value = ""; pending.value = value;
  try { const result = await writer.submitVersionReview(project, prototype, value.versionId, value.reviewers, value.key);
    if (!mounted || run !== generation || selected.value?.prototype_version_id !== value.versionId) return;
    submission.value = result; selected.value = { ...selected.value, state: "IN_REVIEW" };
    versions.value = Object.freeze(versions.value.map(item => item.prototype_version_id === value.versionId ? selected.value! : item));
    pending.value = null; notice.value = "版本已进入正式评审；评审回执不是批准结论。";
  } catch (failure) { if (mounted && run === generation) { error.value = failure instanceof Error ? failure.message : "暂时无法确认送审结果。";
    if (!(failure instanceof PrototypeWriteError) || !failure.uncertain) pending.value = null; } }
  finally { if (mounted && run === generation) busy.value = false; }
}
watch(() => [route.params.projectId, route.params.prototypeId, route.params.versionId], () => { generation += 1;
  root.value = null; selected.value = null; pending.value = null; busy.value = false; error.value = ""; notice.value = "";
  void load(); }, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; });
</script>

<template>
  <section class="version-page" aria-labelledby="version-title" :aria-busy="busy">
    <p class="section-kicker">项目原型</p><h1 id="version-title">原型固定版本</h1>
    <p class="warning"><strong>版本创建和服务端校验都不是批准。</strong>只有固定输入经过正式评审并批准后，Prototype Root正式指针才会更新。</p>
    <p><RouterLink :to="{ name: 'project-prototype-detail', params: { projectId: route.params.projectId, prototypeId: route.params.prototypeId } }">返回原型详情</RouterLink></p>
    <p v-if="!identity" role="status">尚未读取当前身份，请先登录。</p><p v-else-if="identity.password_change_required" role="status">当前账户须先修改密码。</p>
    <template v-else><button type="button" :disabled="busy" @click="load">{{ busy ? "正在读取…" : "刷新版本和业务候选" }}</button>
      <p v-if="error" role="alert">{{ error }}</p><p v-if="notice" role="status">{{ notice }}</p>
      <section v-if="root"><h2>{{ root.name }}的版本</h2><p v-if="loaded && !versions.length">尚无固定版本。</p>
        <ol class="versions"><li v-for="item in versions" :key="item.prototype_version_id"><strong>版本 {{ item.version_no }}</strong>
          <span>{{ item.state }} · 固定需求 {{ item.requirement_refs.length }} 项 · 固定制品 {{ item.artifact_refs.length }} 项</span>
          <button type="button" :disabled="busy || !!pending" @click="choose(item)">查看固定输入{{ item.state === 'DRAFT' ? '并校验' : '' }}</button></li></ol></section>
      <form v-if="canWrite && root?.state === 'ACTIVE'" @submit.prevent="create()"><h2>创建不可变DRAFT</h2>
        <label>固定模板版本<select v-model="form.templateKey" required><option disabled value="">请选择</option>
          <option v-for="item in availableTemplates" :key="templateKey(item)" :value="templateKey(item)">{{ item.name }} · {{ item.scope }} · 版本 {{ item.version_no }}</option></select></label>
        <fieldset><legend>固定文档制品（至少一项）</legend><label v-for="item in availableDocuments" :key="item.document_id" class="choice"><input v-model="form.artifactVersions" type="checkbox" :value="documentVersion(item)">{{ item.title }} · {{ item.display_name }}</label></fieldset>
        <fieldset><legend>当前已批准需求（至少一项）</legend><label v-for="item in approvedRequirements" :key="item.requirement_id" class="choice"><input v-model="form.requirementVersions" type="checkbox" :value="item.current_approved_version_ref">{{ item.requirement_code }}</label></fieldset>
        <fieldset><legend>不可执行交互说明</legend><label>交互模式<select v-model="form.interactionMode"><option>CLICK_THROUGH</option><option>FORM_WORKFLOW</option><option>READ_ONLY</option></select></label>
          <label>导航方式<select v-model="form.navigationMode"><option>LINEAR</option><option>NON_LINEAR</option></select></label>
          <label>人工说明<textarea v-model="form.interactionDescription" required maxlength="2000"></textarea></label>
          <p>页面只保存说明合同，不执行脚本、代码、命令或外部URL。</p></fieldset>
        <p>Coverage摘要由所选批准需求和固定制品数量自动生成，不能手工伪造。</p>
        <label class="confirm"><input v-model="confirmed" type="checkbox">我已人工核对模板、需求、文档和交互说明；AI建议未被自动确认为事实。</label>
        <button :disabled="busy || !!pending || !confirmed || !form.templateKey || !form.artifactVersions.length || !form.requirementVersions.length || !form.interactionDescription.trim()">创建固定DRAFT版本</button></form>
      <section v-if="selected" class="selected"><h2>版本 {{ selected.version_no }} 固定输入</h2>
        <dl><dt>状态</dt><dd>{{ selected.state }}</dd><dt>模板</dt><dd>{{ templateFor(selected)?.name ?? '历史模板（当前列表不可见）' }}</dd>
          <dt>内容指纹</dt><dd>{{ selected.content_fingerprint }}</dd></dl>
        <h3>固定文档</h3><ul><li v-for="artifact in selected.artifact_refs" :key="`${artifact.artifact_kind}:${artifact.target_id}`">
          <template v-if="artifact.document_id"><RouterLink :to="{ name: 'project-document-detail', params: { projectId: selected.project_id, documentId: artifact.document_id }, query: { version: artifact.target_id } }">{{ documentFor(artifact.target_id)?.title ?? '定位固定文档版本' }}</RouterLink></template>
          <span v-else>服务端未提供受权文档根定位，不能猜测原文位置。</span></li></ul>
        <h3>固定批准需求</h3><ul><li v-for="requirement in selected.requirement_refs" :key="requirement.requirement_version_id">{{ requirementFor(requirement.requirement_version_id)?.requirement_code ?? '历史批准需求' }}</li></ul>
        <h3>交互与覆盖</h3><p>交互模式：{{ selected.interaction_spec.mode ?? '历史结构' }}；导航：{{ selected.interaction_spec.navigation ?? '历史结构' }}</p>
        <p>这些字段是固定说明，不会在浏览器执行。</p>
        <template v-if="selected.state === 'DRAFT' && canWrite"><button type="button" :disabled="busy || !!pending" @click="validate()">运行服务端当前事实校验</button>
          <div v-if="report" class="report"><strong>{{ report.valid ? '校验通过（尚未批准）' : '校验未通过' }}</strong>
            <ul><li v-for="issue in report.blocking_issues" :key="issue">{{ issue }}</li></ul><time :datetime="report.checked_at">{{ new Date(report.checked_at).toLocaleString('zh-CN') }}</time></div>
          <fieldset v-if="report?.valid && canSubmit"><legend>正式送审</legend><p>固定策略：PROTOTYPE_ALL_V1；所有所选评审人都必须完成。</p>
            <label v-for="item in reviewers" :key="item.user.user_id" class="choice"><input v-model="selectedReviewers" type="checkbox" :value="item.user.user_id">{{ item.user.display_name }}（{{ item.role }} / {{ item.department.name }}）</label>
            <button type="button" :disabled="busy || !!pending || !selectedReviewers.length" @click="submit()">提交正式评审</button></fieldset>
          <p v-else-if="report?.valid && !canSubmit">校验通过，但只有项目负责人可以提交正式评审。</p></template>
        <p v-if="submission">评审已创建，Round {{ submission.round_no }}，状态 IN_REVIEW；这不是批准结论。</p></section>
      <aside v-if="pending" class="pending"><strong>上次{{ pending.kind === 'create' ? '版本创建' : pending.kind === 'validate' ? '校验' : '送审' }}结果未知。</strong>
        <p>不要改变输入或生成新操作号；请恢复同一操作以取得首次结果。</p>
        <button v-if="pending.kind === 'create'" type="button" :disabled="busy" @click="create(pending)">恢复原版本创建</button>
        <button v-else-if="pending.kind === 'validate'" type="button" :disabled="busy" @click="validate(pending)">恢复原校验</button>
        <button v-else type="button" :disabled="busy" @click="submit(pending)">恢复原送审</button></aside>
    </template>
  </section>
</template>

<style scoped>
.version-page{max-width:74rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}.version-page>section,.version-page form,.pending{display:grid;gap:.7rem;margin:1rem 0;padding:1rem;border:1px solid #d8dee7;border-radius:.8rem}.versions{display:grid;gap:.7rem;padding:0;list-style:none}.versions li{display:flex;align-items:center;gap:1rem;flex-wrap:wrap;padding:.8rem;border:1px solid #d8dee7;border-radius:.7rem}.version-page form>label,.version-page fieldset{display:grid;gap:.45rem}.version-page textarea{min-height:5rem}.choice,.confirm{display:flex!important;align-items:flex-start;gap:.4rem}.warning,.pending{padding:.8rem 1rem;border-left:.3rem solid #d29b42;background:#fff8e9}.selected dl{display:grid;grid-template-columns:9rem 1fr}.selected dd{margin:0;overflow-wrap:anywhere}.report{padding:.8rem;background:#f0f7f2}.version-page [role=alert]{color:#a21d25}
</style>
