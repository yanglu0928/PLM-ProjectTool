<script setup lang="ts">
import { inject, onMounted, onUnmounted, ref, toRaw } from "vue";
import { RouterLink } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { CapabilityReadClient, CapabilityReadError, type CapabilityBaseline } from "@/modules/capability/api/capabilityReadClient";

const props = defineProps<{ session?: SessionClient; client?: CapabilityReadClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const client = toRaw(props.client ?? new CapabilityReadClient());
const actorId = session.view?.user.user_id;
const baselines = ref<readonly CapabilityBaseline[]>([]);
const cursor = ref<string | null>(null);
const loaded = ref(false);
const busy = ref(false);
const error = ref("");
let mounted = true;
let generation = 0;
function mayRead(): boolean {
  const view = session.view;
  return mounted && !!actorId && view?.user.user_id === actorId && !view.password_change_required
    && (view.deployment_role === "DEPLOYMENT_ADMIN" || view.authorized_projects.length > 0);
}
function clear(): void {
  generation += 1; baselines.value = []; cursor.value = null; loaded.value = false; busy.value = false; error.value = "";
}
const unsubscribe = session.subscribe(() => { clear(); if (mayRead()) void load(); });
async function load(next = false): Promise<void> {
  if (!mayRead() || busy.value || (next && !cursor.value)) return;
  const request = ++generation;
  busy.value = true; error.value = "";
  try {
    const page = await client.listBaselines(next ? cursor.value : null);
    if (!mayRead() || request !== generation) return;
    const admin = session.view!.deployment_role === "DEPLOYMENT_ADMIN";
    if (!admin && page.items.some(item => item.state !== "ACTIVE" || !item.current_approved_version_ref)) {
      throw new CapabilityReadError("CAPABILITY_READ_UNAVAILABLE");
    }
    if (new Set([...baselines.value, ...page.items].map(item => item.baseline_id)).size
      !== baselines.value.length + page.items.length && next) {
      throw new CapabilityReadError("CAPABILITY_READ_UNAVAILABLE");
    }
    baselines.value = next ? [...baselines.value, ...page.items] : page.items;
    cursor.value = page.next_cursor; loaded.value = true;
  } catch (failure) {
    if (mayRead() && request === generation) {
      if (!next) baselines.value = [];
      error.value = failure instanceof CapabilityReadError ? failure.message : "暂时无法读取能力基线。";
    }
  } finally { if (request === generation) busy.value = false; }
}
onMounted(() => { void load(); });
onUnmounted(() => { mounted = false; clear(); unsubscribe(); });
</script>

<template>
  <section class="page-panel">
    <h1>标准能力基线</h1>
    <p>仅展示当前账户有权读取的全局能力资料；能力建议不能替代正式审批。</p>
    <p v-if="session.view?.deployment_role === 'DEPLOYMENT_ADMIN'">
      <RouterLink :to="{ name: 'global-capability-document-upload' }">上传标准能力来源文档</RouterLink>
    </p>
    <p v-if="!mayRead()" role="status">请先登录并取得项目成员或部署管理员权限。</p>
    <template v-else>
      <p v-if="session.view?.deployment_role === 'DEPLOYMENT_ADMIN'">管理员历史视图：可能包含未批准版本。</p>
      <p v-else>项目成员视图：仅当前已批准基线。</p>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="busy" role="status">正在读取…</p>
      <p v-if="loaded && !baselines.length">暂无可查看的能力基线。</p>
      <ul v-if="baselines.length">
        <li v-for="item in baselines" :key="item.baseline_id">
          <RouterLink :to="{ name: 'capability-baseline-detail', params: { baselineId: item.baseline_id } }">
            {{ item.baseline_code }} · {{ item.name }}
          </RouterLink>
          <span> · {{ item.current_approved_version_ref ? '有当前批准版本' : '尚无批准版本' }}</span>
        </li>
      </ul>
      <button v-if="cursor" type="button" :disabled="busy" @click="load(true)">加载更多</button>
      <button v-if="error && !busy" type="button" @click="clear(); load()">重试</button>
    </template>
  </section>
</template>
