<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { StructuredSpecReadClient, type StructuredSpecDetail } from
  "@/modules/solution/api/structuredSpecReadClient";
import { describeStructuredSpec, type SpecPresentation } from "./structuredSpecPresentation";

const props = defineProps<{ session?: SessionClient; reader?: StructuredSpecReadClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const reader = toRaw(props.reader ?? new StructuredSpecReadClient());
const route = useRoute();
const current = ref<StructuredSpecDetail | null>(null);
const presentation = ref<SpecPresentation | null>(null);
const busy = ref(false); const error = ref("");
let mounted = true; let generation = 0;
const projectId = () => typeof route.params.projectId === "string" ? route.params.projectId : "";
const specId = () => typeof route.params.specId === "string" ? route.params.specId : "";
function mayRead() {
  return mounted && !!session.view && !session.view.password_change_required
    && session.view.authorized_projects.some(item => item.project_id === projectId());
}
function stateLabel(value: string) {
  const labels: Record<string, string> = { DRAFT: "待评审草案", IN_REVIEW: "评审中",
    APPROVED: "已批准", RETURNED: "已退回", SUPERSEDED: "已被后续版本替代",
    RESTRICTED: "受限" };
  return labels[value] ?? "状态未知";
}
async function load() {
  if (!mayRead() || busy.value) return;
  const project = projectId(), spec = specId(), run = ++generation;
  busy.value = true; error.value = ""; current.value = null; presentation.value = null;
  try {
    const result = await reader.detail(project, spec);
    if (!mounted || run !== generation || project !== projectId() || spec !== specId()) return;
    const readable = describeStructuredSpec(result);
    current.value = result; presentation.value = readable;
  } catch (failure) {
    if (mounted && run === generation) error.value = failure instanceof Error
      ? failure.message : "暂时无法读取专项版本。";
  } finally { if (mounted && run === generation) busy.value = false; }
}
watch(() => [route.name, route.params.projectId, route.params.specId], () => {
  generation += 1; current.value = null; presentation.value = null;
  busy.value = false; error.value = "";
  if (route.name === "project-structured-spec-detail") void load();
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; });
</script>

<template>
  <section class="spec-detail" aria-labelledby="spec-detail-title" :aria-busy="busy">
    <p class="section-kicker">项目方案 · 固定历史</p>
    <h1 id="spec-detail-title">结构化专项详情</h1>
    <p><RouterLink :to="{ name: 'project-sections', params: { projectId: route.params.projectId } }">返回项目章节</RouterLink></p>
    <p v-if="!mayRead()" role="status">当前会话没有此项目的读取权限。</p>
    <template v-else>
      <button type="button" :disabled="busy" @click="load()">{{ busy ? "正在读取…" : "刷新详情" }}</button>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-else-if="busy" role="status">正在读取固定专项版本…</p>
      <template v-else-if="current && presentation">
        <p class="warning" role="status">{{ stateLabel(current.version_state) }}。固定历史引用不证明需求、章节或证据目前仍合格；只有实际完成评审的版本才可作为正式结论。</p>
        <h2>{{ presentation.title }} · 版本 {{ current.version_no }}</h2>
        <dl class="facts"><dt>系列编号</dt><dd>{{ current.spec_series_id }}</dd>
          <dt>版本编号</dt><dd>{{ current.structured_solution_spec_id }}</dd>
          <dt>创建时间</dt><dd>{{ current.created_at }}</dd>
          <dt>内容指纹</dt><dd>{{ current.content_fingerprint }}</dd></dl>
        <section aria-labelledby="spec-fields-title" v-if="presentation.fields.length">
          <h3 id="spec-fields-title">设计内容</h3>
          <dl class="facts"><template v-for="item in presentation.fields" :key="item.label">
            <dt>{{ item.label }}</dt><dd>{{ item.value }}</dd></template></dl>
        </section>
        <section v-for="list in presentation.lists" :key="list.label">
          <h3>{{ list.label }}</h3><p v-if="!list.items.length">无</p>
          <ul v-else><li v-for="(item, index) in list.items" :key="index">{{ item }}</li></ul>
        </section>
        <section v-for="table in presentation.tables" :key="table.label">
          <h3>{{ table.label }}</h3><p v-if="!table.rows.length">无</p>
          <div v-else class="table-scroll"><table><thead><tr><th v-for="heading in table.headings" :key="heading" scope="col">{{ heading }}</th></tr></thead>
            <tbody><tr v-for="(row, index) in table.rows" :key="index"><td v-for="(cell, cellIndex) in row" :key="cellIndex">{{ cell }}</td></tr></tbody></table></div>
        </section>
        <section aria-labelledby="spec-refs-title"><h3 id="spec-refs-title">固定来源引用</h3>
          <h4>需求版本（{{ current.requirement_refs.length }}）</h4>
          <ul><li v-for="item in current.requirement_refs" :key="item.requirement_version_id">
            <RouterLink :to="{ name: 'project-requirement-detail', params: {
              projectId: current.project_id, requirementId: item.requirement_id } }">查看需求</RouterLink>
            · 固定版本 {{ item.requirement_version_id }}</li></ul>
          <h4>章节版本（{{ current.section_refs.length }}）</h4>
          <ul><li v-for="item in current.section_refs" :key="item.solution_section_version_id">
            <RouterLink :to="{ name: 'project-section-version-detail', params: {
              projectId: current.project_id, sectionId: item.solution_section_id,
              versionId: item.solution_section_version_id } }">查看固定章节</RouterLink></li></ul>
          <h4>项目证据（{{ current.evidence_ids.length }}）</h4>
          <p v-if="!current.evidence_ids.length">无</p>
          <ul v-else><li v-for="item in current.evidence_ids" :key="item">{{ item }}</li></ul>
          <p><RouterLink :to="{ name: 'project-evidence', params: { projectId: current.project_id } }">查看项目证据列表</RouterLink></p>
        </section>
        <p v-if="current.review_ref">评审编号：{{ current.review_ref }}；轮次编号：{{ current.review_round_ref }}</p>
        <p v-else>尚无评审记录；本页不提供提交评审操作。</p>
      </template>
    </template>
  </section>
</template>

<style scoped>
.spec-detail{max-width:64rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}
.spec-detail section{margin-block:1.5rem}.spec-detail .facts{display:grid;grid-template-columns:minmax(8rem,12rem) 1fr;gap:.5rem 1rem}
.spec-detail dt{font-weight:650}.spec-detail dd{margin:0;overflow-wrap:anywhere;white-space:pre-wrap}
.spec-detail .warning{padding:.8rem 1rem;border-left:.3rem solid #d29b42;background:#fff8e9}
.spec-detail .table-scroll{overflow-x:auto}.spec-detail table{border-collapse:collapse;width:100%}
.spec-detail th,.spec-detail td{border:1px solid #aaa;padding:.5rem;text-align:left;vertical-align:top}
.spec-detail [role=alert]{color:#a21d25}
</style>
