<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { StructuredSpecListClient, StructuredSpecListError,
  type StructuredSpecSummary } from "@/modules/solution/api/structuredSpecListClient";

const props = defineProps<{ session?: SessionClient; reader?: StructuredSpecListClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const reader = toRaw(props.reader ?? new StructuredSpecListClient());
const route = useRoute();
const items = ref<readonly StructuredSpecSummary[]>([]);
const cursor = ref<string | null>(null);
const busy = ref(false); const loaded = ref(false); const error = ref("");
let generation = 0; let mounted = true;
const projectId = () => typeof route.params.projectId === "string" ? route.params.projectId : "";
function projectAccess() {
  return session.view?.authorized_projects.find(item => item.project_id === projectId()) ?? null;
}
function mayRead() {
  return mounted && !!session.view && !session.view.password_change_required && !!projectAccess();
}
function mayCreate() {
  const access = projectAccess();
  return mayRead() && session.canSubmit
    && (access?.role === "PROJECT_MANAGER" || access?.role === "IMPLEMENTATION_MEMBER");
}
function typeLabel(value: string) {
  const labels: Record<string, string> = { PROCESS_MODEL: "业务流程模型",
    INTERFACE_SPEC: "接口设计", MIGRATION_SPEC: "数据迁移设计",
    PERMISSION_DESIGN: "权限设计" };
  return labels[value] ?? "未知专项类型";
}
function stateLabel(value: string) {
  const labels: Record<string, string> = { DRAFT: "待评审草案", IN_REVIEW: "评审中",
    APPROVED: "已批准", RETURNED: "已退回", SUPERSEDED: "已被后续版本替代",
    RESTRICTED: "受限" };
  return labels[value] ?? "状态未知";
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
    if (page.items.some(item => previous.some(old => old.structured_solution_spec_id
        === item.structured_solution_spec_id)
      || previous.length > 0 && item.structured_solution_spec_id
        >= previous[previous.length - 1]!.structured_solution_spec_id)) {
      throw new StructuredSpecListError("STRUCTURED_SPEC_LIST_UNAVAILABLE");
    }
    items.value = Object.freeze([...previous, ...page.items]);
    cursor.value = page.next_cursor; loaded.value = true;
  } catch (failure) {
    if (!mounted || run !== generation) return;
    items.value = []; cursor.value = null; loaded.value = false;
    error.value = failure instanceof Error ? failure.message : "暂时无法读取专项历史。";
  } finally { if (mounted && run === generation) busy.value = false; }
}
watch(() => [route.name, route.params.projectId], () => {
  generation += 1; items.value = []; cursor.value = null; loaded.value = false;
  busy.value = false; error.value = "";
  if (route.name === "project-structured-specs") void load(null, true);
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; });
</script>

<template>
  <section class="spec-list" aria-labelledby="spec-list-title" :aria-busy="busy">
    <p class="section-kicker">项目方案 · 固定历史</p><h1 id="spec-list-title">结构化专项版本</h1>
    <p class="warning">这里只显示不可变版本摘要，不包含设计正文。DRAFT、历史引用或出现在列表中都不代表已经批准、仍然合格或客户已确认。</p>
    <p><RouterLink :to="{ name: 'project-detail', params: { projectId: route.params.projectId } }">返回项目详情</RouterLink></p>
    <p v-if="mayCreate()"><RouterLink :to="{ name: 'project-structured-spec-create', params: {
      projectId: route.params.projectId } }">创建结构化专项草案</RouterLink></p>
    <p v-if="!session.view" role="status">尚未读取当前身份，请先登录。</p>
    <p v-else-if="session.view.password_change_required" role="status">当前账户须先修改密码。</p>
    <p v-else-if="!mayRead()" role="status">当前会话没有此项目的读取权限。</p>
    <template v-else>
      <button type="button" :disabled="busy" @click="load(null, true)">{{ busy ? "正在读取…" : "刷新专项历史" }}</button>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="loaded && !items.length" role="status">此项目尚无可见的结构化专项版本。</p>
      <ol v-if="items.length" aria-label="结构化专项版本历史"><li v-for="item in items" :key="item.structured_solution_spec_id">
        <strong>{{ typeLabel(item.spec_type) }} · 版本 {{ item.version_no }} · {{ stateLabel(item.version_state) }}</strong>
        <span>系列编号 {{ item.spec_series_id }}</span>
        <span>固定版本编号 {{ item.structured_solution_spec_id }}</span>
        <span>{{ item.review_ref ? "已有评审记录" : "尚无评审记录" }}</span>
        <time :datetime="item.created_at">{{ new Date(item.created_at).toLocaleString("zh-CN") }}</time>
        <RouterLink :to="{ name: 'project-structured-spec-detail', params: { projectId: item.project_id,
          specId: item.structured_solution_spec_id } }">查看固定版本详情</RouterLink>
      </li></ol>
      <button v-if="cursor" type="button" :disabled="busy" @click="load(cursor)">加载更早版本</button>
    </template>
  </section>
</template>

<style scoped>
.spec-list{max-width:64rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}
.spec-list ol{display:grid;gap:.8rem;padding:0;list-style:none}
.spec-list li{display:grid;gap:.35rem;padding:1rem;border:1px solid #d8dee7;border-radius:.75rem}
.warning{padding:.8rem 1rem;border-left:.3rem solid #d29b42;background:#fff8e9}
.spec-list [role=alert]{color:#a21d25}
</style>
