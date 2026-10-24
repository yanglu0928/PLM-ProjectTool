<script setup lang="ts">
import { computed, inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";

import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { RAGRetrievalClient, RAGRetrievalError, type RAGContextView,
  type RAGRetrievalResult, type RAGRetrievalRun, type RAGSourceType } from "@/modules/rag/api/retrievalClient";

const props = defineProps<{ session?: SessionClient; retrievals?: RAGRetrievalClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const retrievals = toRaw(props.retrievals ?? new RAGRetrievalClient(session));
const identity = session.view;
const route = useRoute(); const router = useRouter();
const query = ref(""); const projectIndex = ref(""); const topK = ref(5);
const selectedSources = ref<RAGSourceType[]>([]); const confirmed = ref(false);
const run = ref<RAGRetrievalRun | null>(null); const result = ref<RAGRetrievalResult | null>(null);
const context = ref<RAGContextView | null>(null); const busy = ref(false); const error = ref("");
const createBlocked = ref(false); const uncertainKey = ref(""); const cancelReason = ref("");
const cancelConfirmed = ref(false); const cancelKey = ref(""); const cancelReceipt = ref("");
let mounted = true; let generation = 0;
const sourceOptions: readonly Readonly<{ value: RAGSourceType; label: string }>[] = Object.freeze([
  { value: "CONTRACTUAL", label: "合同/技术协议" }, { value: "PROJECT_RECORD", label: "项目记录" },
  { value: "STANDARD_CAPABILITY", label: "标准能力" }, { value: "REFERENCE_MATERIAL", label: "参考资料" },
  { value: "TEMPLATE", label: "模板" }, { value: "GENERATED_ARTIFACT", label: "生成成果" },
  { value: "OTHER", label: "其他" },
]);
const projectId = () => typeof route.params.projectId === "string" ? route.params.projectId : "";
const runId = () => typeof route.params.runId === "string" ? route.params.runId : "";
const role = computed(() => identity?.authorized_projects.find(item => item.project_id === projectId())?.role ?? "");
const mayRead = () => mounted && !!identity && !identity.password_change_required
  && session.view?.user.user_id === identity.user.user_id && !!role.value;
const mayCreate = computed(() => mayRead() && session.canSubmit
  && ["PROJECT_MANAGER", "IMPLEMENTATION_MEMBER", "CUSTOMER_MANAGER"].includes(role.value));
const mayCancel = computed(() => !!run.value && mayCreate.value
  && (run.value.requested_by === identity?.user.user_id || role.value === "PROJECT_MANAGER")
  && run.value.retrieval_state === "RUNNING" && !uncertainKey.value);
const stateLabel: Readonly<Record<RAGRetrievalRun["retrieval_state"], string>> = Object.freeze({
  RUNNING: "正在检索", SUCCEEDED: "已完成", FAILED: "失败", CANCELLED: "已取消",
});
function newKey() { return crypto.randomUUID(); }
function clearSensitiveInput() { query.value = ""; confirmed.value = false; }
function resetFacts() { run.value = null; result.value = null; context.value = null; cancelReceipt.value = ""; }
function locatorText(value: Readonly<Record<string, string | number | boolean | null>>) {
  return Object.entries(value).map(([key, item]) => `${key}=${String(item)}`).join(" · ");
}
async function load() {
  if (!mayRead() || busy.value || !runId()) return;
  const project = projectId(), target = runId(), current = ++generation;
  busy.value = true; error.value = ""; resetFacts();
  try {
    const currentRun = await retrievals.getRun(project, target);
    if (!mounted || current !== generation || projectId() !== project || runId() !== target || !mayRead()) return;
    run.value = currentRun;
    if (currentRun.retrieval_state === "SUCCEEDED") {
      const [retrievalResult, bundle] = await Promise.all([
        retrievals.getResult(project, target), retrievals.getContext(project, target),
      ]);
      if (!mounted || current !== generation || projectId() !== project || runId() !== target || !mayRead()) return;
      result.value = retrievalResult; context.value = bundle;
    }
  } catch (failure) {
    if (!mounted || current !== generation || projectId() !== project || runId() !== target) return;
    resetFacts(); error.value = failure instanceof RAGRetrievalError ? failure.message : "暂时无法读取检索状态。";
  } finally { if (mounted && current === generation) busy.value = false; }
}
async function create() {
  if (!mayCreate.value || busy.value || createBlocked.value || !confirmed.value) return;
  const project = projectId(), key = newKey(), current = ++generation;
  busy.value = true; error.value = ""; uncertainKey.value = ""; resetFacts();
  try {
    const created = await retrievals.create(project, { query: query.value, project_index_ref: projectIndex.value.trim(),
      top_k: topK.value, metadata_filter: selectedSources.value.length
        ? { source_type: Object.freeze([...selectedSources.value]) } : {} }, key);
    clearSensitiveInput();
    if (!mounted || current !== generation || projectId() !== project || !mayRead()) return;
    await router.replace({ name: "project-retrieval-detail", params: { projectId: project, runId: created.retrieval_run_id } });
  } catch (failure) {
    clearSensitiveInput();
    if (!mounted || current !== generation || projectId() !== project) return;
    if (failure instanceof RAGRetrievalError && !failure.uncertain) error.value = failure.message;
    else { createBlocked.value = true; uncertainKey.value = key;
      error.value = "检索创建结果无法确认。查询已从页面清除；请保留原操作号并核对项目任务，勿换号重试。"; }
  } finally { if (mounted && current === generation) busy.value = false; }
}
async function cancel() {
  const target = run.value;
  if (!target || !mayCancel.value || !cancelConfirmed.value || busy.value) return;
  const project = projectId(); const key = cancelKey.value || newKey(); cancelKey.value = key;
  const current = ++generation; busy.value = true; error.value = ""; cancelReceipt.value = "";
  try {
    const receipt = await retrievals.cancel(project, target, key, cancelReason.value);
    if (!mounted || current !== generation || projectId() !== project || runId() !== target.retrieval_run_id) return;
    resetFacts(); cancelReceipt.value = `${receipt.first_result.state} · ${receipt.first_result.etag}`;
    cancelKey.value = ""; cancelReason.value = ""; cancelConfirmed.value = false;
  } catch (failure) {
    if (!mounted || current !== generation || projectId() !== project || runId() !== target.retrieval_run_id) return;
    error.value = failure instanceof RAGRetrievalError && !failure.uncertain
      ? `${failure.message} 请重新读取当前状态。`
      : "取消结果无法确认；原操作号仍保留在本页。先刷新状态并核对审计，勿生成新操作号。";
  } finally { if (mounted && current === generation) busy.value = false; }
}
watch(() => [route.params.projectId, route.params.runId], () => {
  generation += 1; busy.value = false; error.value = ""; createBlocked.value = false; uncertainKey.value = "";
  clearSensitiveInput(); resetFacts(); cancelKey.value = ""; cancelReason.value = ""; cancelConfirmed.value = false;
  if (runId()) void load();
}, { immediate: true });
watch([query, projectIndex, topK, selectedSources], () => { confirmed.value = false; });
onUnmounted(() => { mounted = false; generation += 1; clearSensitiveInput(); });
</script>

<template>
  <section class="retrieval" aria-labelledby="retrieval-title" :aria-busy="busy">
    <p class="section-kicker">项目知识检索</p>
    <h1 id="retrieval-title">安全检索与最小上下文</h1>
    <p class="security-note"><strong>查询正文只用于本次提交。</strong> 不写入 URL、浏览器存储或页面操作号；结果只显示服务器当前授权的最小片段。</p>
    <p><RouterLink :to="{ name: 'project-detail', params: { projectId: route.params.projectId } }">返回项目详情</RouterLink></p>
    <template v-if="!identity"><p role="status">请先登录并读取当前身份。</p><RouterLink to="/login">前往账户与登录</RouterLink></template>
    <p v-else-if="identity.password_change_required" role="status">当前账户须先修改密码。</p>
    <p v-else-if="!role" role="status">当前账户没有此项目的访问权限。</p>
    <template v-else>
      <p v-if="busy" role="status">正在向服务器确认当前检索事实…</p>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="uncertainKey" class="warning">待核对操作号：<code>{{ uncertainKey }}</code>。本页已锁定新建入口。</p>
      <form v-if="!runId() && mayCreate" autocomplete="off" @submit.prevent="create">
        <h2>新建项目内 FTS 检索</h2>
        <p>首版仅查询当前项目的 ACTIVE 索引，不调用外部模型，不跨项目补齐候选。</p>
        <label>查询内容<textarea v-model="query" required maxlength="4096" :disabled="busy || createBlocked" spellcheck="false" /></label>
        <label>ACTIVE 项目索引 UUID<input v-model="projectIndex" required maxlength="36" :disabled="busy || createBlocked" autocomplete="off" /></label>
        <p class="hint">索引列表尚未开放到前端，请使用实施管理员提供且已激活的项目索引编号；服务器会再次核验项目归属和 ACTIVE 状态。</p>
        <label>最多返回条数<input v-model.number="topK" type="number" min="1" max="100" required :disabled="busy || createBlocked" /></label>
        <fieldset :disabled="busy || createBlocked"><legend>可选来源类型过滤</legend>
          <label v-for="option in sourceOptions" :key="option.value" class="choice"><input v-model="selectedSources" type="checkbox" :value="option.value">{{ option.label }}</label>
        </fieldset>
        <label class="confirm"><input v-model="confirmed" type="checkbox" :disabled="busy || createBlocked">我已核对项目、ACTIVE 索引、查询范围和返回条数</label>
        <button type="submit" :disabled="busy || createBlocked || !confirmed || !query.trim() || !projectIndex.trim()">提交检索</button>
      </form>
      <p v-else-if="!runId()" role="status">当前角色或登录状态不能创建检索。</p>

      <template v-if="runId()">
        <button type="button" :disabled="busy" @click="load">{{ busy ? "正在读取…" : "刷新检索状态" }}</button>
        <p v-if="cancelReceipt" role="status">取消首次回执：{{ cancelReceipt }}。这不是当前状态证明，请刷新。</p>
        <dl v-if="run" aria-label="当前授权检索状态">
          <dt>检索号</dt><dd>{{ run.retrieval_run_id }}</dd><dt>状态</dt><dd>{{ stateLabel[run.retrieval_state] }}</dd>
          <dt>项目索引</dt><dd>{{ run.project_index_ref }}</dd><dt>策略</dt><dd>{{ run.retrieval_policy_ref }} / {{ run.rerank_policy_ref }}</dd>
          <dt>返回上限</dt><dd>{{ run.top_k }}</dd><dt>质量标记</dt><dd>{{ run.quality_flags.length ? run.quality_flags.join('、') : '无' }}</dd>
          <dt>运行任务</dt><dd><RouterLink :to="{ name: 'project-job-detail', params: { projectId: run.project_id, jobId: run.job_id } }">{{ run.job_id }}</RouterLink></dd>
          <dt>创建时间</dt><dd><time :datetime="run.created_at">{{ new Date(run.created_at).toLocaleString('zh-CN') }}</time></dd>
          <template v-if="run.completed_at"><dt>完成时间</dt><dd><time :datetime="run.completed_at">{{ new Date(run.completed_at).toLocaleString('zh-CN') }}</time></dd></template>
          <template v-if="run.error_code"><dt>安全错误</dt><dd>{{ run.error_code }}</dd></template>
        </dl>
        <form v-if="mayCancel" @submit.prevent="cancel"><h2>申请取消当前检索</h2>
          <p>取消是协作请求；已发布的合法结果不会回滚。最终状态以重新读取为准。</p>
          <label>取消原因<textarea v-model="cancelReason" maxlength="1024" required :disabled="busy" /></label>
          <label class="confirm"><input v-model="cancelConfirmed" type="checkbox" :disabled="busy">我已核对检索号和当前版本 {{ run?.etag }}</label>
          <button type="submit" :disabled="busy || !cancelConfirmed || !cancelReason.trim()">提交取消请求</button>
        </form>
        <section v-if="result" aria-labelledby="retrieval-results"><h2 id="retrieval-results">授权检索结果</h2>
          <p>共 {{ result.candidates.length }} 条；分数为服务器可复算整数值，不代表人工确认结论。</p>
          <ol><li v-for="candidate in result.candidates" :key="candidate.candidate_id">
            <strong>#{{ candidate.rank + 1 }} · {{ candidate.source_type }} · {{ candidate.retrieval_channel }}</strong>
            <p>{{ candidate.snippet }}</p><p>文档版本：{{ candidate.document_version_ref }}</p>
            <p>定位：{{ locatorText(candidate.source_locator) }}</p><p>最终分数：{{ candidate.final_score_micros }}</p>
            <details><summary>查看分数分解</summary><ul><li v-for="part in candidate.score_parts" :key="`${part.score_kind}:${part.score_ordinal}`">{{ part.score_kind }}：{{ part.weighted_score_micros }}（{{ part.score_policy_ref }}）</li></ul></details>
          </li></ol>
        </section>
        <section v-if="context" aria-labelledby="retrieval-context"><h2 id="retrieval-context">最小上下文</h2>
          <p>策略 {{ context.context_policy_ref }} · {{ context.token_count }}/{{ context.token_budget }} Token。此处不显示内部指纹、向量、Golden 标签或人工答案。</p>
          <ol><li v-for="item in context.items" :key="item.chunk_id"><p>{{ item.snippet }}</p>
            <p>文档版本：{{ item.document_version_ref }} · 定位：{{ locatorText(item.source_locator) }}</p></li></ol>
        </section>
      </template>
    </template>
  </section>
</template>

<style scoped>
.retrieval { max-width: 62rem; margin: 1rem auto; padding: 1.5rem; background: #fff; border-radius: 1rem; }
.security-note, .warning { padding: .8rem 1rem; border-left: .3rem solid #d29b42; background: #fff8e9; line-height: 1.65; }
.retrieval form, .retrieval section { display: grid; gap: .75rem; margin-top: 1rem; }
.retrieval label { display: grid; gap: .35rem; } .retrieval .choice, .retrieval .confirm { grid-template-columns: auto 1fr; align-items: start; }
.retrieval textarea { min-height: 6rem; } .retrieval input, .retrieval textarea { max-width: 100%; padding: .45rem; }
.retrieval dl { display: grid; grid-template-columns: max-content minmax(0, 1fr); gap: .5rem 1rem; overflow-wrap: anywhere; }
.retrieval dt { font-weight: 700; } .retrieval dd { margin: 0; } .retrieval ol { display: grid; gap: .8rem; padding-left: 1.4rem; }
.retrieval li { padding: .8rem; border: 1px solid #d8dee7; border-radius: .7rem; overflow-wrap: anywhere; }
.retrieval [role="alert"] { color: #a21d25; } .hint { color: #5f6e66; } code { overflow-wrap: anywhere; }
</style>
