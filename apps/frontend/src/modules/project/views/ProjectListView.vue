<script setup lang="ts">
import { inject, onMounted, onUnmounted, ref, toRaw } from "vue";
import { RouterLink } from "vue-router";

import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { ProjectReadClient, ProjectReadError, type ProjectPage } from "@/modules/project/api/projectReadClient";

const props = defineProps<{ session?: SessionClient; projects?: ProjectReadClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const projects = toRaw(props.projects ?? new ProjectReadClient());
const identity = session.view;
const page = ref<ProjectPage | null>(null);
const busy = ref(false);
const error = ref("");
let mounted = true;

async function load() {
  if (busy.value || !identity || identity.password_change_required) return;
  busy.value = true;
  page.value = null;
  error.value = "";
  try {
    const result = await projects.list();
    if (mounted) page.value = result;
  } catch (failure) {
    if (mounted) error.value = failure instanceof ProjectReadError
      ? failure.message : "暂时无法读取项目，请稍后重试。";
  } finally {
    if (mounted) busy.value = false;
  }
}
onMounted(() => { void load(); });
onUnmounted(() => { mounted = false; });
</script>

<template>
  <section class="project-panel" aria-labelledby="projects-title" :aria-busy="busy">
    <p class="section-kicker">当前授权范围</p>
    <h1 id="projects-title">我的项目</h1>
    <p>项目内容以服务器当前授权为准；登录页显示的项目摘要不作为访问凭据。</p>
    <template v-if="!identity">
      <p role="status">尚未读取当前身份。请先登录，或在账户页读取当前身份。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else-if="identity.password_change_required">
      <p role="status">当前账户须先修改密码，暂不能读取项目。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else>
      <p>当前账户：{{ identity.user.username_display }}</p>
      <button type="button" :disabled="busy" @click="load">{{ busy ? '正在读取…' : '刷新项目列表' }}</button>
      <p v-if="error" role="alert">{{ error }}</p>
      <RouterLink v-if="error" to="/login">如登录失效，请重新登录或读取当前身份</RouterLink>
      <p v-if="page && page.items.length === 0" role="status">当前没有可查看的项目。部署管理员身份本身不授予项目成员权限。</p>
      <ul v-if="page && page.items.length" aria-label="当前授权项目">
        <li v-for="project in page.items" :key="project.project_id">
          <strong>{{ project.name }}</strong>
          <span>编号：{{ project.code }} · {{ project.state === 'ACTIVE' ? '进行中' : '已归档' }}</span>
        </li>
      </ul>
    </template>
  </section>
</template>

<style scoped>
.project-panel { max-width: 48rem; margin: 1rem auto; padding: 1.5rem; background: #fff; border-radius: 1rem; }
.project-panel p { line-height: 1.65; }
.project-panel ul { list-style: none; padding: 0; display: grid; gap: .8rem; }
.project-panel li { display: grid; gap: .25rem; border: 1px solid #d6ded7; border-radius: .5rem; padding: .9rem; }
.project-panel button:disabled { cursor: not-allowed; opacity: .55; }
.project-panel [role="alert"] { color: #a21d25; }
</style>
