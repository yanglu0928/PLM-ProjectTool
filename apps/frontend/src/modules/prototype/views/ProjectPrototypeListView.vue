<script setup lang="ts">
import { computed, inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { PrototypeIdentityReadClient, PrototypeReadError, type PrototypeCursor,
  type PrototypeView } from "@/modules/prototype/api/prototypeReadClient";
import { PrototypeWriteClient, PrototypeWriteError } from "@/modules/prototype/api/prototypeWriteClient";

const props = defineProps<{ session?: SessionClient; reader?: PrototypeIdentityReadClient; writer?: PrototypeWriteClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const reader = toRaw(props.reader ?? new PrototypeIdentityReadClient());
const writer = toRaw(props.writer ?? new PrototypeWriteClient(session));
const identity = session.view; const route = useRoute();
const items = ref<readonly PrototypeView[]>([]); const cursor = ref<PrototypeCursor | null>(null);
const loaded = ref(false); const busy = ref(false); const error = ref(""); const notice = ref("");
const name = ref(""); const confirmed = ref(false);
const pending = ref<{ readonly name: string; readonly key: string } | null>(null);
let generation = 0; let mounted = true;
const projectId = () => typeof route.params.projectId === "string" ? route.params.projectId : "";
const role = computed(() => identity?.authorized_projects.find(item => item.project_id === projectId())?.role ?? null);
const canCreate = computed(() => !!identity && !identity.password_change_required && session.canSubmit
  && session.view?.user.user_id === identity.user.user_id && ["PROJECT_MANAGER", "IMPLEMENTATION_MEMBER"].includes(role.value ?? ""));
const stateLabels = Object.freeze({ ACTIVE: "有效", NOT_REQUIRED: "明确不需要", ARCHIVED: "已归档" });

async function load(next: PrototypeCursor | null = null, replace = false) {
  if (!identity || identity.password_change_required || busy.value) return;
  const project = projectId(), run = ++generation; busy.value = true; error.value = "";
  if (replace) { items.value = []; cursor.value = null; loaded.value = false; }
  try {
    const page = await reader.list(project, 50, next);
    if (!mounted || run !== generation || project !== projectId()) return;
    const known = new Set(items.value.map(item => item.prototype_id));
    if (page.items.some(item => known.has(item.prototype_id))) throw new PrototypeReadError("PROTOTYPE_READ_UNAVAILABLE");
    items.value = Object.freeze([...items.value, ...page.items]); cursor.value = page.next_cursor; loaded.value = true;
  } catch (failure) {
    if (!mounted || run !== generation || project !== projectId()) return;
    items.value = []; cursor.value = null; loaded.value = false;
    error.value = failure instanceof Error ? failure.message : "暂时无法读取项目原型。";
  } finally { if (mounted && run === generation) busy.value = false; }
}
async function create(attempt = pending.value ?? { name: name.value.trim(), key: `prototype-create-${crypto.randomUUID()}` }) {
  if (!canCreate.value || busy.value || !confirmed.value && pending.value === null) return;
  const project = projectId(), run = ++generation; busy.value = true; error.value = ""; notice.value = "";
  if (pending.value === null) pending.value = Object.freeze(attempt);
  let refresh = false;
  try {
    const created = await writer.createPrototype(project, attempt.name, attempt.key);
    if (!mounted || run !== generation || project !== projectId()) return;
    notice.value = `原型“${created.name}”已创建。请进入详情维护固定版本；创建回执不代表审批通过。`;
    pending.value = null; name.value = ""; confirmed.value = false; refresh = true;
  } catch (failure) {
    if (!mounted || run !== generation) return;
    error.value = failure instanceof Error ? failure.message : "暂时无法确认创建结果。";
    if (!(failure instanceof PrototypeWriteError) || !failure.uncertain) pending.value = null;
  } finally { if (mounted && run === generation) busy.value = false; }
  if (refresh && mounted && run === generation) await load(null, true);
}
watch(() => route.params.projectId, () => {
  generation += 1; items.value = []; cursor.value = null; loaded.value = false; error.value = ""; notice.value = "";
  pending.value = null; name.value = ""; confirmed.value = false; busy.value = false; void load(null, true);
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; });
</script>

<template>
  <section class="prototype-list" aria-labelledby="prototype-list-title" :aria-busy="busy">
    <p class="section-kicker">项目原型</p><h1 id="prototype-list-title">原型范围与固定版本</h1>
    <p class="warning"><strong>模板和 AI 输出只是辅助输入，不是客户确认事实。</strong>原型版本必须引用已批准需求、
      固定模板版本和固定文档版本，并经校验与正式评审后才能批准。</p>
    <p>“没有原型”不能自动解释为“不需要原型”；必须进入原型详情，由有权人员明确记录原因、影响和受影响需求。</p>
    <nav aria-label="原型相关页面"><RouterLink :to="{ name: 'project-detail', params: { projectId: route.params.projectId } }">返回项目详情</RouterLink>
      <RouterLink :to="{ name: 'project-prototype-packages', params: { projectId: route.params.projectId } }">原型包</RouterLink>
      <RouterLink :to="{ name: 'project-prototype-templates', params: { projectId: route.params.projectId } }">原型模板</RouterLink>
      <RouterLink :to="{ name: 'project-prototype-links', params: { projectId: route.params.projectId } }">需求覆盖关系</RouterLink></nav>
    <p v-if="!identity" role="status">尚未读取当前身份，请先登录。</p>
    <p v-else-if="identity.password_change_required" role="status">当前账户须先修改密码。</p>
    <template v-else>
      <form v-if="canCreate" @submit.prevent="create()"><h2>创建原型身份</h2>
        <label>原型名称<input v-model="name" required maxlength="255" :disabled="busy || !!pending"></label>
        <p class="hint">这里只创建可追溯身份，不会自动生成页面、批准版本或执行 AI 内容。</p>
        <label class="confirm"><input v-model="confirmed" type="checkbox" :disabled="busy || !!pending">我确认该名称对应当前项目需要维护的原型范围。</label>
        <button :disabled="busy || !confirmed || !!pending">创建原型</button>
      </form>
      <aside v-if="pending" class="pending" aria-live="polite"><strong>上次创建结果未知。</strong>
        <p>请保留当前名称和操作号，不要新建重复原型。可用原操作恢复首次结果。</p>
        <button type="button" :disabled="busy" @click="create(pending)">使用原操作恢复结果</button></aside>
      <button type="button" :disabled="busy" @click="load(null, true)">{{ busy ? "正在读取…" : "刷新原型" }}</button>
      <p v-if="error" role="alert">{{ error }}</p><p v-if="notice" role="status">{{ notice }}</p>
      <p v-if="loaded && !items.length" role="status">当前项目没有可见原型；请创建原型或确认是否需要正式“不需要原型”决定。</p>
      <ol v-if="items.length" aria-label="项目原型">
        <li v-for="item in items" :key="item.prototype_id"><div><strong>{{ item.name }}</strong><span>{{ stateLabels[item.state] }}</span></div>
          <span>更新时间：<time :datetime="item.updated_at">{{ new Date(item.updated_at).toLocaleString("zh-CN") }}</time></span>
          <span>当前批准版本：{{ item.current_approved_version_ref ? "已形成" : "尚未形成" }}</span>
          <RouterLink :to="{ name: 'project-prototype-detail', params: { projectId: item.project_id, prototypeId: item.prototype_id } }">查看范围、版本和人工维护项</RouterLink></li>
      </ol><button v-if="cursor" type="button" :disabled="busy" @click="load(cursor)">加载更多原型</button>
    </template>
  </section>
</template>

<style scoped>
.prototype-list{max-width:64rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}.prototype-list nav{display:flex;gap:1rem;flex-wrap:wrap}.prototype-list form,.prototype-list label{display:grid;gap:.4rem}.prototype-list form,.pending{margin:1rem 0;padding:1rem;border:1px solid #d8dee7;border-radius:.8rem}.prototype-list ol{display:grid;gap:.8rem;padding:0;list-style:none}.prototype-list li{display:grid;gap:.4rem;padding:1rem;border:1px solid #d8dee7;border-radius:.75rem}.prototype-list li div{display:flex;justify-content:space-between;gap:1rem}.warning{padding:.8rem 1rem;border-left:.3rem solid #d29b42;background:#fff8e9}.hint{color:#4b5563}.confirm{display:flex!important;align-items:flex-start}.pending{background:#fff8e9}.prototype-list [role=alert]{color:#a21d25}
</style>
