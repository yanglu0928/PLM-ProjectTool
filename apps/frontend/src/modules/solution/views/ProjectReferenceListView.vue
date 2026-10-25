<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { ReferenceReadClient, ReferenceReadError, type ReferenceSummary } from "@/modules/solution/api/referenceReadClient";

const props = defineProps<{ session?: SessionClient; reader?: ReferenceReadClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const reader = toRaw(props.reader ?? new ReferenceReadClient());
const route = useRoute();
const items = ref<readonly ReferenceSummary[]>([]);
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
    if (page.items.some(item => previous.some(old => old.reference_solution_id === item.reference_solution_id)
      || previous.length > 0 && item.reference_solution_id <= previous[previous.length - 1]!.reference_solution_id)) {
      throw new ReferenceReadError("REFERENCE_UNAVAILABLE");
    }
    items.value = Object.freeze([...previous, ...page.items]); cursor.value = page.next_cursor; loaded.value = true;
  } catch (failure) {
    if (!mounted || current !== generation) return;
    items.value = []; cursor.value = null; loaded.value = false;
    error.value = failure instanceof Error ? failure.message : "暂时无法读取参考方案。";
  } finally { if (mounted && current === generation) busy.value = false; }
}
watch(() => route.params.projectId, () => {
  generation += 1; items.value = []; cursor.value = null; loaded.value = false; busy.value = false; error.value = "";
  void load(null, true);
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; });
const stateLabel = (state: ReferenceSummary["eligibility_state"]) => ({
  REFERENCE_ONLY: "仅供参考", ELIGIBLE: "已标记可用", RESTRICTED: "受限", REVOKED: "已撤销",
})[state];
</script>

<template>
  <section class="reference-list" aria-labelledby="reference-list-title" :aria-busy="busy">
    <p class="section-kicker">项目方案</p><h1 id="reference-list-title">参考方案候选</h1>
    <p class="warning">这里展示历史固定来源和当前标记，不代表来源仍可访问、适用或已由客户确认。打开详情后须重新核对原文与业务差异。</p>
    <p><RouterLink :to="{ name: 'project-detail', params: { projectId: route.params.projectId } }">返回项目详情</RouterLink></p>
    <p v-if="!session.view" role="status">尚未读取当前身份，请先登录。</p>
    <p v-else-if="session.view.password_change_required" role="status">当前账户须先修改密码。</p>
    <template v-else>
      <button type="button" :disabled="busy" @click="load(null, true)">{{ busy ? "正在读取…" : "刷新候选" }}</button>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="loaded && !items.length" role="status">当前项目没有可见参考方案。</p>
      <ol v-if="items.length" aria-label="项目参考方案候选"><li v-for="item in items" :key="item.reference_solution_id">
        <strong>{{ item.name }}</strong><span>{{ stateLabel(item.eligibility_state) }} · 草稿版本 {{ item.version_no }}</span>
        <time :datetime="item.created_at">{{ new Date(item.created_at).toLocaleString("zh-CN") }}</time>
        <RouterLink :to="{ name: 'project-reference-detail', params: { projectId: item.project_id,
          referenceId: item.reference_solution_id } }">查看固定来源与待核对信息</RouterLink>
      </li></ol>
      <button v-if="cursor" type="button" :disabled="busy" @click="load(cursor)">加载更多候选</button>
    </template>
  </section>
</template>

<style scoped>
.reference-list{max-width:60rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}.reference-list ol{display:grid;gap:.8rem;padding:0;list-style:none}.reference-list li{display:grid;gap:.35rem;padding:1rem;border:1px solid #d8dee7;border-radius:.75rem}.warning{padding:.8rem 1rem;border-left:.3rem solid #d29b42;background:#fff8e9}.reference-list [role=alert]{color:#a21d25}
</style>
