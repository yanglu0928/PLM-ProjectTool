<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { SectionReadClient, type SectionCurrent } from "@/modules/solution/api/sectionReadClient";

const props = defineProps<{ session?: SessionClient; reader?: SectionReadClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const reader = toRaw(props.reader ?? new SectionReadClient());
const route = useRoute();
const current = ref<SectionCurrent | null>(null); const busy = ref(false); const error = ref("");
let generation = 0; let mounted = true;
const projectId = () => typeof route.params.projectId === "string" ? route.params.projectId : "";
const sectionId = () => typeof route.params.sectionId === "string" ? route.params.sectionId : "";
function mayRead() {
  return mounted && !!session.view && !session.view.password_change_required
    && session.view.authorized_projects.some(item => item.project_id === projectId());
}
async function load() {
  if (!mayRead() || busy.value) return;
  const project = projectId(), section = sectionId(), run = ++generation;
  busy.value = true; error.value = ""; current.value = null;
  try {
    const result = await reader.current(project, section);
    if (!mounted || run !== generation || project !== projectId() || section !== sectionId()) return;
    current.value = result;
  } catch (failure) {
    if (mounted && run === generation) error.value = failure instanceof Error
      ? failure.message : "暂时无法读取方案章节。";
  } finally { if (mounted && run === generation) busy.value = false; }
}
watch(() => [route.params.projectId, route.params.sectionId], () => {
  generation += 1; current.value = null; busy.value = false; error.value = "";
  void load();
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; });
</script>

<template>
  <section class="section-detail" aria-labelledby="section-detail-title" :aria-busy="busy">
    <p class="section-kicker">项目方案</p><h1 id="section-detail-title">方案章节详情</h1>
    <p class="warning">此处只显示章节身份及批准版引用状态，不展示正文、评审决定或客户签署；不得据此判断方案已交付。</p>
    <p><RouterLink :to="{ name: 'project-sections', params: { projectId: route.params.projectId } }">返回方案章节</RouterLink></p>
    <p v-if="!session.view" role="status">尚未读取当前身份，请先登录。</p>
    <p v-else-if="session.view.password_change_required" role="status">当前账户须先修改密码。</p>
    <template v-else>
      <button type="button" :disabled="busy || !mayRead()" @click="load()">{{ busy ? "正在读取…" : "重新读取章节" }}</button>
      <p v-if="error" role="alert">{{ error }}</p>
      <template v-if="current"><h2>{{ current.section_key }}</h2>
        <dl><dt>所属目录</dt><dd><RouterLink :to="{ name: 'project-outline-detail', params: {
          projectId: current.project_id, outlineId: current.solution_outline_id } }">查看目录身份</RouterLink></dd>
          <dt>章节状态</dt><dd>{{ current.section_state === "ARCHIVED" ? "已归档" : "活动中" }}</dd>
          <dt>批准版引用</dt><dd>{{ current.current_approved_version_ref ? "已记录；版本正文与评审需另行核查" : "尚无已审批版本" }}</dd>
          <dt>创建时间</dt><dd><time :datetime="current.created_at">{{ new Date(current.created_at).toLocaleString("zh-CN") }}</time></dd>
          <dt>并发版本</dt><dd>{{ current.etag }}</dd></dl>
      </template>
    </template>
  </section>
</template>

<style scoped>
.section-detail{max-width:60rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}.section-detail dl{display:grid;grid-template-columns:10rem 1fr;gap:.5rem}.section-detail dd{margin:0;overflow-wrap:anywhere}.warning{padding:.8rem 1rem;border-left:.3rem solid #d29b42;background:#fff8e9}.section-detail [role=alert]{color:#a21d25}
</style>
