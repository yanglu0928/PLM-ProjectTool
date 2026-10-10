<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { RequirementReadClient, RequirementReadError, type RequirementCursor,
  type RequirementView } from "@/modules/requirement/api/requirementReadClient";

const props = defineProps<{ session?: SessionClient; requirements?: RequirementReadClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const requirements = toRaw(props.requirements ?? new RequirementReadClient());
const identity = session.view; const route = useRoute();
const items = ref<readonly RequirementView[]>([]); const cursor = ref<RequirementCursor | null>(null);
const loaded = ref(false); const busy = ref(false); const error = ref("");
let generation = 0; let mounted = true;
const stateLabels = Object.freeze({ ACTIVE: "有效", DEFERRED: "已延期", REJECTED: "已拒绝", ARCHIVED: "已归档" });

function mayRead() { return mounted && !!identity && !identity.password_change_required
  && session.view?.user.user_id === identity.user.user_id; }
async function load(next: RequirementCursor | null = null, replace = false) {
  if (!mayRead() || busy.value) return;
  const projectId = typeof route.params.projectId === "string" ? route.params.projectId : "";
  const current = ++generation; busy.value = true; error.value = "";
  if (replace) { items.value = []; cursor.value = null; loaded.value = false; }
  try {
    const page = await requirements.listRequirements(projectId, 50, next);
    if (!mounted || current !== generation || route.params.projectId !== projectId || !mayRead()) return;
    const known = new Set(items.value.map(item => item.requirement_id));
    if (page.items.some(item => known.has(item.requirement_id))) throw new RequirementReadError("REQUIREMENT_READ_UNAVAILABLE");
    items.value = Object.freeze([...items.value, ...page.items]); cursor.value = page.next_cursor; loaded.value = true;
  } catch (failure) {
    if (!mounted || current !== generation || route.params.projectId !== projectId) return;
    items.value = []; cursor.value = null; loaded.value = false;
    error.value = failure instanceof RequirementReadError ? failure.message : "暂时无法读取项目需求，请稍后重试。";
  } finally { if (mounted && current === generation) busy.value = false; }
}
watch(() => route.params.projectId, () => {
  generation += 1; items.value = []; cursor.value = null; loaded.value = false; error.value = ""; busy.value = false;
  void load(null, true);
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; });
</script>

<template>
  <section class="requirement-list" aria-labelledby="requirement-list-title" :aria-busy="busy">
    <p class="section-kicker">项目需求</p><h1 id="requirement-list-title">需求与固定版本</h1>
    <p class="fact-warning"><strong>AI 建议和来源摘要不是已确认业务事实。</strong>正式结论以人工确认的固定版本和原始证据为准。</p>
    <p>列表不复制资料原文。进入需求后，须由用户点击证据入口，服务器才会重新核验权限并定位原文。</p>
    <p><RouterLink :to="{ name: 'project-detail', params: { projectId: route.params.projectId } }">返回项目详情</RouterLink></p>
    <template v-if="!identity"><p role="status">尚未读取当前身份。请先登录。</p><RouterLink to="/login">前往账户与登录</RouterLink></template>
    <template v-else-if="identity.password_change_required"><p role="status">当前账户须先修改密码，暂不能读取项目需求。</p></template>
    <template v-else>
      <button type="button" :disabled="busy" @click="load(null, true)">{{ busy ? "正在读取…" : "刷新需求" }}</button>
      <p v-if="error" role="alert">{{ error }}</p><p v-if="loaded && !items.length" role="status">当前项目没有可见需求。</p>
      <ol v-if="items.length" aria-label="项目需求">
        <li v-for="item in items" :key="item.requirement_id">
          <div class="heading"><strong>{{ item.requirement_code }}</strong><span>{{ stateLabels[item.state] }}</span></div>
          <span>更新时间：<time :datetime="item.updated_at">{{ new Date(item.updated_at).toLocaleString("zh-CN") }}</time></span>
          <span>当前批准版本：{{ item.current_approved_version_ref ? "已形成" : "尚未形成" }}</span>
          <RouterLink :to="{ name: 'project-requirement-detail', params: { projectId: item.project_id,
            requirementId: item.requirement_id } }">查看版本、待维护内容与原文入口</RouterLink>
        </li>
      </ol>
      <button v-if="cursor && loaded" type="button" :disabled="busy" @click="load(cursor)">加载更多需求</button>
    </template>
  </section>
</template>

<style scoped>
.requirement-list { max-width: 54rem; margin: 1rem auto; padding: 1.5rem; background: #fff; border-radius: 1rem; }
.requirement-list p { line-height: 1.65; }.requirement-list ol { display: grid; gap: .8rem; padding: 0; list-style: none; }
.requirement-list li { display: grid; gap: .4rem; padding: 1rem; border: 1px solid #d8dee7; border-radius: .75rem; overflow-wrap: anywhere; }
.heading { display: flex; justify-content: space-between; gap: 1rem; }.fact-warning { padding: .8rem 1rem; border-left: .3rem solid #d29b42; background: #fff8e9; }
.requirement-list [role="alert"] { color: #a21d25; }
</style>
