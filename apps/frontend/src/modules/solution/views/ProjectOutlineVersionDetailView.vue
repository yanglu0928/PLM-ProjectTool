<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { OutlineVersionReadClient, type OutlineVersionDetail } from
  "@/modules/solution/api/outlineVersionReadClient";

const props = defineProps<{ session?: SessionClient; reader?: OutlineVersionReadClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const reader = toRaw(props.reader ?? new OutlineVersionReadClient());
const route = useRoute();
const current = ref<OutlineVersionDetail | null>(null);
const busy = ref(false); const error = ref("");
let generation = 0; let mounted = true;
const projectId = () => typeof route.params.projectId === "string" ? route.params.projectId : "";
const outlineId = () => typeof route.params.outlineId === "string" ? route.params.outlineId : "";
const versionId = () => typeof route.params.versionId === "string" ? route.params.versionId : "";
function mayRead() {
  return mounted && !!session.view && !session.view.password_change_required
    && session.view.authorized_projects.some(item => item.project_id === projectId());
}
async function load() {
  if (!mayRead() || busy.value) return;
  const project = projectId(), outline = outlineId(), version = versionId(), run = ++generation;
  busy.value = true; error.value = ""; current.value = null;
  try {
    const result = await reader.detail(project, outline, version);
    if (!mounted || run !== generation || project !== projectId()
      || outline !== outlineId() || version !== versionId()) return;
    current.value = result;
  } catch (failure) {
    if (mounted && run === generation) error.value = failure instanceof Error
      ? failure.message : "暂时无法读取方案版本。";
  } finally { if (mounted && run === generation) busy.value = false; }
}
watch(() => [route.params.projectId, route.params.outlineId, route.params.versionId], () => {
  generation += 1; current.value = null; busy.value = false; error.value = ""; void load();
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; });
</script>

<template>
  <section class="outline-version-detail" aria-labelledby="outline-version-detail-title" :aria-busy="busy">
    <p class="section-kicker">项目方案</p><h1 id="outline-version-detail-title">方案固定版本详情</h1>
    <p class="warning">本页是历史固定引用，不证明关联章节、需求或参考方案目前仍有效；评审、批准和客户确认必须另行核查。</p>
    <p><RouterLink :to="{ name: 'project-outline-versions', params: { projectId: route.params.projectId,
      outlineId: route.params.outlineId } }">返回版本历史</RouterLink></p>
    <p v-if="!session.view" role="status">尚未读取当前身份，请先登录。</p>
    <p v-else-if="session.view.password_change_required" role="status">当前账户须先修改密码。</p>
    <template v-else>
      <button type="button" :disabled="busy || !mayRead()" @click="load()">{{ busy ? "正在读取…" : "重新读取版本" }}</button>
      <p v-if="error" role="alert">{{ error }}</p>
      <template v-if="current">
        <h2>版本 {{ current.version_no }} · {{ current.version_state }}</h2>
        <dl><dt>固定内容摘要</dt><dd><code>{{ current.content_fingerprint }}</code></dd>
          <dt>前一版本</dt><dd>{{ current.supersedes_version_ref ?? "无" }}</dd>
          <dt>评审引用</dt><dd>{{ current.review_ref ?? "尚无" }}</dd>
          <dt>评审轮次引用</dt><dd>{{ current.review_round_ref ?? "尚无" }}</dd>
          <dt>创建时间</dt><dd><time :datetime="current.created_at">{{ new Date(current.created_at).toLocaleString("zh-CN") }}</time></dd></dl>
        <h3>固定章节（{{ current.section_ids.length }}）</h3>
        <ol><li v-for="section in current.section_ids" :key="section">
          <RouterLink :to="{ name: 'project-section-detail', params: { projectId: current.project_id,
            sectionId: section } }">{{ section }}</RouterLink></li></ol>
        <h3>固定需求版本（{{ current.requirement_refs.length }}）</h3>
        <p v-if="!current.requirement_refs.length">无</p>
        <ol v-else><li v-for="item in current.requirement_refs" :key="item.requirement_version_id">
          <RouterLink :to="{ name: 'project-requirement-detail', params: { projectId: current.project_id,
            requirementId: item.requirement_id } }">需求 {{ item.requirement_id }}</RouterLink>
          · 固定版本 {{ item.requirement_version_id }}</li></ol>
        <h3>固定参考版本（{{ current.reference_refs.length }}）</h3>
        <p v-if="!current.reference_refs.length">无</p>
        <ol v-else><li v-for="item in current.reference_refs" :key="item.reference_version_id">
          <template v-if="item.scope === 'PROJECT'"><RouterLink :to="{ name: 'project-reference-detail',
            params: { projectId: current.project_id, referenceId: item.reference_solution_id } }">本项目参考 {{ item.reference_solution_id }}</RouterLink></template>
          <template v-else>GLOBAL 固定参考 {{ item.reference_solution_id }}（当前可用性未验证）</template>
          · 固定版本 {{ item.reference_version_id }}</li></ol>
        <h3>缺失声明（{{ current.missing_declarations.length }}）</h3>
        <p v-if="!current.missing_declarations.length">无</p>
        <ol v-else><li v-for="(item, index) in current.missing_declarations" :key="index"><pre>{{ JSON.stringify(item, null, 2) }}</pre></li></ol>
        <h3>冲突声明（{{ current.conflict_declarations.length }}）</h3>
        <p v-if="!current.conflict_declarations.length">无</p>
        <ol v-else><li v-for="(item, index) in current.conflict_declarations" :key="index"><pre>{{ JSON.stringify(item, null, 2) }}</pre></li></ol>
      </template>
    </template>
  </section>
</template>

<style scoped>
.outline-version-detail{max-width:64rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}
.outline-version-detail dl{display:grid;grid-template-columns:10rem 1fr;gap:.5rem}
.outline-version-detail dd{margin:0;overflow-wrap:anywhere}
.outline-version-detail pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f7fa;padding:.7rem}
.warning{padding:.8rem 1rem;border-left:.3rem solid #d29b42;background:#fff8e9}
.outline-version-detail [role=alert]{color:#a21d25}
</style>
