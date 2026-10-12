<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { SectionVersionReadClient, type SectionVersionDetail } from
  "@/modules/solution/api/sectionVersionReadClient";

const props = defineProps<{ session?: SessionClient; reader?: SectionVersionReadClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const reader = toRaw(props.reader ?? new SectionVersionReadClient());
const route = useRoute();
const current = ref<SectionVersionDetail | null>(null);
const busy = ref(false); const error = ref("");
let generation = 0; let mounted = true;
const projectId = () => typeof route.params.projectId === "string" ? route.params.projectId : "";
const sectionId = () => typeof route.params.sectionId === "string" ? route.params.sectionId : "";
const versionId = () => typeof route.params.versionId === "string" ? route.params.versionId : "";
function mayRead() {
  return mounted && !!session.view && !session.view.password_change_required
    && session.view.authorized_projects.some(item => item.project_id === projectId());
}
async function load() {
  if (!mayRead() || busy.value) return;
  const project = projectId(), section = sectionId(), version = versionId(), run = ++generation;
  busy.value = true; error.value = ""; current.value = null;
  try {
    const result = await reader.detail(project, section, version);
    if (!mounted || run !== generation || project !== projectId()
      || section !== sectionId() || version !== versionId()) return;
    current.value = result;
  } catch (failure) {
    if (mounted && run === generation) error.value = failure instanceof Error
      ? failure.message : "暂时无法读取章节版本。";
  } finally { if (mounted && run === generation) busy.value = false; }
}
watch(() => [route.params.projectId, route.params.sectionId, route.params.versionId], () => {
  generation += 1; current.value = null; busy.value = false; error.value = ""; void load();
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; });
</script>

<template>
  <section class="section-version-detail" aria-labelledby="section-version-detail-title" :aria-busy="busy">
    <p class="section-kicker">项目方案</p><h1 id="section-version-detail-title">章节固定版本详情</h1>
    <p class="warning">本页仅展示历史固定引用；Document、Requirement 和 Evidence 当前可用性需另行核查，评审及客户确认也不能由本页推定。</p>
    <p><RouterLink :to="{ name: 'project-section-versions', params: { projectId: route.params.projectId,
      sectionId: route.params.sectionId } }">返回版本历史</RouterLink></p>
    <p v-if="!session.view" role="status">尚未读取当前身份，请先登录。</p>
    <p v-else-if="session.view.password_change_required" role="status">当前账户须先修改密码。</p>
    <template v-else>
      <button type="button" :disabled="busy || !mayRead()" @click="load()">{{ busy ? "正在读取…" : "重新读取版本" }}</button>
      <p v-if="error" role="alert">{{ error }}</p>
      <template v-if="current">
        <h2>{{ current.title }} · 版本 {{ current.version_no }} · {{ current.version_state }}</h2>
        <dl><dt>固定正文来源</dt><dd v-if="current.content_document_version_ref">DocumentVersion <code>{{ current.content_document_version_ref }}</code></dd>
          <dd v-else>ArtifactRef <code>{{ current.content_artifact_ref }}</code></dd>
          <dt>固定内容摘要</dt><dd><code>{{ current.content_fingerprint }}</code></dd>
          <dt>前一版本</dt><dd>{{ current.supersedes_version_ref ?? "无" }}</dd>
          <dt>评审引用</dt><dd>{{ current.review_ref ?? "尚无" }}</dd>
          <dt>评审轮次引用</dt><dd>{{ current.review_round_ref ?? "尚无" }}</dd>
          <dt>创建时间</dt><dd><time :datetime="current.created_at">{{ new Date(current.created_at).toLocaleString("zh-CN") }}</time></dd></dl>
        <p>当前接口未提供来源文档的精确定位信息，不能从固定 UUID 推断下载地址或原文位置。</p>
        <h3>固定需求版本（{{ current.requirement_refs.length }}）</h3>
        <p v-if="!current.requirement_refs.length">无</p>
        <ol v-else><li v-for="item in current.requirement_refs" :key="item.requirement_version_id">
          <RouterLink :to="{ name: 'project-requirement-detail', params: { projectId: current.project_id,
            requirementId: item.requirement_id } }">需求 {{ item.requirement_id }}</RouterLink>
          · 固定版本 {{ item.requirement_version_id }}</li></ol>
        <h3>固定 Evidence（{{ current.evidence_ids.length }}）</h3>
        <p v-if="!current.evidence_ids.length">无</p>
        <ol v-else><li v-for="evidence in current.evidence_ids" :key="evidence"><code>{{ evidence }}</code></li></ol>
        <h3>假设声明（{{ current.assumptions.length }}）</h3>
        <p v-if="!current.assumptions.length">无</p>
        <ol v-else><li v-for="(item, index) in current.assumptions" :key="index"><pre>{{ JSON.stringify(item, null, 2) }}</pre></li></ol>
        <h3>排除声明（{{ current.exclusions.length }}）</h3>
        <p v-if="!current.exclusions.length">无</p>
        <ol v-else><li v-for="(item, index) in current.exclusions" :key="index"><pre>{{ JSON.stringify(item, null, 2) }}</pre></li></ol>
      </template>
    </template>
  </section>
</template>

<style scoped>
.section-version-detail{max-width:64rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}
.section-version-detail dl{display:grid;grid-template-columns:10rem 1fr;gap:.5rem}
.section-version-detail dd{margin:0;overflow-wrap:anywhere}
.section-version-detail pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f7fa;padding:.7rem}
.warning{padding:.8rem 1rem;border-left:.3rem solid #d29b42;background:#fff8e9}
.section-version-detail [role=alert]{color:#a21d25}
</style>
