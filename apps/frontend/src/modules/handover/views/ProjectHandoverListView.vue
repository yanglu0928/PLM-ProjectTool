<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { HandoverReadClient, HandoverReadError, type HandoverAnalysisCursor,
  type HandoverAnalysisView } from "@/modules/handover/api/handoverReadClient";

const props = defineProps<{ session?: SessionClient; handover?: HandoverReadClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const handover = toRaw(props.handover ?? new HandoverReadClient());
const identity = session.view; const route = useRoute();
const items = ref<readonly HandoverAnalysisView[]>([]);
const cursor = ref<HandoverAnalysisCursor | null>(null);
const loaded = ref(false); const busy = ref(false); const error = ref("");
let generation = 0; let mounted = true;
const stateLabels = Object.freeze({ ACTIVE: "进行中", ARCHIVED: "已归档", RESTRICTED: "受限" });

function mayRead() {
  return mounted && !!identity && !identity.password_change_required
    && session.view?.user.user_id === identity.user.user_id;
}
async function load(next: HandoverAnalysisCursor | null = null, replace = false) {
  if (!mayRead() || busy.value) return;
  const projectId = typeof route.params.projectId === "string" ? route.params.projectId : "";
  const current = ++generation; busy.value = true; error.value = "";
  if (replace) { items.value = []; cursor.value = null; loaded.value = false; }
  try {
    const page = await handover.listAnalyses(projectId, 50, next);
    if (!mounted || current !== generation || route.params.projectId !== projectId || !mayRead()) return;
    const known = new Set(items.value.map(item => item.handover_analysis_id));
    if (page.items.some(item => known.has(item.handover_analysis_id))) throw new HandoverReadError("HANDOVER_READ_UNAVAILABLE");
    items.value = Object.freeze([...items.value, ...page.items]); cursor.value = page.next_cursor; loaded.value = true;
  } catch (failure) {
    if (!mounted || current !== generation || route.params.projectId !== projectId) return;
    items.value = []; cursor.value = null; loaded.value = false;
    error.value = failure instanceof HandoverReadError ? failure.message : "暂时无法读取项目交接分析，请稍后重试。";
  } finally { if (mounted && current === generation) busy.value = false; }
}
watch(() => route.params.projectId, () => {
  generation += 1; items.value = []; cursor.value = null; loaded.value = false; error.value = ""; busy.value = false;
  void load(null, true);
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; });
</script>

<template>
  <section class="handover-list" aria-labelledby="handover-list-title" :aria-busy="busy">
    <p class="section-kicker">项目交接</p>
    <h1 id="handover-list-title">交接分析与待确认事项</h1>
    <p class="fact-warning"><strong>候选问题不等于已确认事实。</strong> 正式结论以指定版本的人工评审结果为准。</p>
    <p>列表不复制资料原文。进入分析后，可按问题逐项定位固定 Evidence，并查看需要人工维护的字段提示。</p>
    <p><RouterLink :to="{ name: 'project-detail', params: { projectId: route.params.projectId } }">返回项目详情</RouterLink></p>
    <template v-if="!identity">
      <p role="status">尚未读取当前身份。请先登录，或在账户页读取当前身份。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else-if="identity.password_change_required">
      <p role="status">当前账户须先修改密码，暂不能读取项目交接分析。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else>
      <button type="button" :disabled="busy" @click="load(null, true)">{{ busy ? "正在读取…" : "刷新交接分析" }}</button>
      <p v-if="busy" role="status">正在确认项目交接分析访问权限…</p>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="loaded && !items.length" role="status">当前项目没有可见的交接分析。</p>
      <ol v-if="items.length" aria-label="项目交接分析">
        <li v-for="item in items" :key="item.handover_analysis_id">
          <div class="analysis-heading"><strong>{{ item.analysis_purpose }}</strong><span>{{ stateLabels[item.state] }}</span></div>
          <span>更新时间：<time :datetime="item.updated_at">{{ new Date(item.updated_at).toLocaleString("zh-CN") }}</time></span>
          <span>正式版本：{{ item.current_approved_version_ref ?? "尚未形成" }}</span>
          <RouterLink :to="{ name: 'project-handover-detail', params: {
            projectId: item.project_id, analysisId: item.handover_analysis_id } }">查看版本、问题与原文位置</RouterLink>
        </li>
      </ol>
      <button v-if="cursor && loaded" type="button" :disabled="busy" @click="load(cursor)">加载更多交接分析</button>
    </template>
  </section>
</template>

<style scoped>
.handover-list { max-width: 54rem; margin: 1rem auto; padding: 1.5rem; background: #fff; border-radius: 1rem; }
.handover-list p { line-height: 1.65; }
.handover-list ol { display: grid; gap: .8rem; padding: 0; list-style: none; }
.handover-list li { display: grid; gap: .4rem; padding: 1rem; border: 1px solid #d8dee7; border-radius: .75rem; overflow-wrap: anywhere; }
.analysis-heading { display: flex; justify-content: space-between; gap: 1rem; }
.fact-warning { padding: .8rem 1rem; border-left: .3rem solid #d29b42; background: #fff8e9; }
.handover-list [role="alert"] { color: #a21d25; }
</style>
