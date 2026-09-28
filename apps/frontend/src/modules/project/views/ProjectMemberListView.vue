<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { ProjectMemberReadClient, ProjectMemberReadError, type ProjectMemberView } from "@/modules/project/api/projectMemberReadClient";

const props = defineProps<{ session?: SessionClient; members?: ProjectMemberReadClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const members = toRaw(props.members ?? new ProjectMemberReadClient());
const identity = session.view;
const route = useRoute();
const items = ref<readonly ProjectMemberView[]>([]);
const nextCursor = ref<string | null>(null);
const loaded = ref(false);
const busy = ref(false);
const error = ref("");
let generation = 0;

async function load(cursor: string | null, replace: boolean) {
  if (busy.value || !identity || identity.password_change_required) return;
  const current = generation;
  const projectId = route.params.projectId;
  busy.value = true;
  error.value = "";
  if (replace) { items.value = []; nextCursor.value = null; loaded.value = false; }
  try {
    const page = await members.list(typeof projectId === "string" ? projectId : "", cursor);
    if (current !== generation) return;
    const known = new Set(items.value.map((item) => item.member_id));
    if (page.items.some((item) => known.has(item.member_id))) {
      throw new ProjectMemberReadError("PROJECT_MEMBER_CLIENT_UNAVAILABLE");
    }
    items.value = Object.freeze([...items.value, ...page.items]);
    nextCursor.value = page.next_cursor;
    loaded.value = true;
  } catch (failure) {
    if (current !== generation) return;
    items.value = [];
    nextCursor.value = null;
    loaded.value = false;
    error.value = failure instanceof ProjectMemberReadError
      ? failure.message : "暂时无法读取项目成员，请稍后重试。";
  } finally {
    if (current === generation) busy.value = false;
  }
}

watch(() => route.params.projectId, () => {
  generation += 1;
  items.value = [];
  nextCursor.value = null;
  loaded.value = false;
  error.value = "";
  busy.value = false;
  void load(null, true);
}, { immediate: true });
onUnmounted(() => { generation += 1; });

const roleNames: Record<ProjectMemberView["role"], string> = {
  PROJECT_MANAGER: "项目负责人", IMPLEMENTATION_MEMBER: "实施成员",
  CUSTOMER_MANAGER: "客户负责人", CUSTOMER_MEMBER: "客户成员",
};
const stateNames: Record<ProjectMemberView["state"], string> = {
  ACTIVE: "有效", SUSPENDED: "暂停", REMOVED: "已移除",
};
</script>

<template>
  <section class="member-panel" aria-labelledby="member-list-title" :aria-busy="busy">
    <p class="section-kicker">项目权限</p>
    <h1 id="member-list-title">项目成员历史</h1>
    <p>可见范围由服务器按当前项目和角色实时确认；列表包含已移除的历史成员。</p>
    <p><RouterLink :to="{ name: 'project-detail', params: { projectId: route.params.projectId } }">返回项目详情</RouterLink></p>
    <p><RouterLink :to="{ name: 'project-member-create', params: { projectId: route.params.projectId } }">添加项目成员</RouterLink></p>
    <template v-if="!identity">
      <p role="status">尚未读取当前身份。请先登录，或在账户页读取当前身份。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else-if="identity.password_change_required">
      <p role="status">当前账户须先修改密码，暂不能读取项目成员。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else>
      <button type="button" :disabled="busy" @click="load(null, true)">{{ busy ? '正在读取…' : '刷新成员列表' }}</button>
      <p v-if="busy" role="status">正在确认项目成员访问权限…</p>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="loaded && items.length === 0" role="status">当前项目没有成员记录。</p>
      <ul v-if="items.length" aria-label="项目成员历史">
        <li v-for="item in items" :key="item.member_id">
          <strong>{{ item.user.display_name }}</strong>
          <span>{{ roleNames[item.role] }} · {{ stateNames[item.state] }} · {{ item.department.name }}</span>
          <span>生效：<time :datetime="item.effective_at">{{ new Date(item.effective_at).toLocaleString('zh-CN') }}</time></span>
          <span v-if="item.ended_at">结束：<time :datetime="item.ended_at">{{ new Date(item.ended_at).toLocaleString('zh-CN') }}</time></span>
        </li>
      </ul>
      <button v-if="nextCursor" type="button" :disabled="busy" @click="load(nextCursor, false)">读取下一页</button>
    </template>
  </section>
</template>

<style scoped>
.member-panel { max-width: 48rem; margin: 1rem auto; padding: 1.5rem; background: #fff; border-radius: 1rem; }
.member-panel p { line-height: 1.65; }
.member-panel ul { list-style: none; padding: 0; display: grid; gap: .8rem; }
.member-panel li { display: grid; gap: .25rem; border: 1px solid #d6ded7; border-radius: .5rem; padding: .9rem; overflow-wrap: anywhere; }
.member-panel button:disabled { cursor: not-allowed; opacity: .55; }
.member-panel [role="alert"] { color: #a21d25; }
</style>
