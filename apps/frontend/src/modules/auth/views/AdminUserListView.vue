<script setup lang="ts">
import { inject, onMounted, onUnmounted, ref, toRaw } from "vue";
import { RouterLink } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { AdminUserListClient, UserCandidateError, type UserCandidate } from "@/modules/auth/api/adminUserListClient";

const props = defineProps<{ session?: SessionClient; users?: AdminUserListClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const users = toRaw(props.users ?? new AdminUserListClient());
const identity = session.view;
const allowedAtEntry = identity?.deployment_role === "DEPLOYMENT_ADMIN" && !identity.password_change_required;
const items = ref<UserCandidate[]>([]);
const cursor = ref<string | null>(null);
const loaded = ref(false);
const busy = ref(false);
const error = ref("");
let mounted = true;

async function load(next = false) {
  if (!mounted || !allowedAtEntry || busy.value || (next && !cursor.value)) return;
  const before = next ? cursor.value : null;
  busy.value = true;
  error.value = "";
  if (!next) { items.value = []; cursor.value = null; loaded.value = false; }
  try {
    const page = await users.page(before);
    if (!mounted) return;
    if (session.view?.user.user_id !== identity?.user.user_id) {
      error.value = "当前身份已变化，请重新登录后读取用户列表。";
      items.value = []; cursor.value = null; loaded.value = false;
      return;
    }
    const combined = next ? [...items.value, ...page.items] : [...page.items];
    if (new Set(combined.map((user) => user.user_id)).size !== combined.length) {
      throw new UserCandidateError("USER_LIST_UNAVAILABLE");
    }
    items.value = combined;
    cursor.value = page.next_cursor;
    loaded.value = true;
  } catch (failure) {
    if (mounted) {
      items.value = []; cursor.value = null; loaded.value = false;
      error.value = failure instanceof UserCandidateError ? failure.message : "暂时无法读取用户列表，请稍后重试。";
    }
  } finally { if (mounted) busy.value = false; }
}
onMounted(() => { void load(); });
onUnmounted(() => { mounted = false; });
</script>

<template>
  <section class="user-list" aria-labelledby="user-list-title" :aria-busy="busy">
    <p class="section-kicker">部署管理</p>
    <h1 id="user-list-title">用户账户</h1>
    <p>列表来自服务器当前授权查询，可用于核对账户是否存在；账户启用状态可能变化，不代表项目成员资格。</p>
    <template v-if="!identity || !allowedAtEntry">
      <p role="status">需要已登录且不受改密限制的部署管理员会话。</p>
      <RouterLink to="/login">前往账户与登录</RouterLink>
    </template>
    <template v-else>
      <p>当前部署管理员：{{ identity.user.username_display }}</p>
      <RouterLink to="/admin/users/new">创建账户</RouterLink>
      <button type="button" :disabled="busy" @click="load(false)">刷新用户列表</button>
      <p v-if="error" role="alert">{{ error }}</p>
      <RouterLink v-if="error" to="/login">如登录失效，请重新登录或读取当前身份</RouterLink>
      <p v-if="loaded && items.length === 0" role="status">当前没有可显示的用户账户。</p>
      <ul v-if="loaded && items.length" aria-label="部署用户账户">
        <li v-for="user in items" :key="user.user_id">
          <span>{{ user.username_display }}</span>
          <span>{{ user.account_state === 'ENABLED' ? '启用' : '停用' }} · {{ user.user_id }}</span>
          <RouterLink :to="`/admin/users/${user.user_id}`">查看详情与状态</RouterLink>
        </li>
      </ul>
      <button v-if="cursor" type="button" :disabled="busy" @click="load(true)">加载更多用户</button>
    </template>
  </section>
</template>

<style scoped>
.user-list { max-width: 48rem; margin: 1rem auto; padding: 1.5rem; background: #fff; border-radius: 1rem; }
.user-list p { line-height: 1.65; }
.user-list ul { list-style: none; padding: 0; display: grid; gap: .8rem; }
.user-list li { display: grid; gap: .25rem; border: 1px solid #d6ded7; border-radius: .5rem; padding: .9rem; }
.user-list button { margin: .8rem; }
.user-list [role="alert"] { color: #a21d25; }
.user-list button:disabled { opacity: .55; cursor: not-allowed; }
</style>
