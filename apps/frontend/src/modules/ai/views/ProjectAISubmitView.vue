<script setup lang="ts">
import { computed, inject, onUnmounted, reactive, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { AISubmissionClient, AISubmissionError, type AICreatedTask, type AIEgressAuthorizationView,
  type AIEgressPreviewView, type AISubmissionOptions, type AITaskParameterField } from "@/modules/ai/api/aiSubmissionClient";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { DocumentReadClient, DocumentReadError, type DocumentView } from "@/modules/document/api/documentReadClient";

const props = defineProps<{ session?: SessionClient; submission?: AISubmissionClient;
  documents?: DocumentReadClient; keyFactory?: () => string }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const submission = toRaw(props.submission ?? new AISubmissionClient(session));
const documents = toRaw(props.documents ?? new DocumentReadClient());
const newKey = props.keyFactory ?? (() => crypto.randomUUID());
const identity = session.view; const route = useRoute();
const options = ref<AISubmissionOptions | null>(null); const availableDocuments = ref<readonly DocumentView[]>([]);
const policyRef = ref(""); const egressRef = ref(""); const routeKey = ref("");
const selected = ref<string[]>([]); const parameters = reactive<Record<string, string | number | boolean>>({});
const preview = ref<AIEgressPreviewView | null>(null); const authorization = ref<AIEgressAuthorizationView | null>(null);
const created = ref<AICreatedTask | null>(null); const approvalChecked = ref(false); const busy = ref(false); const error = ref("");
const uncertainKey = ref(""); const keys = reactive({ preview: "", authorize: "", create: "", revoke: "" });
let generation = 0; let mounted = true;
const projectId = () => typeof route.params.projectId === "string" ? route.params.projectId : "";
const role = computed(() => identity?.authorized_projects.find(item => item.project_id === projectId())?.role ?? null);
const mayUse = computed(() => !!identity && !identity.password_change_required && session.canSubmit
  && session.view?.user.user_id === identity.user.user_id && ["PROJECT_MANAGER", "IMPLEMENTATION_MEMBER"].includes(role.value ?? ""));
const mayAuthorize = computed(() => role.value === "PROJECT_MANAGER");
const policy = computed(() => options.value?.task_policies.find(item => item.reference === policyRef.value) ?? null);
const egress = computed(() => options.value?.egress_policies.find(item => item.reference === egressRef.value) ?? null);
const selectedRoute = computed(() => options.value?.routes.find(item => `${item.provider_id}:${item.model_id}` === routeKey.value) ?? null);
function valueFor(field: AITaskParameterField): string | number | boolean { if (field.value_type === "BOOLEAN") return false;
  if (field.value_type === "INTEGER") return field.minimum ?? 0; return field.allowed_values[0] ?? ""; }
function selectPolicy() { for (const key of Object.keys(parameters)) delete parameters[key];
  for (const field of policy.value?.parameter_fields ?? []) parameters[field.name] = valueFor(field); }
function resetState() { preview.value = null; authorization.value = null; created.value = null; approvalChecked.value = false;
  error.value = ""; uncertainKey.value = ""; keys.preview = ""; keys.authorize = ""; keys.create = ""; keys.revoke = ""; }
function sourceRefs() { return availableDocuments.value.filter(item => selected.value.includes(item.document_id)).map(item => ({
  resource_type: "DOC-02" as const, resource_id: item.document_id,
  version_id: item.effective_version_ref ?? item.latest_version_ref!,
})); }
async function load() { if (!mounted || !mayUse.value || busy.value) return; const current = ++generation; const project = projectId();
  busy.value = true; error.value = ""; options.value = null; availableDocuments.value = []; resetState();
  try { const [choices, first] = await Promise.all([submission.options(project), documents.list({ kind: "PROJECT", projectId: project })]);
    let all = [...first.items]; let cursor = first.next_cursor; let pages = 1;
    while (cursor && pages < 20) { const page = await documents.list({ kind: "PROJECT", projectId: project }, cursor); all.push(...page.items); cursor = page.next_cursor; pages += 1; }
    if (cursor || new Set(all.map(item => item.document_id)).size !== all.length) throw new DocumentReadError("DOCUMENT_CLIENT_UNAVAILABLE");
    if (!mounted || current !== generation || projectId() !== project || !mayUse.value) return;
    options.value = choices; availableDocuments.value = Object.freeze(all.filter(item => item.state === "ACTIVE" && (item.effective_version_ref ?? item.latest_version_ref)));
    policyRef.value = choices.task_policies[0]?.reference ?? ""; egressRef.value = choices.egress_policies[0]?.reference ?? "";
    routeKey.value = choices.routes[0] ? `${choices.routes[0].provider_id}:${choices.routes[0].model_id}` : ""; selectPolicy();
  } catch (failure) { if (!mounted || current !== generation) return; error.value = failure instanceof Error ? failure.message : "暂时无法读取提交选项。"; }
  finally { if (mounted && current === generation) busy.value = false; }
}
async function makePreview() { if (!policy.value || !egress.value || !selectedRoute.value || !selected.value.length || busy.value) return;
  keys.preview ||= newKey(); busy.value = true; error.value = ""; uncertainKey.value = "";
  try { preview.value = await submission.createPreview(projectId(), { purpose_ref: policy.value.purpose_ref,
    provider_id: selectedRoute.value.provider_id, model_id: selectedRoute.value.model_id, source_refs: sourceRefs(),
    allowed_data_categories: egress.value.allowed_data_categories, minimal_payload_policy_ref: egress.value.reference,
    max_payload_bytes: egress.value.max_payload_bytes, max_input_tokens: egress.value.max_input_tokens,
    max_retry_attempts: egress.value.max_retry_attempts, ai_task_plan: { task_type: policy.value.task_type,
      prompt_policy_ref: policy.value.reference, output_schema_ref: policy.value.output_schema_ref,
      context_policy_ref: policy.value.context_policy_ref, task_parameters: { ...parameters } } }, keys.preview);
  } catch (failure) { error.value = failure instanceof Error ? failure.message : "外发预览失败。"; if (failure instanceof AISubmissionError && failure.uncertain) uncertainKey.value = keys.preview; }
  finally { busy.value = false; }
}
async function authorize() { if (!preview.value || !mayAuthorize.value || !approvalChecked.value || busy.value) return;
  keys.authorize ||= newKey(); busy.value = true; error.value = ""; uncertainKey.value = "";
  try { authorization.value = await submission.authorize(projectId(), preview.value, preview.value.expires_at, keys.authorize); }
  catch (failure) { error.value = failure instanceof Error ? failure.message : "授权失败。"; if (failure instanceof AISubmissionError && failure.uncertain) uncertainKey.value = keys.authorize; }
  finally { busy.value = false; }
}
async function createTask() { if (!authorization.value || !policy.value || busy.value) return; keys.create ||= newKey(); busy.value = true; error.value = ""; uncertainKey.value = "";
  try { created.value = await submission.createTask(projectId(), { task_type: policy.value.task_type, prompt_policy_ref: policy.value.reference,
    output_schema_ref: policy.value.output_schema_ref, context_policy_ref: policy.value.context_policy_ref,
    task_parameters: { ...parameters } }, sourceRefs(), authorization.value, keys.create); }
  catch (failure) { error.value = failure instanceof Error ? failure.message : "任务创建失败。"; if (failure instanceof AISubmissionError && failure.uncertain) uncertainKey.value = keys.create; }
  finally { busy.value = false; }
}
async function revoke() { if (!authorization.value || created.value || busy.value) return; keys.revoke ||= newKey(); busy.value = true; error.value = ""; uncertainKey.value = "";
  try { await submission.revoke(projectId(), authorization.value, "用户在创建AI任务前撤销本轮授权", keys.revoke); authorization.value = null; approvalChecked.value = false; }
  catch (failure) { error.value = failure instanceof Error ? failure.message : "撤销失败。"; if (failure instanceof AISubmissionError && failure.uncertain) uncertainKey.value = keys.revoke; }
  finally { busy.value = false; }
}
watch(() => route.params.projectId, () => { generation += 1; void load(); }, { immediate: true });
watch(policyRef, () => { if (!preview.value) selectPolicy(); }); onUnmounted(() => { mounted = false; generation += 1; });
</script>

<template>
  <section class="ai-submit" aria-labelledby="ai-submit-title" :aria-busy="busy">
    <p class="section-kicker">AI 分析工作台</p><h1 id="ai-submit-title">新建分析任务</h1>
    <p class="warning"><strong>这会把所选固定文档版本的最小必要内容发送到页面显示的外部区域。</strong> 预览、明确授权和创建任务是三个独立步骤，不会自动连续执行。</p>
    <p><RouterLink :to="{ name: 'project-ai-workbench', params: { projectId: route.params.projectId } }">返回AI工作台</RouterLink></p>
    <p v-if="!identity" role="status">请先登录并读取当前身份。</p>
    <p v-else-if="identity.password_change_required" role="status">当前账户须先修改密码。</p>
    <p v-else-if="!mayUse" role="status">当前角色不能创建AI任务。</p>
    <template v-else>
      <button type="button" :disabled="busy || !!preview" @click="load">刷新受控选项与文档</button>
      <p v-if="busy" role="status">正在处理当前步骤…</p><p v-if="error" role="alert">{{ error }}</p>
      <p v-if="uncertainKey" class="uncertain">结果待核对。请保留操作号 <code>{{ uncertainKey }}</code>，先检查任务/预览事实，不要直接更换操作号重试。</p>
      <template v-if="options && !created">
        <fieldset :disabled="busy || !!preview"><legend>1. 选择固定输入并生成外发预览</legend>
          <label>分析策略<select v-model="policyRef"><option v-for="item in options.task_policies" :key="item.reference" :value="item.reference">{{ item.task_type }} · {{ item.reference }}</option></select></label>
          <label>外发策略<select v-model="egressRef"><option v-for="item in options.egress_policies" :key="item.reference" :value="item.reference">{{ item.reference }}</option></select></label>
          <label>AI服务<select v-model="routeKey"><option v-for="item in options.routes" :key="`${item.provider_id}:${item.model_id}`" :value="`${item.provider_id}:${item.model_id}`">{{ item.provider_display_name }} / {{ item.provider_model_key }} · {{ item.data_region }}</option></select></label>
          <p v-if="!options.routes.length" role="status">没有同时通过当前状态和执行白名单的AI服务，提交入口已关闭。</p>
          <div v-for="field in policy?.parameter_fields ?? []" :key="field.name" class="parameter">
            <label v-if="field.value_type === 'STRING'">{{ field.name }}<select v-if="field.allowed_values.length" v-model="parameters[field.name]"><option v-for="value in field.allowed_values" :key="value" :value="value">{{ value }}</option></select><input v-else v-model.trim="parameters[field.name]" :required="field.required" :maxlength="field.max_length ?? 4096"></label>
            <label v-else-if="field.value_type === 'INTEGER'">{{ field.name }}<input v-model.number="parameters[field.name]" type="number" :min="field.minimum ?? undefined" :max="field.maximum ?? undefined" :required="field.required"></label>
            <label v-else><input v-model="parameters[field.name]" type="checkbox">{{ field.name }}</label>
          </div>
          <h2>固定文档版本</h2><p>只显示元数据；选择后锁定当前有效版本，不发送“最新版本”动态引用。</p>
          <label v-for="item in availableDocuments" :key="item.document_id" class="document-choice"><input v-model="selected" type="checkbox" :value="item.document_id">{{ item.title }} · {{ item.display_name }} · 版本 {{ item.effective_version_ref ?? item.latest_version_ref }}</label>
          <p v-if="!availableDocuments.length">没有可提交的有效固定文档版本。</p>
          <button type="button" :disabled="busy || !selected.length || !policy || !egress || !selectedRoute" @click="makePreview">生成外发预览（不会发送）</button>
        </fieldset>
        <section v-if="preview" class="preview" aria-label="外发预览"><h2>2. 核对并明确授权本轮外发</h2>
          <p>服务区域：{{ preview.data_region }} · 来源数：{{ preview.estimated_record_count }} · 上限：{{ preview.max_payload_bytes }} 字节 / {{ preview.max_input_tokens }} Token / {{ preview.max_retry_attempts }} 次尝试</p>
          <p>风险：{{ preview.risk_codes.join('、') }} · 预览到期：<time :datetime="preview.expires_at">{{ new Date(preview.expires_at).toLocaleString('zh-CN') }}</time></p>
          <ul><li v-for="source in preview.source_refs" :key="source.version_id">文档 {{ source.resource_id }} · 固定版本 {{ source.version_id }}</li></ul>
          <template v-if="!authorization"><label v-if="mayAuthorize" class="approval"><input v-model="approvalChecked" type="checkbox">我已核对以上服务区域、来源版本、数据范围和风险，明确同意仅本轮外发。</label>
            <p v-else role="status">当前角色可生成预览但不能批准外发；请由项目负责人完成本轮操作。</p>
            <button v-if="mayAuthorize" type="button" :disabled="busy || !approvalChecked" @click="authorize">明确授权本轮外发</button></template>
        </section>
        <section v-if="authorization" class="authorization" aria-label="外发授权"><h2>3. 创建AI任务</h2><p>授权 {{ authorization.authorization_id }} 有效至 {{ new Date(authorization.valid_until).toLocaleString('zh-CN') }}。创建任务后才会进入执行队列。</p>
          <button type="button" :disabled="busy" @click="createTask">创建AI任务</button><button type="button" :disabled="busy" @click="revoke">创建前撤销授权</button>
          <p>撤销只能阻止尚未开始的后续外发，不能撤回已发送的数据。</p></section>
      </template>
      <section v-if="created" class="created" aria-label="任务已创建"><h2>任务已创建</h2><p>AI任务 {{ created.ai_task_id }}；运行任务 {{ created.job_id }}。</p>
        <RouterLink :to="{ name: 'project-ai-task-detail', params: { projectId: route.params.projectId, taskId: created.ai_task_id } }">查看AI任务详情</RouterLink></section>
    </template>
  </section>
</template>

<style scoped>
.ai-submit { max-width: 62rem; margin: 1rem auto; padding: 1.5rem; background: #fff; border-radius: 1rem; }
.warning, .uncertain { padding: .8rem 1rem; border-left: .3rem solid #d29b42; background: #fff8e9; line-height: 1.65; }
fieldset, .preview, .authorization, .created { display: grid; gap: .8rem; margin-top: 1rem; padding: 1rem; border: 1px solid #d8dee7; border-radius: .8rem; }
label { display: grid; gap: .3rem; } .document-choice, .approval { grid-template-columns: auto 1fr; align-items: start; }
select, input { max-width: 100%; padding: .45rem; } button { width: fit-content; padding: .5rem .8rem; }
.ai-submit [role="alert"] { color: #a21d25; } code { overflow-wrap: anywhere; }
</style>
