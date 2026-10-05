<script setup lang="ts">
import { computed, inject, onUnmounted, reactive, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { EvidenceViewerClient, EvidenceViewerClientError, type EvidenceViewerDescriptor } from "@/modules/evidence/api/evidenceViewerClient";
import { HandoverActionReadClient, HandoverActionReadError, type HandoverActionCursor,
  type HandoverActionDetail, type HandoverActionSummary } from "@/modules/handover/api/handoverActionReadClient";
import { HandoverActionWriteClient, HandoverActionWriteError, type HandoverActionFirstReceipt,
  type HandoverActionType, type HandoverActionPriority } from "@/modules/handover/api/handoverActionWriteClient";

const props = defineProps<{ session?: SessionClient; actions?: HandoverActionReadClient; writes?: HandoverActionWriteClient;
  evidence?: EvidenceViewerClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const actions = toRaw(props.actions ?? new HandoverActionReadClient());
const writes = toRaw(props.writes ?? new HandoverActionWriteClient(session));
const evidence = toRaw(props.evidence ?? new EvidenceViewerClient());
const identity = session.view; const route = useRoute(); const items = ref<readonly HandoverActionSummary[]>([]);
const cursor = ref<HandoverActionCursor | null>(null); const loaded = ref(false); const busy = ref(false); const error = ref("");
const detail = ref<HandoverActionDetail | null>(null); const detailBusy = ref(false); const detailError = ref("");
const located = ref<EvidenceViewerDescriptor | null>(null); const locationError = ref(""); const locationBusy = ref(false);
const createOpen = ref(false); const operation = ref<"patch" | "start" | "submit" | "verify" | "cancel" | null>(null);
const mutationBusy = ref(false); const mutationError = ref(""); const mutationMessage = ref("");
let generation = 0; let detailGeneration = 0; let locationGeneration = 0; let mounted = true;

const stateLabels = Object.freeze({ OPEN: "待开始", IN_PROGRESS: "处理中", SUBMITTED: "已提交待验证", VERIFIED: "已验证待关闭",
  CLOSED: "已关闭", CANCELLED: "已取消" });
const actionTypeLabels: Readonly<Record<HandoverActionType, string>> = Object.freeze({ PROVIDE_INFO: "补充资料", CONFIRM_DECISION: "确认决策",
  RESOLVE_CONFLICT: "解决冲突", MITIGATE_RISK: "处置风险", DEFINE_SCOPE: "明确范围", OTHER: "其他" });
const priorityLabels: Readonly<Record<HandoverActionPriority, string>> = Object.freeze({ LOW: "低", MEDIUM: "中", HIGH: "高", URGENT: "紧急" });
function projectId() { return typeof route.params.projectId === "string" ? route.params.projectId : ""; }
function role() { return identity?.authorized_projects.find(item => item.project_id === projectId())?.role ?? null; }
function mayRead() { return mounted && !!identity && !identity.password_change_required && session.view?.user.user_id === identity.user.user_id; }
const mayCreate = computed(() => ["PROJECT_MANAGER", "IMPLEMENTATION_MEMBER"].includes(role() ?? ""));
function assigned() { return !!detail.value && detail.value.owner_ref === identity?.user.user_id; }
function mayPatch() { return !!detail.value && ["OPEN", "IN_PROGRESS"].includes(detail.value.action_state)
  && (["PROJECT_MANAGER", "IMPLEMENTATION_MEMBER"].includes(role() ?? "") || assigned()); }
function mayStart() { return detail.value?.action_state === "OPEN" && (role() === "PROJECT_MANAGER" || assigned()); }
function maySubmit() { return detail.value?.action_state === "IN_PROGRESS" && (role() === "IMPLEMENTATION_MEMBER" || assigned()); }
function mayVerify() { return detail.value?.action_state === "SUBMITTED" && ["PROJECT_MANAGER", "CUSTOMER_MANAGER"].includes(role() ?? ""); }
function mayCancel() { return !!detail.value && !["CLOSED", "CANCELLED"].includes(detail.value.action_state) && role() === "PROJECT_MANAGER"; }

interface InputFieldDraft { name: string; format: string; example: string; required: boolean; }
const blankField = (): InputFieldDraft => ({ name: "", format: "", example: "", required: true });
const createForm = reactive({ sourceKind: "HUMAN" as "HUMAN" | "ANALYSIS_ITEM", analysisVersion: "", sourceItem: "", humanReason: "",
  actionType: "PROVIDE_INFO" as HandoverActionType, title: "", ownerRef: identity?.user.user_id ?? "", dueAt: "",
  priority: "MEDIUM" as HandoverActionPriority, reason: "" });
const createFields = ref<InputFieldDraft[]>([blankField()]);
const patchForm = reactive({ title: "", ownerRef: "", dueAt: "", priority: "MEDIUM" as HandoverActionPriority });
const patchFields = ref<InputFieldDraft[]>([blankField()]);
const commandForm = reactive({ reason: "", documents: "", evidence: "" });
type MutationReceipt = HandoverActionFirstReceipt<{ readonly action_item_id: string }>;
interface PendingMutation { label: string; task: () => Promise<MutationReceipt>; after: (receipt: MutationReceipt) => Promise<void>; }
const pendingRetry = ref<PendingMutation | null>(null);

function clearDetail() { detailGeneration += 1; locationGeneration += 1; detail.value = null; detailError.value = ""; located.value = null;
  locationError.value = ""; operation.value = null; mutationError.value = ""; mutationMessage.value = ""; pendingRetry.value = null; }
function summary(value: HandoverActionDetail): HandoverActionSummary { return Object.freeze({ action_item_id: value.action_item_id,
  source_kind: value.source_kind, action_type: value.action_type, title: value.title, owner_ref: value.owner_ref, due_at: value.due_at,
  priority: value.priority, action_state: value.action_state, submitted_at: value.submitted_at, verified_at: value.verified_at,
  closed_at: value.closed_at, resolution_trace_ref: value.resolution_trace_ref, updated_at: value.updated_at, etag: value.etag }); }
async function refreshDetail(actionId: string) { const project = projectId(); const value = await actions.get(project, actionId);
  if (!mounted || project !== projectId() || !mayRead()) return; detail.value = value;
  items.value = Object.freeze(items.value.map(item => item.action_item_id === actionId ? summary(value) : item)); }
async function load(next: HandoverActionCursor | null = null, replace = false) { if (!mayRead() || busy.value) return; const project = projectId(); const current = ++generation;
  if (replace) { items.value = []; cursor.value = null; loaded.value = false; clearDetail(); } busy.value = true; error.value = "";
  try { const page = await actions.list(project, 50, next); if (!mounted || current !== generation || projectId() !== project || !mayRead()) return;
    const known = new Set(items.value.map(item => item.action_item_id)); if (page.items.some(item => known.has(item.action_item_id))) throw new HandoverActionReadError("HANDOVER_ACTION_UNAVAILABLE");
    items.value = Object.freeze([...items.value, ...page.items]); cursor.value = page.next_cursor; loaded.value = true;
  } catch (failure) { if (mounted && current === generation) { items.value = []; cursor.value = null; loaded.value = false; clearDetail();
    error.value = failure instanceof HandoverActionReadError ? failure.message : "暂时无法读取交接待办。"; } }
  finally { if (mounted && current === generation) busy.value = false; } }
async function show(item: HandoverActionSummary) { if (!mayRead() || detailBusy.value) return; const project = projectId(); const current = ++detailGeneration;
  locationGeneration += 1; detail.value = null; located.value = null; locationError.value = ""; detailError.value = ""; operation.value = null;
  mutationError.value = ""; mutationMessage.value = ""; pendingRetry.value = null; detailBusy.value = true;
  try { const value = await actions.get(project, item.action_item_id); if (!mounted || current !== detailGeneration || projectId() !== project || !mayRead()) return; detail.value = value; }
  catch (failure) { if (mounted && current === detailGeneration) detailError.value = failure instanceof HandoverActionReadError ? failure.message : "暂时无法读取待办详情。"; }
  finally { if (mounted && current === detailGeneration) detailBusy.value = false; } }
async function locate(evidenceId: string) { if (!detail.value || !detail.value.evidence.some(item => item.evidence_id === evidenceId) || locationBusy.value) return;
  const project = projectId(); const actionId = detail.value.action_item_id; const current = ++locationGeneration; located.value = null; locationError.value = ""; locationBusy.value = true;
  try { const value = await evidence.get({ kind: "PROJECT", projectId: project }, evidenceId); if (!mounted || current !== locationGeneration
    || projectId() !== project || detail.value?.action_item_id !== actionId || !mayRead()) return; located.value = value; }
  catch (failure) { if (mounted && current === locationGeneration) locationError.value = failure instanceof EvidenceViewerClientError ? failure.message : "暂时无法定位待办依据。"; }
  finally { if (mounted && current === locationGeneration) locationBusy.value = false; } }

function localInput(iso: string) { const value = new Date(iso); return Number.isFinite(value.valueOf())
  ? new Date(value.valueOf() - value.getTimezoneOffset() * 60_000).toISOString().slice(0, 16) : ""; }
function utcInput(value: string) { const parsed = new Date(value); return Number.isFinite(parsed.valueOf()) ? parsed.toISOString().replace(".000Z", "Z") : value; }
function ids(value: string) { return value.split(/[\s,;]+/u).map(item => item.trim()).filter(Boolean); }
function documents(value: string) { return value.split(/\r?\n/u).map(line => line.trim()).filter(Boolean).map(line => { const pair = line.split(/[,，\s]+/u);
  return { document_id: pair[0] ?? "", document_version_id: pair[1] ?? "" }; }); }
function key(label: string) { return `handover-${label}-${globalThis.crypto.randomUUID()}`; }
function plainFields(values: readonly InputFieldDraft[]) { return { fields: values.map(value => ({ ...value })) }; }
function addField(target: "create" | "patch") { const values = target === "create" ? createFields : patchFields; if (values.value.length < 32) values.value.push(blankField()); }
function removeField(target: "create" | "patch", index: number) { const values = target === "create" ? createFields : patchFields;
  if (values.value.length > 1) values.value.splice(index, 1); }
function resetMutation() { mutationError.value = ""; mutationMessage.value = ""; pendingRetry.value = null; }
function beginCreate() { createOpen.value = !createOpen.value; resetMutation(); }
function beginPatch() { if (!detail.value) return; patchForm.title = detail.value.title; patchForm.ownerRef = detail.value.owner_ref;
  patchForm.dueAt = localInput(detail.value.due_at); patchForm.priority = detail.value.priority;
  patchFields.value = detail.value.requested_input_spec.fields.map(field => ({ ...field })); operation.value = "patch"; resetMutation(); }
function beginOperation(value: "start" | "submit" | "verify" | "cancel") { operation.value = value; commandForm.reason = "";
  commandForm.documents = ""; commandForm.evidence = ""; resetMutation(); }

async function attempt(command: PendingMutation) { if (mutationBusy.value) return; mutationBusy.value = true; mutationError.value = "";
  mutationMessage.value = ""; pendingRetry.value = null; let receipt: MutationReceipt;
  try { receipt = await command.task(); }
  catch (failure) { mutationError.value = failure instanceof HandoverActionWriteError ? failure.message : "操作结果无法确认，请重新读取。";
    if (failure instanceof HandoverActionWriteError && failure.uncertain) pendingRetry.value = command; mutationBusy.value = false; return; }
  try { await command.after(receipt); mutationMessage.value = `${command.label}已受理，并已重新读取当前待办事实。`; operation.value = null; createOpen.value = false; }
  catch { mutationMessage.value = `${command.label}已获得首次回执，但当前状态读取失败；请点击刷新核对，不要据此认定最终状态。`; }
  finally { mutationBusy.value = false; }
}
function createAction() { const attemptKey = key("create"); const project = projectId(); const sourceIsHuman = createForm.sourceKind === "HUMAN";
  const task = () => writes.create(project, { source_analysis_version_ref: sourceIsHuman ? null : createForm.analysisVersion,
    source_item_id: sourceIsHuman ? null : createForm.sourceItem, human_source_reason: sourceIsHuman ? createForm.humanReason : null,
    action_type: createForm.actionType, title: createForm.title, requested_input_spec: plainFields(createFields.value),
    owner_ref: createForm.ownerRef, due_at: utcInput(createForm.dueAt), priority: createForm.priority, created_reason: createForm.reason }, attemptKey);
  void attempt({ label: "创建待办", task, after: async () => { await load(null, true); } }); }
function patchAction() { if (!detail.value) return; const project = projectId(), actionId = detail.value.action_item_id, etag = detail.value.etag;
  const task = () => writes.patch(project, actionId, etag, { title: patchForm.title, requested_input_spec: plainFields(patchFields.value),
    owner_ref: patchForm.ownerRef, due_at: utcInput(patchForm.dueAt), priority: patchForm.priority });
  void attempt({ label: "更新待办", task, after: async () => refreshDetail(actionId) }); }
function transition(value: "start" | "submit" | "verify" | "cancel") { if (!detail.value) return; const project = projectId();
  const actionId = detail.value.action_item_id, etag = detail.value.etag, attemptKey = key(value); let task: () => Promise<MutationReceipt>;
  if (value === "start") task = () => writes.start(project, actionId, etag, attemptKey, commandForm.reason);
  else if (value === "submit") task = () => writes.submit(project, actionId, etag, attemptKey, documents(commandForm.documents), ids(commandForm.evidence), commandForm.reason);
  else if (value === "verify") task = () => writes.verify(project, actionId, etag, attemptKey, ids(commandForm.evidence), commandForm.reason);
  else task = () => writes.cancel(project, actionId, etag, attemptKey, commandForm.reason);
  const labels = { start: "开始处理", submit: "提交响应", verify: "验证响应", cancel: "取消待办" };
  void attempt({ label: labels[value], task, after: async () => refreshDetail(actionId) }); }

watch(() => route.params.projectId, () => { generation += 1; items.value = []; cursor.value = null; loaded.value = false; busy.value = false;
  error.value = ""; clearDetail(); createOpen.value = false; void load(null, true); }, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; clearDetail(); });
</script>

<template><section class="action-workbench" aria-labelledby="action-title" :aria-busy="busy || mutationBusy">
  <p class="section-kicker">项目交接</p><h1 id="action-title">交接待办与验证状态</h1>
  <p class="fact-warning"><strong>已提交不等于已完成。</strong> SUBMITTED 必须经过受权验证，VERIFIED 仍须正式关闭并形成 Resolution Trace。</p>
  <p><RouterLink :to="{ name: 'project-handover', params: { projectId: route.params.projectId } }">返回交接分析</RouterLink></p>
  <template v-if="!identity"><p role="status">尚未读取当前身份。请先登录。</p></template>
  <template v-else-if="identity.password_change_required"><p role="status">当前账户须先修改密码，暂不能读取交接待办。</p></template>
  <template v-else>
    <div class="toolbar"><button type="button" :disabled="busy || mutationBusy" @click="load(null, true)">{{ busy ? '正在读取…' : '刷新交接待办' }}</button>
      <button v-if="mayCreate" type="button" :disabled="mutationBusy" @click="beginCreate">{{ createOpen ? '收起创建区' : '创建交接待办' }}</button></div>
    <p v-if="error" role="alert">{{ error }}</p>
    <form v-if="createOpen && mayCreate" class="write-panel" @submit.prevent="createAction">
      <h2>创建交接待办</h2><p class="form-help">登记待办不会自动确认分析结论；请选择真实来源并明确告诉处理人需要维护什么。</p>
      <label>来源类型<select v-model="createForm.sourceKind"><option value="HUMAN">面对面调研/人工记录</option><option value="ANALYSIS_ITEM">已固定的分析问题</option></select></label>
      <label v-if="createForm.sourceKind === 'HUMAN'">人工来源说明<textarea v-model="createForm.humanReason" required maxlength="2000" placeholder="例如：2026-10-05 客户现场调研记录，第3项"></textarea></label>
      <template v-else><label>分析版本 ID<input v-model.trim="createForm.analysisVersion" required placeholder="UUID"></label>
        <label>分析问题 ID<input v-model.trim="createForm.sourceItem" required placeholder="UUID"></label></template>
      <label>待办类型<select v-model="createForm.actionType"><option v-for="(label, value) in actionTypeLabels" :key="value" :value="value">{{ label }}</option></select></label>
      <label>标题<input v-model.trim="createForm.title" required maxlength="255" placeholder="一句话说明要解决的问题"></label>
      <label>负责人 ID<input v-model.trim="createForm.ownerRef" required placeholder="当前项目成员 UUID"></label>
      <div class="two"><label>截止时间<input v-model="createForm.dueAt" type="datetime-local" required></label>
        <label>优先级<select v-model="createForm.priority"><option v-for="(label, value) in priorityLabels" :key="value" :value="value">{{ label }}</option></select></label></div>
      <fieldset><legend>需要人工维护的字段</legend><div v-for="(field, index) in createFields" :key="index" class="field-row">
        <input v-model.trim="field.name" required maxlength="128" placeholder="字段名称"><input v-model.trim="field.format" required maxlength="128" placeholder="格式，如：文本/日期/单选">
        <input v-model.trim="field.example" required maxlength="500" placeholder="示例值"><label class="check"><input v-model="field.required" type="checkbox">必填</label>
        <button type="button" :disabled="createFields.length === 1" @click="removeField('create', index)">移除</button></div>
        <button type="button" :disabled="createFields.length >= 32" @click="addField('create')">增加字段</button></fieldset>
      <label>创建原因<textarea v-model="createForm.reason" required maxlength="2000" placeholder="说明为什么需要创建此待办"></textarea></label>
      <button type="submit" :disabled="mutationBusy">{{ mutationBusy ? '正在提交…' : '创建待办' }}</button>
    </form>
    <p v-if="mutationError" role="alert">{{ mutationError }}</p><p v-if="mutationMessage" role="status">{{ mutationMessage }}</p>
    <button v-if="pendingRetry" type="button" :disabled="mutationBusy" @click="attempt(pendingRetry)">使用原操作号和版本重试</button>
    <p v-if="loaded && !items.length">当前项目没有可见待办。</p>
    <ol v-if="items.length" aria-label="交接待办"><li v-for="item in items" :key="item.action_item_id">
      <strong>{{ item.title }}</strong><span>{{ stateLabels[item.action_state] }} · {{ priorityLabels[item.priority] }} · 截止 {{ new Date(item.due_at).toLocaleString('zh-CN') }}</span>
      <span>负责人：{{ item.owner_ref }}</span><button type="button" :disabled="detailBusy || mutationBusy" @click="show(item)">查看待办详情</button></li></ol>
    <button v-if="cursor" type="button" :disabled="busy || mutationBusy" @click="load(cursor)">加载更多待办</button>
    <p v-if="detailBusy" role="status">正在读取待办详情…</p><p v-if="detailError" role="alert">{{ detailError }}</p>
    <article v-if="detail" class="action-detail"><h2>{{ detail.title }}</h2><p><strong>当前状态：</strong>{{ stateLabels[detail.action_state] }}</p>
      <p v-if="detail.action_state === 'SUBMITTED'" class="status-warning">响应已经提交，但尚未验证和关闭。</p>
      <p v-if="detail.action_state === 'VERIFIED'" class="status-warning">响应已经验证，但尚未关闭，也未形成最终 Resolution Trace。</p>
      <p><strong>创建原因：</strong>{{ detail.created_reason }}</p><p v-if="detail.human_source_reason"><strong>人工来源：</strong>{{ detail.human_source_reason }}</p>
      <section><h3>需要维护的信息</h3><ul><li v-for="field in detail.requested_input_spec.fields" :key="field.name"><strong>{{ field.name }}</strong>
        · {{ field.required ? '必填' : '选填' }} · {{ field.format }} · 示例：{{ field.example }}</li></ul></section>
      <section><h3>响应文档</h3><p v-if="!detail.responses.length">尚未提交响应文档。</p><ul><li v-for="response in detail.responses" :key="response.document_version_id">
        固定版本 {{ response.document_version_id }} · <RouterLink :to="{ name: 'project-document-detail', params: { projectId: route.params.projectId,
          documentId: response.document_id } }">查看受权文档历史</RouterLink></li></ul></section>
      <section><h3>依据</h3><p v-if="!detail.evidence.length">尚无提交、验证或解决依据。</p><div class="evidence-actions">
        <button v-for="entry in detail.evidence" :key="entry.evidence_id" type="button" :disabled="locationBusy" @click="locate(entry.evidence_id)">
          定位{{ entry.purpose }}依据</button></div><p v-if="locationError" role="alert">{{ locationError }}</p>
        <div v-if="located" class="located"><strong>已核验位置：</strong>{{ located.display_label }}
          <a :href="located.content_url" target="_blank" rel="noopener noreferrer">打开固定版本</a></div></section>
      <p><strong>最新状态事件：</strong>{{ detail.current_event.from_state ?? '初始' }} → {{ detail.current_event.to_state }}；{{ detail.current_event.reason }}</p>
      <section v-if="mayPatch() || mayStart() || maySubmit() || mayVerify() || mayCancel() || detail.action_state === 'VERIFIED'" class="operations">
        <h3>待办操作</h3><p class="form-help">按钮只表示当前界面判断可尝试；服务器会重新检查角色、版本、证据与 License。</p>
        <div class="toolbar"><button v-if="mayPatch()" type="button" :disabled="mutationBusy" @click="beginPatch">修改待办信息</button>
          <button v-if="mayStart()" type="button" :disabled="mutationBusy" @click="beginOperation('start')">开始处理</button>
          <button v-if="maySubmit()" type="button" :disabled="mutationBusy" @click="beginOperation('submit')">提交响应</button>
          <button v-if="mayVerify()" type="button" :disabled="mutationBusy" @click="beginOperation('verify')">验证响应</button>
          <button v-if="mayCancel()" type="button" :disabled="mutationBusy" @click="beginOperation('cancel')">取消待办</button>
          <button v-if="detail.action_state === 'VERIFIED' && role() === 'PROJECT_MANAGER'" type="button" disabled>关闭待办（暂不可用）</button></div>
        <p v-if="detail.action_state === 'VERIFIED' && role() === 'PROJECT_MANAGER'" class="status-warning">当前生产组合尚未接入 Survey/Requirement Resolution Owner；为避免假关闭，关闭操作按 CR-HND-008 失败关闭。</p>
        <form v-if="operation === 'patch' && mayPatch()" class="write-panel" @submit.prevent="patchAction"><h4>修改待办信息</h4>
          <label>标题<input v-model.trim="patchForm.title" required maxlength="255"></label><label>负责人 ID<input v-model.trim="patchForm.ownerRef" required></label>
          <div class="two"><label>截止时间<input v-model="patchForm.dueAt" type="datetime-local" required></label><label>优先级<select v-model="patchForm.priority">
            <option v-for="(label, value) in priorityLabels" :key="value" :value="value">{{ label }}</option></select></label></div>
          <fieldset><legend>需要人工维护的字段</legend><div v-for="(field, index) in patchFields" :key="index" class="field-row">
            <input v-model.trim="field.name" required maxlength="128" placeholder="字段名称"><input v-model.trim="field.format" required maxlength="128" placeholder="格式">
            <input v-model.trim="field.example" required maxlength="500" placeholder="示例值"><label class="check"><input v-model="field.required" type="checkbox">必填</label>
            <button type="button" :disabled="patchFields.length === 1" @click="removeField('patch', index)">移除</button></div>
            <button type="button" :disabled="patchFields.length >= 32" @click="addField('patch')">增加字段</button></fieldset>
          <button type="submit" :disabled="mutationBusy">保存并重新读取</button></form>
        <form v-if="operation && operation !== 'patch'" class="write-panel" @submit.prevent="transition(operation)"><h4>{{ operation === 'start' ? '开始处理' : operation === 'submit' ? '提交响应' : operation === 'verify' ? '验证响应' : '取消待办' }}</h4>
          <label v-if="operation === 'submit'">响应文档与固定版本<textarea v-model="commandForm.documents" required placeholder="每行：文档 UUID, 固定版本 UUID"></textarea></label>
          <label v-if="operation === 'submit' || operation === 'verify'">Evidence ID<textarea v-model="commandForm.evidence" required placeholder="可用逗号、空格或换行分隔；必须属于当前响应文档"></textarea></label>
          <label>操作理由<textarea v-model="commandForm.reason" required maxlength="2000" placeholder="说明本次操作的可审计原因"></textarea></label>
          <button type="submit" :disabled="mutationBusy">{{ mutationBusy ? '正在提交…' : '确认操作' }}</button></form>
      </section>
    </article>
  </template></section></template>

