<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { ProjectReadClient, ProjectReadError, type ProjectView } from "@/modules/project/api/projectReadClient";

const props = defineProps<{ session?: SessionClient; projects?: ProjectReadClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const projects = toRaw(props.projects ?? new ProjectReadClient());
const identity = session.view;
const route = useRoute();
const project = ref<ProjectView | null>(null);
const busy = ref(false);
const error = ref("");
let generation = 0;

watch(() => route.params.projectId, async (value) => {
  const current = ++generation;
  project.value = null;
  error.value = "";
  busy.value = false;
  if (!identity || identity.password_change_required) return;
  busy.value = true;
  try {
    const result = await projects.get(typeof value === "string" ? value : "");
    if (current === generation) project.value = result;
  } catch (failure) {
    if (current === generation) error.value = failure instanceof ProjectReadError
      ? failure.message : "暂时无法读取项目，请稍后重试。";
  } finally {
    if (current === generation) busy.value = false;
  }
}, { immediate: true });
onUnmounted(() => { generation += 1; });
</script>

<template>
  <section class="project-detail" aria-labelledby="project-title" :aria-busy="busy">
    <p class="section-kicker">当前项目</p>
    <h1 id="project-title">项目详情</h1>
    <p><RouterLink to="/projects">返回我的项目</RouterLink></p>
    <template v-if="!identity">
      <p role="status">尚未读取当前身份。请先登录，或在账户页读取当前身份。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else-if="identity.password_change_required">
      <p role="status">当前账户须先修改密码，暂不能读取项目。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else>
      <p v-if="busy" role="status">正在确认当前项目访问权限…</p>
      <p v-if="error" role="alert">{{ error }}</p>
      <dl v-if="project" aria-label="当前授权项目详情">
        <dt>名称</dt><dd>{{ project.name }}</dd>
        <dt>编号</dt><dd>{{ project.code }}</dd>
        <dt>状态</dt><dd>{{ project.state === 'ACTIVE' ? '进行中' : '已归档' }}</dd>
        <dt>创建时间</dt><dd><time :datetime="project.created_at">{{ new Date(project.created_at).toLocaleString('zh-CN') }}</time></dd>
      </dl>
    </template>
  </section>
</template>

<style scoped>
.project-detail { max-width: 48rem; margin: 1rem auto; padding: 1.5rem; background: #fff; border-radius: 1rem; }
.project-detail p { line-height: 1.65; }
.project-detail dl { display: grid; grid-template-columns: minmax(5rem, auto) 1fr; gap: .65rem 1rem; }
.project-detail dt { font-weight: 700; }
.project-detail dd { margin: 0; overflow-wrap: anywhere; }
.project-detail [role="alert"] { color: #a21d25; }
</style>
