<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { OutlineReadClient, OutlineReadError, type OutlineSummary } from "@/modules/solution/api/outlineReadClient";

const props = defineProps<{ session?: SessionClient; reader?: OutlineReadClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const reader = toRaw(props.reader ?? new OutlineReadClient());
const route = useRoute();
const items = ref<readonly OutlineSummary[]>([]);
const cursor = ref<string | null>(null);
const busy = ref(false); const loaded = ref(false); const error = ref("");
let generation = 0; let mounted = true;
const projectId = () => typeof route.params.projectId === "string" ? route.params.projectId : "";
function mayRead() {
  return mounted && !!session.view && !session.view.password_change_required
    && session.view.authorized_projects.some(item => item.project_id === projectId());
}
async function load(next: string | null = null, replace = false) {
  if (!mayRead() || busy.value) return;
  const project = projectId(), current = ++generation;
  busy.value = true; error.value = "";
  if (replace) { items.value = []; cursor.value = null; loaded.value = false; }
  try {
    const page = await reader.list(project, 50, next);
    if (!mounted || current !== generation || project !== projectId()) return;
    const previous = items.value;
    if (page.items.some(item => previous.some(old => old.solution_outline_id === item.solution_outline_id)
      || previous.length > 0 && item.solution_outline_id <= previous[previous.length - 1]!.solution_outline_id)) {
      throw new OutlineReadError("OUTLINE_UNAVAILABLE");
    }
    items.value = Object.freeze([...previous, ...page.items]);
    cursor.value = page.next_cursor; loaded.value = true;
  } catch (failure) {
    if (!mounted || current !== generation) return;
    items.value = []; cursor.value = null; loaded.value = false;
    error.value = failure instanceof Error ? failure.message : "暂时无法读取方案目录。";
  } finally { if (mounted && current === generation) busy.value = false; }
}
watch(() => route.params.projectId, () => {
  generation += 1; items.value = []; cursor.value = null; loaded.value = false; busy.value = false; error.value = "";
  void load(null, true);
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; });
</script>

<template>
  <section class="outline-list" aria-labelledby="outline-list-title" :aria-busy="busy">
    <p class="section-kicker">项目方案</p><h1 id="outline-list-title">方案目录</h1>
    <p class="warning">目录只是方案的逻辑身份。新建目录或显示在列表中，不代表方案内容、评审或客户确认已完成。</p>
    <p><RouterLink :to="{ name: 'project-detail', params: { projectId: route.params.projectId } }">返回项目详情</RouterLink></p>
    <p v-if="session.canSubmit && session.view?.authorized_projects.some(item => item.project_id === projectId()
      && (item.role === 'PROJECT_MANAGER' || item.role === 'IMPLEMENTATION_MEMBER'))">
      <RouterLink :to="{ name: 'project-outline-create', params: { projectId: route.params.projectId } }">创建方案目录</RouterLink>
    </p>
    <p v-if="!session.view" role="status">尚未读取当前身份，请先登录。</p>
    <p v-else-if="session.view.password_change_required" role="status">当前账户须先修改密码。</p>
    <template v-else>
      <button type="button" :disabled="busy" @click="load(null, true)">{{ busy ? "正在读取…" : "刷新目录" }}</button>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="loaded && !items.length" role="status">当前项目没有可见方案目录。</p>
      <ol v-if="items.length" aria-label="项目方案目录"><li v-for="item in items" :key="item.solution_outline_id">
        <strong>{{ item.name }}</strong><span>{{ item.outline_state === "ARCHIVED" ? "已归档" : "活动中" }}</span>
        <span>{{ item.current_approved_version_ref ? "已记录批准版引用；正文仍需核查" : "尚无已审批版本" }}</span>
        <time :datetime="item.created_at">{{ new Date(item.created_at).toLocaleString("zh-CN") }}</time>
        <RouterLink :to="{ name: 'project-outline-detail', params: { projectId: item.project_id,
          outlineId: item.solution_outline_id } }">查看目录详情</RouterLink>
      </li></ol>
      <button v-if="cursor" type="button" :disabled="busy" @click="load(cursor)">加载更多目录</button>
    </template>
  </section>
</template>

<style scoped>
.outline-list{max-width:60rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}.outline-list ol{display:grid;gap:.8rem;padding:0;list-style:none}.outline-list li{display:grid;gap:.35rem;padding:1rem;border:1px solid #d8dee7;border-radius:.75rem}.warning{padding:.8rem 1rem;border-left:.3rem solid #d29b42;background:#fff8e9}.outline-list [role=alert]{color:#a21d25}
</style>
