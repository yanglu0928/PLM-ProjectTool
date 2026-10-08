<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw } from "vue";
import { RouterLink } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { GlobalReferenceReadClient, GlobalReferenceReadError,
  type GlobalReferenceSummary } from "@/modules/solution/api/globalReferenceReadClient";

const props = defineProps<{ session?: SessionClient; reader?: GlobalReferenceReadClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const reader = toRaw(props.reader ?? new GlobalReferenceReadClient());
const items = ref<readonly GlobalReferenceSummary[]>([]);
const cursor = ref<string | null>(null);
const busy = ref(false); const loaded = ref(false); const error = ref("");
let generation = 0; let mounted = true;
function mayRead() {
  return mounted && session.view?.deployment_role === "DEPLOYMENT_ADMIN"
    && !session.view.password_change_required;
}
async function load(next: string | null = null, replace = false) {
  if (!mayRead() || busy.value) return;
  const run = ++generation;
  busy.value = true; error.value = "";
  if (replace) { items.value = []; cursor.value = null; loaded.value = false; }
  try {
    const page = await reader.list(50, next);
    if (!mounted || run !== generation || !mayRead()) return;
    const previous = items.value;
    if (page.items.some(item => previous.some(old => old.reference_solution_id === item.reference_solution_id)
      || previous.length > 0 && item.reference_solution_id <= previous[previous.length - 1]!.reference_solution_id)) {
      throw new GlobalReferenceReadError("GLOBAL_REFERENCE_UNAVAILABLE");
    }
    items.value = Object.freeze([...previous, ...page.items]);
    cursor.value = page.next_cursor; loaded.value = true;
  } catch (failure) {
    if (!mounted || run !== generation) return;
    items.value = []; cursor.value = null; loaded.value = false;
    error.value = failure instanceof Error ? failure.message : "暂时无法读取全局参考方案。";
  } finally { if (mounted && run === generation) busy.value = false; }
}
onUnmounted(() => { mounted = false; generation += 1; });
const stateLabel = (state: GlobalReferenceSummary["eligibility_state"]) => ({
  REFERENCE_ONLY: "仅供参考", ELIGIBLE: "已标记可用", RESTRICTED: "受限", REVOKED: "已撤销",
})[state];
</script>

<template>
  <section class="global-reference-list" aria-labelledby="global-reference-list-title" :aria-busy="busy">
    <p class="section-kicker">平台方案</p><h1 id="global-reference-list-title">全局参考方案候选</h1>
    <p class="warning">仅展示历史固定来源和当前标记；不代表来源仍合格、脱敏确认仍有效或方案已获客户批准。</p>
    <p><RouterLink :to="{ name: 'global-reference-source-picker' }">返回来源集合核查</RouterLink></p>
    <p v-if="!session.view" role="status">尚未读取当前身份，请先登录。</p>
    <p v-else-if="session.view.password_change_required" role="status">当前账户须先修改密码。</p>
    <p v-else-if="session.view.deployment_role !== 'DEPLOYMENT_ADMIN'" role="status">当前账户无权查看全局参考方案。</p>
    <template v-else>
      <button type="button" :disabled="busy" @click="load(null, true)">{{ busy ? "正在读取…" : "读取候选" }}</button>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="loaded && !items.length" role="status">当前没有可见的全局参考方案。</p>
      <ol v-if="items.length" aria-label="全局参考方案候选"><li v-for="item in items" :key="item.reference_solution_id">
        <strong>{{ item.name }}</strong><span>{{ stateLabel(item.eligibility_state) }} · 草稿版本 {{ item.version_no }}</span>
        <time :datetime="item.created_at">{{ new Date(item.created_at).toLocaleString("zh-CN") }}</time>
        <RouterLink :to="{ name: 'global-reference-detail', params: { referenceId: item.reference_solution_id } }">查看固定来源与待核对信息</RouterLink>
      </li></ol>
      <button v-if="cursor" type="button" :disabled="busy" @click="load(cursor)">加载更多候选</button>
    </template>
  </section>
</template>

<style scoped>
.global-reference-list{max-width:60rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}.global-reference-list ol{display:grid;gap:.8rem;padding:0;list-style:none}.global-reference-list li{display:grid;gap:.35rem;padding:1rem;border:1px solid #d8dee7;border-radius:.75rem}.warning{padding:.8rem 1rem;border-left:.3rem solid #d29b42;background:#fff8e9}.global-reference-list [role=alert]{color:#a21d25}
</style>
