<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { SectionReadClient, SectionReadError, type SectionSummary } from "@/modules/solution/api/sectionReadClient";

const props = defineProps<{ session?: SessionClient; reader?: SectionReadClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const reader = toRaw(props.reader ?? new SectionReadClient());
const route = useRoute();
const items = ref<readonly SectionSummary[]>([]);
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
  const project = projectId(), run = ++generation;
  busy.value = true; error.value = "";
  if (replace) { items.value = []; cursor.value = null; loaded.value = false; }
  try {
    const page = await reader.list(project, 50, next);
    if (!mounted || run !== generation || project !== projectId()) return;
    const previous = items.value;
    if (page.items.some(item => previous.some(old => old.solution_section_id === item.solution_section_id)
      || previous.length > 0 && item.solution_section_id <= previous[previous.length - 1]!.solution_section_id)) {
      throw new SectionReadError("SECTION_UNAVAILABLE");
    }
    items.value = Object.freeze([...previous, ...page.items]);
    cursor.value = page.next_cursor; loaded.value = true;
  } catch (failure) {
    if (!mounted || run !== generation) return;
    items.value = []; cursor.value = null; loaded.value = false;
    error.value = failure instanceof Error ? failure.message : "暂时无法读取方案章节。";
  } finally { if (mounted && run === generation) busy.value = false; }
}
watch(() => route.params.projectId, () => {
  generation += 1; items.value = []; cursor.value = null; loaded.value = false; busy.value = false; error.value = "";
  void load(null, true);
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; });
</script>

<template>
  <section class="section-list" aria-labelledby="section-list-title" :aria-busy="busy">
    <p class="section-kicker">项目方案</p><h1 id="section-list-title">方案章节</h1>
    <p class="warning">这里列出整个项目的章节身份，不按单个目录筛选。章节存在或有批准版引用，不代表正文、评审与客户确认已经核实。</p>
    <p><RouterLink :to="{ name: 'project-outlines', params: { projectId: route.params.projectId } }">返回方案目录</RouterLink></p>
    <p v-if="!session.view" role="status">尚未读取当前身份，请先登录。</p>
    <p v-else-if="session.view.password_change_required" role="status">当前账户须先修改密码。</p>
    <template v-else>
      <button type="button" :disabled="busy || !mayRead()" @click="load(null, true)">{{ busy ? "正在读取…" : "刷新章节" }}</button>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="loaded && !items.length" role="status">当前项目没有可见方案章节。</p>
      <ol v-if="items.length" aria-label="项目方案章节"><li v-for="item in items" :key="item.solution_section_id">
        <strong>{{ item.section_key }}</strong><span>{{ item.section_state === "ARCHIVED" ? "已归档" : "活动中" }}</span>
        <span>{{ item.current_approved_version_ref ? "已记录批准版引用；正文仍需核查" : "尚无已审批版本" }}</span>
        <time :datetime="item.created_at">{{ new Date(item.created_at).toLocaleString("zh-CN") }}</time>
        <RouterLink :to="{ name: 'project-outline-detail', params: { projectId: item.project_id,
          outlineId: item.solution_outline_id } }">所属目录</RouterLink>
        <RouterLink :to="{ name: 'project-section-detail', params: { projectId: item.project_id,
          sectionId: item.solution_section_id } }">查看章节详情</RouterLink>
      </li></ol>
      <button v-if="cursor" type="button" :disabled="busy" @click="load(cursor)">加载更多章节</button>
    </template>
  </section>
</template>

<style scoped>
.section-list{max-width:60rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}.section-list ol{display:grid;gap:.8rem;padding:0;list-style:none}.section-list li{display:grid;gap:.35rem;padding:1rem;border:1px solid #d8dee7;border-radius:.75rem}.warning{padding:.8rem 1rem;border-left:.3rem solid #d29b42;background:#fff8e9}.section-list [role=alert]{color:#a21d25}
</style>
