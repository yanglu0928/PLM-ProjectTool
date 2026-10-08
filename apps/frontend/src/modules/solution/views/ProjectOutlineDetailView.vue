<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { OutlineReadClient, type OutlineCurrent } from "@/modules/solution/api/outlineReadClient";

const props = defineProps<{ session?: SessionClient; reader?: OutlineReadClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const reader = toRaw(props.reader ?? new OutlineReadClient());
const route = useRoute();
const current = ref<OutlineCurrent | null>(null); const busy = ref(false); const error = ref("");
let generation = 0; let mounted = true;
const projectId = () => typeof route.params.projectId === "string" ? route.params.projectId : "";
const outlineId = () => typeof route.params.outlineId === "string" ? route.params.outlineId : "";
function mayRead() {
  return mounted && !!session.view && !session.view.password_change_required
    && session.view.authorized_projects.some(item => item.project_id === projectId());
}
async function load() {
  if (!mayRead() || busy.value) return;
  const project = projectId(), outline = outlineId(), run = ++generation;
  busy.value = true; error.value = ""; current.value = null;
  try {
    const result = await reader.current(project, outline);
    if (!mounted || run !== generation || project !== projectId() || outline !== outlineId()) return;
    current.value = result;
  } catch (failure) {
    if (mounted && run === generation) error.value = failure instanceof Error
      ? failure.message : "暂时无法读取方案目录。";
  } finally { if (mounted && run === generation) busy.value = false; }
}
watch(() => [route.params.projectId, route.params.outlineId], () => {
  generation += 1; current.value = null; busy.value = false; error.value = "";
  void load();
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; });
</script>

<template>
  <section class="outline-detail" aria-labelledby="outline-detail-title" :aria-busy="busy">
    <p class="section-kicker">项目方案</p><h1 id="outline-detail-title">方案目录详情</h1>
    <p class="warning">此处仅显示目录身份及批准版引用状态，不展示方案正文、评审决定或客户签署；不得据此判断方案已交付。</p>
    <p><RouterLink :to="{ name: 'project-outlines', params: { projectId: route.params.projectId } }">返回方案目录</RouterLink></p>
    <p v-if="!session.view" role="status">尚未读取当前身份，请先登录。</p>
    <p v-else-if="session.view.password_change_required" role="status">当前账户须先修改密码。</p>
    <template v-else>
      <button type="button" :disabled="busy" @click="load()">{{ busy ? "正在读取…" : "重新读取目录" }}</button>
      <p v-if="error" role="alert">{{ error }}</p>
      <template v-if="current"><h2>{{ current.name }}</h2>
        <dl><dt>目录状态</dt><dd>{{ current.outline_state === "ARCHIVED" ? "已归档" : "活动中" }}</dd>
          <dt>批准版引用</dt><dd>{{ current.current_approved_version_ref ? "已记录；版本正文与评审需另行核查" : "尚无已审批版本" }}</dd>
          <dt>创建时间</dt><dd><time :datetime="current.created_at">{{ new Date(current.created_at).toLocaleString("zh-CN") }}</time></dd>
          <dt>并发版本</dt><dd>{{ current.etag }}</dd></dl>
      </template>
    </template>
  </section>
</template>

<style scoped>
.outline-detail{max-width:60rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}.outline-detail dl{display:grid;grid-template-columns:10rem 1fr;gap:.5rem}.outline-detail dd{margin:0;overflow-wrap:anywhere}.warning{padding:.8rem 1rem;border-left:.3rem solid #d29b42;background:#fff8e9}.outline-detail [role=alert]{color:#a21d25}
</style>
