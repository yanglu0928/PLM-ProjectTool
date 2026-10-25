<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { SectionVersionReadClient, SectionVersionReadError,
  type SectionVersionSummary } from "@/modules/solution/api/sectionVersionReadClient";

const props = defineProps<{ session?: SessionClient; reader?: SectionVersionReadClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const reader = toRaw(props.reader ?? new SectionVersionReadClient());
const route = useRoute();
const items = ref<readonly SectionVersionSummary[]>([]);
const cursor = ref<string | null>(null);
const busy = ref(false); const loaded = ref(false); const error = ref("");
let generation = 0; let mounted = true;
const projectId = () => typeof route.params.projectId === "string" ? route.params.projectId : "";
const sectionId = () => typeof route.params.sectionId === "string" ? route.params.sectionId : "";
function mayRead() {
  return mounted && !!session.view && !session.view.password_change_required
    && session.view.authorized_projects.some(item => item.project_id === projectId());
}
async function load(next: string | null = null, replace = false) {
  if (!mayRead() || busy.value) return;
  const project = projectId(), section = sectionId(), run = ++generation;
  busy.value = true; error.value = "";
  if (replace) { items.value = []; cursor.value = null; loaded.value = false; }
  try {
    const page = await reader.list(project, section, 50, next);
    if (!mounted || run !== generation || project !== projectId() || section !== sectionId()) return;
    const previous = items.value;
    if (page.items.some(item => previous.some(old => old.solution_section_version_id === item.solution_section_version_id)
      || previous.length > 0 && item.version_no >= previous[previous.length - 1]!.version_no)) {
      throw new SectionVersionReadError("SECTION_VERSION_UNAVAILABLE");
    }
    items.value = Object.freeze([...previous, ...page.items]);
    cursor.value = page.next_cursor; loaded.value = true;
  } catch (failure) {
    if (!mounted || run !== generation) return;
    items.value = []; cursor.value = null; loaded.value = false;
    error.value = failure instanceof Error ? failure.message : "暂时无法读取章节版本。";
  } finally { if (mounted && run === generation) busy.value = false; }
}
watch(() => [route.params.projectId, route.params.sectionId], () => {
  generation += 1; items.value = []; cursor.value = null; loaded.value = false;
  busy.value = false; error.value = ""; void load(null, true);
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; });
</script>

<template>
  <section class="section-version-list" aria-labelledby="section-version-list-title" :aria-busy="busy">
    <p class="section-kicker">项目方案</p><h1 id="section-version-list-title">章节版本历史</h1>
    <p class="warning">仅显示创建时的固定引用及当前版本状态；历史来源不证明目前仍合格，也不代表方案已交付或客户已确认。</p>
    <p><RouterLink :to="{ name: 'project-section-detail', params: { projectId: route.params.projectId,
      sectionId: route.params.sectionId } }">返回章节</RouterLink></p>
    <p v-if="!session.view" role="status">尚未读取当前身份，请先登录。</p>
    <p v-else-if="session.view.password_change_required" role="status">当前账户须先修改密码。</p>
    <template v-else>
      <button type="button" :disabled="busy || !mayRead()" @click="load(null, true)">{{ busy ? "正在读取…" : "刷新版本历史" }}</button>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="loaded && !items.length" role="status">此章节尚无可见版本。</p>
      <ol v-if="items.length" aria-label="章节版本历史"><li v-for="item in items" :key="item.solution_section_version_id">
        <strong>版本 {{ item.version_no }} · {{ item.version_state }} · {{ item.title }}</strong>
        <span>固定需求 {{ item.declared_requirement_count }} · Evidence {{ item.declared_evidence_count }}</span>
        <span>假设 {{ item.assumption_count }} · 排除 {{ item.exclusion_count }}</span>
        <time :datetime="item.created_at">{{ new Date(item.created_at).toLocaleString("zh-CN") }}</time>
        <RouterLink :to="{ name: 'project-section-version-detail', params: { projectId: item.project_id,
          sectionId: item.solution_section_id, versionId: item.solution_section_version_id } }">查看固定版本详情</RouterLink>
      </li></ol>
      <button v-if="cursor" type="button" :disabled="busy" @click="load(cursor)">加载更早版本</button>
    </template>
  </section>
</template>

<style scoped>
.section-version-list{max-width:64rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}
.section-version-list ol{display:grid;gap:.8rem;padding:0;list-style:none}
.section-version-list li{display:grid;gap:.35rem;padding:1rem;border:1px solid #d8dee7;border-radius:.75rem}
.warning{padding:.8rem 1rem;border-left:.3rem solid #d29b42;background:#fff8e9}
.section-version-list [role=alert]{color:#a21d25}
</style>
