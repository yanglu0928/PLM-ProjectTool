<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { OutlineVersionReadClient, OutlineVersionReadError,
  type OutlineVersionSummary } from "@/modules/solution/api/outlineVersionReadClient";

const props = defineProps<{ session?: SessionClient; reader?: OutlineVersionReadClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const reader = toRaw(props.reader ?? new OutlineVersionReadClient());
const route = useRoute();
const items = ref<readonly OutlineVersionSummary[]>([]);
const cursor = ref<string | null>(null);
const busy = ref(false); const loaded = ref(false); const error = ref("");
let generation = 0; let mounted = true;
const projectId = () => typeof route.params.projectId === "string" ? route.params.projectId : "";
const outlineId = () => typeof route.params.outlineId === "string" ? route.params.outlineId : "";
function mayRead() {
  return mounted && !!session.view && !session.view.password_change_required
    && session.view.authorized_projects.some(item => item.project_id === projectId());
}
async function load(next: string | null = null, replace = false) {
  if (!mayRead() || busy.value) return;
  const project = projectId(), outline = outlineId(), run = ++generation;
  busy.value = true; error.value = "";
  if (replace) { items.value = []; cursor.value = null; loaded.value = false; }
  try {
    const page = await reader.list(project, outline, 50, next);
    if (!mounted || run !== generation || project !== projectId() || outline !== outlineId()) return;
    const previous = items.value;
    if (page.items.some(item => previous.some(old => old.solution_outline_version_id === item.solution_outline_version_id)
      || previous.length > 0 && item.version_no >= previous[previous.length - 1]!.version_no)) {
      throw new OutlineVersionReadError("OUTLINE_VERSION_UNAVAILABLE");
    }
    items.value = Object.freeze([...previous, ...page.items]);
    cursor.value = page.next_cursor; loaded.value = true;
  } catch (failure) {
    if (!mounted || run !== generation) return;
    items.value = []; cursor.value = null; loaded.value = false;
    error.value = failure instanceof Error ? failure.message : "暂时无法读取方案版本。";
  } finally { if (mounted && run === generation) busy.value = false; }
}
watch(() => [route.params.projectId, route.params.outlineId], () => {
  generation += 1; items.value = []; cursor.value = null; loaded.value = false;
  busy.value = false; error.value = ""; void load(null, true);
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; });
</script>

<template>
  <section class="outline-version-list" aria-labelledby="outline-version-list-title" :aria-busy="busy">
    <p class="section-kicker">项目方案</p><h1 id="outline-version-list-title">方案版本历史</h1>
    <p class="warning">仅显示创建时的历史快照与当前版本状态；历史引用不证明来源目前仍合格，也不代表方案已交付或客户已确认。</p>
    <p><RouterLink :to="{ name: 'project-outline-detail', params: { projectId: route.params.projectId,
      outlineId: route.params.outlineId } }">返回方案目录</RouterLink></p>
    <p v-if="!session.view" role="status">尚未读取当前身份，请先登录。</p>
    <p v-else-if="session.view.password_change_required" role="status">当前账户须先修改密码。</p>
    <template v-else>
      <button type="button" :disabled="busy || !mayRead()" @click="load(null, true)">{{ busy ? "正在读取…" : "刷新版本历史" }}</button>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="loaded && !items.length" role="status">此目录尚无可见方案版本。</p>
      <ol v-if="items.length" aria-label="方案版本历史"><li v-for="item in items" :key="item.solution_outline_version_id">
        <strong>版本 {{ item.version_no }} · {{ item.version_state }}</strong>
        <span>固定章节 {{ item.declared_section_count }} · 需求 {{ item.declared_requirement_count }} · 参考 {{ item.declared_reference_count }}</span>
        <span>缺失声明 {{ item.missing_declaration_count }} · 冲突声明 {{ item.conflict_declaration_count }}</span>
        <time :datetime="item.created_at">{{ new Date(item.created_at).toLocaleString("zh-CN") }}</time>
        <RouterLink :to="{ name: 'project-outline-version-detail', params: { projectId: item.project_id,
          outlineId: item.solution_outline_id, versionId: item.solution_outline_version_id } }">查看固定版本详情</RouterLink>
      </li></ol>
      <button v-if="cursor" type="button" :disabled="busy" @click="load(cursor)">加载更早版本</button>
    </template>
  </section>
</template>

<style scoped>
.outline-version-list{max-width:64rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}
.outline-version-list ol{display:grid;gap:.8rem;padding:0;list-style:none}
.outline-version-list li{display:grid;gap:.35rem;padding:1rem;border:1px solid #d8dee7;border-radius:.75rem}
.warning{padding:.8rem 1rem;border-left:.3rem solid #d29b42;background:#fff8e9}
.outline-version-list [role=alert]{color:#a21d25}
</style>
