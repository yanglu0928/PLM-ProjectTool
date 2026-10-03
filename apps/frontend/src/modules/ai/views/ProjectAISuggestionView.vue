<script setup lang="ts">
import { computed, inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { AIReadClient, AIReadError, type AIGapItemV1, type AIGapItemV2,
  type AISourceLocation, type AISuggestionView } from "@/modules/ai/api/aiReadClient";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";

const props = defineProps<{ session?: SessionClient; ai?: AIReadClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const ai = toRaw(props.ai ?? new AIReadClient());
const identity = session.view;
const route = useRoute();
const suggestion = ref<AISuggestionView | null>(null);
const busy = ref(false);
const error = ref("");
let generation = 0;
let mounted = true;

const categoryLabels = Object.freeze({ STANDARD_FUNCTION: "标准功能", NONSTANDARD_FUNCTION: "非标功能",
  DIFFERENCE: "差异项", PENDING_CONFIRMATION: "待确认项" });
const items = computed(() => suggestion.value?.payload.items ?? []);
function location(ordinal: number): AISourceLocation | null {
  return suggestion.value?.source_locations.find(item => item.source_ordinal === ordinal) ?? null;
}
function ordinals(item: AIGapItemV1 | AIGapItemV2): readonly number[] {
  return "source_ordinals" in item ? item.source_ordinals : item.source_citations.map(citation => citation.source_ordinal);
}
function nodeLabels(source: AISourceLocation, item: AIGapItemV1 | AIGapItemV2): readonly Readonly<Record<string, unknown>>[] {
  if (!("source_citations" in item)) return source.locations;
  const citation = item.source_citations.find(value => value.source_ordinal === source.source_ordinal);
  const nodes = new Set(citation?.node_ids ?? []);
  return source.locations.filter(value => typeof value.node_id === "string" && nodes.has(value.node_id));
}
function mayRead() {
  return mounted && !!identity && !identity.password_change_required
    && session.view?.user.user_id === identity.user.user_id;
}
function ids() {
  return { projectId: typeof route.params.projectId === "string" ? route.params.projectId : "",
    taskId: typeof route.params.taskId === "string" ? route.params.taskId : "" };
}
async function load() {
  if (!mayRead() || busy.value) return;
  const request = ids(); const current = ++generation;
  suggestion.value = null; error.value = ""; busy.value = true;
  try {
    const value = await ai.getSuggestion(request.projectId, request.taskId);
    const latest = ids();
    if (!mounted || current !== generation || latest.projectId !== request.projectId
        || latest.taskId !== request.taskId || !mayRead()) return;
    suggestion.value = value;
  } catch (failure) {
    const latest = ids();
    if (!mounted || current !== generation || latest.projectId !== request.projectId || latest.taskId !== request.taskId) return;
    suggestion.value = null;
    error.value = failure instanceof AIReadError ? failure.message : "暂时无法读取AI建议，请稍后重试。";
  } finally { if (mounted && current === generation) busy.value = false; }
}
watch(() => [route.params.projectId, route.params.taskId], () => {
  generation += 1; suggestion.value = null; error.value = ""; busy.value = false; void load();
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; });
</script>

<template>
  <section class="ai-suggestion" aria-labelledby="ai-suggestion-title" :aria-busy="busy">
    <p class="section-kicker">AI 分析工作台</p>
    <h1 id="ai-suggestion-title">建议、原文位置与待维护信息</h1>
    <p class="fact-warning"><strong>以下内容是AI建议，不是正式业务事实。</strong> 打开原文只用于核对；待维护字段尚未填写，也没有被系统自动确认。</p>
    <p><RouterLink :to="{ name: 'project-ai-task-detail', params: { projectId: route.params.projectId, taskId: route.params.taskId } }">返回AI任务详情</RouterLink></p>
    <template v-if="!identity">
      <p role="status">尚未读取当前身份。请先登录，或在账户页读取当前身份。</p><RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else-if="identity.password_change_required">
      <p role="status">当前账户须先修改密码，暂不能读取AI建议。</p><RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else>
      <button type="button" :disabled="busy" @click="load()">{{ busy ? "正在读取…" : "刷新建议" }}</button>
      <p v-if="busy" role="status">正在重新确认建议与原文访问权限…</p>
      <p v-if="error" role="alert">{{ error }}</p>
      <template v-if="suggestion">
        <p>建议状态：{{ suggestion.suggestion_state }} · {{ suggestion.fact_status }} · 版本 {{ suggestion.etag }}</p>
        <p v-if="suggestion.quality_flags.length">质量标记：{{ suggestion.quality_flags.join("、") }}</p>
        <article v-for="(item, index) in items" :key="`${item.category}:${index}`" class="suggestion-card">
          <p class="category">{{ categoryLabels[item.category] }}</p>
          <h2>{{ item.title }}</h2>
          <dl>
            <dt>分析摘要</dt><dd>{{ item.summary }}</dd>
            <dt>判断依据</dt><dd>{{ item.rationale }}</dd>
            <dt>建议</dt><dd>{{ item.recommendation }}</dd>
          </dl>
          <section class="source-block" aria-label="建议来源位置">
            <h3>核对原文</h3>
            <div v-for="ordinal in ordinals(item)" :key="ordinal" class="source-item">
              <template v-if="location(ordinal)">
                <p>来源 {{ ordinal }} · {{ location(ordinal)!.precision === 'PARSED_NODE' ? '精确解析位置' : '整个文档版本' }}</p>
                <ul>
                  <li v-for="(position, positionIndex) in nodeLabels(location(ordinal)!, item)" :key="positionIndex">
                    {{ position.display_label }}
                  </li>
                </ul>
                <a :href="location(ordinal)!.content_url" target="_blank" rel="noopener noreferrer"
                  :aria-label="`打开来源 ${ordinal} 的固定版本原文`">打开固定版本原文</a>
              </template>
            </div>
          </section>
          <section v-if="'confirmation' in item && item.confirmation.required" class="confirmation" aria-label="需要人工维护的信息">
            <h3>需要人工维护</h3>
            <p><strong>待确认问题：</strong>{{ item.confirmation.question }}</p>
            <ul>
              <li v-for="field in item.confirmation.required_fields" :key="field.key">
                <strong>{{ field.label }}{{ field.required ? '（必填）' : '（选填）' }}</strong>
                <span>填写提示：{{ field.prompt }}</span>
                <span>为什么需要：{{ field.reason }}</span>
              </li>
            </ul>
            <p>当前页面仅解释需要维护的内容；尚未写入任何项目草稿或正式版本。</p>
          </section>
          <p v-else class="confirmation-none">此项没有结构化人工补充字段；仍需结合原文进行人工判断。</p>
        </article>
      </template>
    </template>
  </section>
</template>

<style scoped>
.ai-suggestion { max-width: 60rem; margin: 1rem auto; padding: 1.5rem; background: #fff; border-radius: 1rem; }
.ai-suggestion p { line-height: 1.65; }
.fact-warning { padding: .8rem 1rem; border-left: .3rem solid #d29b42; background: #fff8e9; }
.suggestion-card { margin-top: 1rem; padding: 1.2rem; border: 1px solid #d8dee7; border-radius: .9rem; }
.suggestion-card dl { display: grid; grid-template-columns: minmax(6rem, auto) 1fr; gap: .65rem 1rem; }
.suggestion-card dt { font-weight: 700; }
.suggestion-card dd { margin: 0; overflow-wrap: anywhere; }
.category { color: #44715d; font-size: .82rem; font-weight: 750; letter-spacing: .08em; }
.source-block, .confirmation { margin-top: 1rem; padding: 1rem; border-radius: .7rem; background: #f3f7f4; }
.source-item + .source-item { border-top: 1px solid #d8dee7; }
.confirmation li { display: grid; gap: .25rem; margin-bottom: .7rem; }
.confirmation-none { color: #5f6e66; }
.ai-suggestion [role="alert"] { color: #a21d25; }
</style>