<style scoped>
.action-workbench{max-width:62rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}.action-workbench ol{display:grid;gap:.7rem;padding:0;list-style:none}.action-workbench li{display:grid;gap:.35rem;padding:1rem;border:1px solid #d8dee7;border-radius:.7rem;overflow-wrap:anywhere}.action-detail{margin-top:1rem;padding:1rem;border:1px solid #aebfc8;border-radius:.8rem}.fact-warning,.status-warning{padding:.8rem;background:#fff8e9;border-left:.3rem solid #d29b42}.evidence-actions,.toolbar{display:flex;gap:.5rem;flex-wrap:wrap}.located{margin-top:.7rem;padding:.7rem;background:#eef7f1}.operations{margin-top:1rem;padding-top:1rem;border-top:1px solid #d8dee7}.write-panel{display:grid;gap:.75rem;margin:1rem 0;padding:1rem;background:#f7f9fb;border:1px solid #cbd5df;border-radius:.7rem}.write-panel label{display:grid;gap:.25rem}.write-panel input,.write-panel select,.write-panel textarea{box-sizing:border-box;width:100%;padding:.5rem}.write-panel textarea{min-height:5rem}.two,.field-row{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.5rem}.field-row{grid-template-columns:1fr 1fr 1.4fr auto auto;margin-bottom:.5rem}.field-row .check{display:flex;align-items:center;gap:.25rem}.field-row .check input{width:auto}.form-help{color:#52606d}.action-workbench [role=alert]{color:#a21d25}@media(max-width:48rem){.two,.field-row{grid-template-columns:1fr}}
</style>
