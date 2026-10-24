<script setup lang="ts">
import { inject, onMounted, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { CapabilityReadClient, CapabilityReadError, type CapabilityBaseline,
  type CapabilityVersion, type CapabilityItem } from "@/modules/capability/api/capabilityReadClient";

const props = defineProps<{ session?: SessionClient; client?: CapabilityReadClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const client = toRaw(props.client ?? new CapabilityReadClient());
const route = useRoute();
const actorId = session.view?.user.user_id;
const baseline = ref<CapabilityBaseline | null>(null);
const versions = ref<readonly CapabilityVersion[]>([]);
const versionCursor = ref<string | null>(null);
const selected = ref<CapabilityVersion | null>(null);
const items = ref<readonly CapabilityItem[]>([]);
const itemCursor = ref<string | null>(null);
const busy = ref(false);
const childBusy = ref(false);
const error = ref("");
let mounted = true;
let generation = 0;
let childGeneration = 0;
function baselineId(): string { return typeof route.params.baselineId === "string" ? route.params.baselineId : ""; }
function mayRead(): boolean {
  const view = session.view;
  return mounted && !!actorId && view?.user.user_id === actorId && !view.password_change_required
    && (view.deployment_role === "DEPLOYMENT_ADMIN" || view.authorized_projects.length > 0);
}
function reset(): void {
  generation += 1; childGeneration += 1; baseline.value = null; versions.value = []; versionCursor.value = null;
  selected.value = null; items.value = []; itemCursor.value = null; busy.value = false; childBusy.value = false; error.value = "";
}
const unsubscribe = session.subscribe(() => { reset(); if (mayRead()) void load(); });
async function load(): Promise<void> {
  reset();
  if (!mayRead()) return;
  const id = baselineId(); const request = ++generation; busy.value = true;
  try {
    const [base, page] = await Promise.all([client.getBaseline(id), client.listVersions(id)]);
    if (!mayRead() || request !== generation || id !== baselineId()) return;
    const admin = session.view!.deployment_role === "DEPLOYMENT_ADMIN";
    if (!admin && (base.state !== "ACTIVE" || !base.current_approved_version_ref
      || page.items.some(item => item.state !== "APPROVED"
        || item.baseline_version_id !== base.current_approved_version_ref))) {
      throw new CapabilityReadError("CAPABILITY_READ_UNAVAILABLE");
    }
    baseline.value = base; versions.value = page.items; versionCursor.value = page.next_cursor;
    if (base.current_approved_version_ref) await choose(base.current_approved_version_ref);
  } catch (failure) {
    if (mayRead() && request === generation) { reset(); error.value = failure instanceof CapabilityReadError
      ? failure.message : "暂时无法读取能力基线。"; }
  } finally { if (request === generation) busy.value = false; }
}
async function moreVersions(): Promise<void> {
  const id = baselineId(); const cursor = versionCursor.value;
  if (!mayRead() || !baseline.value || !cursor || childBusy.value) return;
  const request = ++childGeneration; childBusy.value = true; error.value = "";
  try {
    const page = await client.listVersions(id, cursor);
    if (!mayRead() || request !== childGeneration || id !== baselineId()) return;
    if (session.view?.deployment_role !== "DEPLOYMENT_ADMIN" && page.items.some(item =>
      item.state !== "APPROVED" || item.baseline_version_id !== baseline.value?.current_approved_version_ref)) {
      throw new CapabilityReadError("CAPABILITY_READ_UNAVAILABLE");
    }
    if (new Set([...versions.value, ...page.items].map(item => item.baseline_version_id)).size
      !== versions.value.length + page.items.length) throw new CapabilityReadError("CAPABILITY_READ_UNAVAILABLE");
    versions.value = [...versions.value, ...page.items]; versionCursor.value = page.next_cursor;
  } catch (failure) { if (request === childGeneration) error.value = failure instanceof CapabilityReadError
    ? failure.message : "暂时无法读取版本。"; }
  finally { if (request === childGeneration) childBusy.value = false; }
}
async function choose(versionId: string): Promise<void> {
  const id = baselineId();
  if (!mayRead() || !baseline.value || childBusy.value) return;
  if (session.view?.deployment_role !== "DEPLOYMENT_ADMIN"
    && versionId !== baseline.value.current_approved_version_ref) return;
  const request = ++childGeneration; selected.value = null; items.value = []; itemCursor.value = null;
  childBusy.value = true; error.value = "";
  try {
    const [version, page] = await Promise.all([client.getVersion(id, versionId), client.listItems(id, versionId)]);
    if (!mayRead() || request !== childGeneration || id !== baselineId()) return;
    if (session.view?.deployment_role !== "DEPLOYMENT_ADMIN"
      && (version.state !== "APPROVED" || version.baseline_version_id !== baseline.value?.current_approved_version_ref)) {
      throw new CapabilityReadError("CAPABILITY_READ_UNAVAILABLE");
    }
    selected.value = version; items.value = page.items; itemCursor.value = page.next_cursor;
  } catch (failure) { if (request === childGeneration) error.value = failure instanceof CapabilityReadError
    ? failure.message : "暂时无法读取版本条目。"; }
  finally { if (request === childGeneration) childBusy.value = false; }
}
async function moreItems(): Promise<void> {
  const id = baselineId(); const version = selected.value; const cursor = itemCursor.value;
  if (!mayRead() || !version || !cursor || childBusy.value) return;
  const request = ++childGeneration; childBusy.value = true; error.value = "";
  try {
    const page = await client.listItems(id, version.baseline_version_id, cursor);
    if (!mayRead() || request !== childGeneration || id !== baselineId() || selected.value !== version) return;
    if (new Set([...items.value, ...page.items].map(item => item.capability_item_id)).size
      !== items.value.length + page.items.length) throw new CapabilityReadError("CAPABILITY_READ_UNAVAILABLE");
    items.value = [...items.value, ...page.items]; itemCursor.value = page.next_cursor;
  } catch (failure) { if (request === childGeneration) error.value = failure instanceof CapabilityReadError
    ? failure.message : "暂时无法读取能力条目。"; }
  finally { if (request === childGeneration) childBusy.value = false; }
}
watch(() => route.params.baselineId, () => { void load(); });
onMounted(() => { void load(); });
onUnmounted(() => { mounted = false; reset(); unsubscribe(); });
</script>

<template>
  <section class="page-panel">
    <RouterLink to="/capability-baselines">返回标准能力列表</RouterLink>
    <h1>标准能力详情</h1>
    <p v-if="!mayRead()" role="status">请先登录并取得项目成员或部署管理员权限。</p>
    <template v-else>
      <p v-if="busy || childBusy" role="status">正在读取…</p>
      <p v-if="error" role="alert">{{ error }}</p>
      <template v-if="baseline">
        <h2>{{ baseline.baseline_code }} · {{ baseline.name }}</h2>
        <p v-if="baseline.description">{{ baseline.description }}</p>
        <p>{{ baseline.current_approved_version_ref ? '存在当前批准版本' : '尚无批准版本，不可作为正式能力依据' }}</p>
        <p v-if="session.view?.deployment_role === 'DEPLOYMENT_ADMIN'">管理员历史视图；未批准版本仅供审查。</p>
        <h3>版本</h3>
        <ul><li v-for="version in versions" :key="version.baseline_version_id">
          <button type="button" :disabled="childBusy" @click="choose(version.baseline_version_id)">
            第 {{ version.version_no }} 版 · {{ version.state }}
          </button>
        </li></ul>
        <button v-if="versionCursor" type="button" :disabled="childBusy" @click="moreVersions">加载更多版本</button>
        <template v-if="selected">
          <h3>能力条目 · 第 {{ selected.version_no }} 版</h3>
          <p v-if="selected.state !== 'APPROVED'">此版本尚非正式批准版本。</p>
          <p v-if="!items.length">此版本暂无可显示条目。</p>
          <ul><li v-for="item in items" :key="item.capability_item_id">
            <strong>{{ item.capability_code }} · {{ item.name }}</strong>
            <p>{{ item.domain_name }} / {{ item.module_name }} / {{ item.feature_name }}</p>
            <p>{{ item.description }}</p><p>边界：{{ item.boundary }}</p>
            <p>状态：{{ item.state }}</p>
          </li></ul>
          <button v-if="itemCursor" type="button" :disabled="childBusy" @click="moreItems">加载更多条目</button>
        </template>
      </template>
      <button v-if="error && !busy && !childBusy" type="button" @click="load">重试</button>
    </template>
  </section>
</template>
