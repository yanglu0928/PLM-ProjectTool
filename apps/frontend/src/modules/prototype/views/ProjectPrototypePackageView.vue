<script setup lang="ts">
import { computed, inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { PrototypeIdentityReadClient, PrototypePackageReadClient, PrototypeReadError,
  type PrototypePackageCursor, type PrototypePackageView, type PrototypeView } from "@/modules/prototype/api/prototypeReadClient";
import { PrototypeWriteClient, PrototypeWriteError } from "@/modules/prototype/api/prototypeWriteClient";

type Pending = { readonly kind: "create"; readonly name: string; readonly key: string }
  | { readonly kind: "members"; readonly packageId: string; readonly etag: string;
    readonly prototypeIds: readonly string[]; readonly key: string };
const props = defineProps<{ session?: SessionClient; packages?: PrototypePackageReadClient;
  prototypes?: PrototypeIdentityReadClient; writer?: PrototypeWriteClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const packagesApi = toRaw(props.packages ?? new PrototypePackageReadClient());
const prototypesApi = toRaw(props.prototypes ?? new PrototypeIdentityReadClient());
const writer = toRaw(props.writer ?? new PrototypeWriteClient(session));
const identity = session.view; const route = useRoute();
const packages = ref<readonly PrototypePackageView[]>([]); const prototypes = ref<readonly PrototypeView[]>([]);
const selected = ref<PrototypePackageView | null>(null); const members = ref<string[]>([]);
const createName = ref(""); const createConfirmed = ref(false); const rename = ref(""); const renameConfirmed = ref(false);
const membersConfirmed = ref(false); const pending = ref<Pending | null>(null);
const busy = ref(false); const loaded = ref(false); const error = ref(""); const notice = ref("");
let generation = 0; let mounted = true;
const projectId = () => typeof route.params.projectId === "string" ? route.params.projectId : "";
const role = computed(() => identity?.authorized_projects.find(item => item.project_id === projectId())?.role ?? null);
const canWrite = computed(() => !!identity && !identity.password_change_required && session.canSubmit
  && session.view?.user.user_id === identity.user.user_id
  && ["PROJECT_MANAGER", "IMPLEMENTATION_MEMBER"].includes(role.value ?? ""));
const states = Object.freeze({ ACTIVE: "有效", ARCHIVED: "已归档", RESTRICTED: "当前不可访问" });

async function allPages<T, C extends string>(first: () => Promise<{ readonly items: readonly T[]; readonly next_cursor: C | null }>,
  next: (cursor: C) => Promise<{ readonly items: readonly T[]; readonly next_cursor: C | null }>): Promise<readonly T[]> {
  const page = await first(); const result = [...page.items]; let cursor = page.next_cursor; let count = 1;
  while (cursor && count < 20) { const current = cursor; const more = await next(current); result.push(...more.items);
    cursor = more.next_cursor; count += 1; }
  if (cursor) throw new PrototypeReadError("PROTOTYPE_READ_UNAVAILABLE"); return Object.freeze(result);
}
async function load() {
  if (!identity || identity.password_change_required || busy.value) return;
  const project = projectId(), run = ++generation; busy.value = true; error.value = ""; notice.value = ""; loaded.value = false;
  try {
    const [packageItems, prototypeItems] = await Promise.all([
      allPages(() => packagesApi.list(project), cursor => packagesApi.list(project, 50, cursor as PrototypePackageCursor)),
      allPages(() => prototypesApi.list(project), cursor => prototypesApi.list(project, 50, cursor)),
    ]);
    if (!mounted || run !== generation || project !== projectId()) return;
    if (new Set(packageItems.map(item => item.prototype_package_id)).size !== packageItems.length
      || new Set(prototypeItems.map(item => item.prototype_id)).size !== prototypeItems.length) {
      throw new PrototypeReadError("PROTOTYPE_READ_UNAVAILABLE");
    }
    packages.value = packageItems; prototypes.value = prototypeItems; selected.value = null; members.value = []; loaded.value = true;
  } catch (failure) { if (mounted && run === generation) { packages.value = []; prototypes.value = []; selected.value = null;
    error.value = failure instanceof Error ? failure.message : "暂时无法读取原型包。"; } }
  finally { if (mounted && run === generation) busy.value = false; }
}
async function choose(item: PrototypePackageView) {
  if (busy.value) return; const project = projectId(), run = ++generation; busy.value = true; error.value = ""; notice.value = "";
  try { const detail = await packagesApi.get(project, item.prototype_package_id);
    if (!mounted || run !== generation) return; selected.value = detail; members.value = [...(detail.prototype_ids ?? [])];
    rename.value = detail.name; renameConfirmed.value = false; membersConfirmed.value = false; }
  catch (failure) { if (mounted && run === generation) error.value = failure instanceof Error ? failure.message : "暂时无法读取原型包详情。"; }
  finally { if (mounted && run === generation) busy.value = false; }
}
async function create(attempt: Extract<Pending, { kind: "create" }> | null = null) {
  if (!canWrite.value || busy.value || (!createConfirmed.value && attempt === null)) return;
  const value = attempt ?? Object.freeze({ kind: "create" as const, name: createName.value.trim(),
    key: `prototype-package-create-${crypto.randomUUID()}` });
  const project = projectId(), run = ++generation; let completed = false; busy.value = true; error.value = ""; notice.value = ""; pending.value = value;
  try { await writer.createPackage(project, value.name, value.key); if (!mounted || run !== generation || project !== projectId()) return;
    pending.value = null; createName.value = ""; createConfirmed.value = false; completed = true; }
  catch (failure) { if (mounted && run === generation) { error.value = failure instanceof Error ? failure.message : "暂时无法确认创建结果。";
    if (!(failure instanceof PrototypeWriteError) || !failure.uncertain) pending.value = null; } }
  finally { if (mounted && run === generation) busy.value = false; }
  if (completed && mounted && run === generation) { await load(); if (mounted && project === projectId()) notice.value = "原型包已创建；尚未自动加入任何原型。"; }
}
async function patchName() {
  if (!canWrite.value || !selected.value || !renameConfirmed.value || busy.value) return;
  const project = projectId(), packageId = selected.value.prototype_package_id, expected = selected.value.etag;
  const requested = rename.value.trim(), run = ++generation; busy.value = true; error.value = ""; notice.value = "";
  renameConfirmed.value = false;
  try { const result = await writer.patchPackage(project, packageId, expected, requested); if (!mounted || run !== generation) return;
    selected.value = { ...selected.value, ...result }; notice.value = "原型包名称已更新。"; }
  catch (failure) { if (!mounted || run !== generation) return;
    if (failure instanceof PrototypeWriteError && failure.uncertain) { busy.value = false;
      try { const current = await packagesApi.get(project, packageId); if (!mounted || run !== generation) return;
        selected.value = current; rename.value = current.name; notice.value = current.name === requested
          ? "写入回执曾丢失；独立GET已证明名称更新成功。" : "写入结果未知且名称未匹配，已重新读取；请人工核对。";
      } catch { if (mounted && run === generation) error.value = "写入结果未知，且独立GET对账失败；请勿盲目重试。"; }
    } else error.value = failure instanceof Error ? failure.message : "暂时无法更新名称。";
  } finally { if (mounted && run === generation) busy.value = false; }
}
async function saveMembers(attempt: Extract<Pending, { kind: "members" }> | null = null) {
  if (!canWrite.value || !selected.value || busy.value || (!membersConfirmed.value && attempt === null)) return;
  const value = attempt ?? Object.freeze({ kind: "members" as const, packageId: selected.value.prototype_package_id,
    etag: selected.value.etag, prototypeIds: Object.freeze([...members.value].sort()),
    key: `prototype-package-members-${crypto.randomUUID()}` });
  const run = ++generation; busy.value = true; error.value = ""; notice.value = ""; pending.value = value;
  try { const result = await writer.setPackageMembers(projectId(), value.packageId, value.etag, value.prototypeIds, value.key);
    if (!mounted || run !== generation) return; selected.value = { ...selected.value, ...result }; members.value = [...result.prototype_ids];
    pending.value = null; membersConfirmed.value = false; notice.value = "原型包成员集合已完整替换；原型及历史未删除。"; }
  catch (failure) { if (mounted && run === generation) { error.value = failure instanceof Error ? failure.message : "暂时无法确认成员更新结果。";
    if (!(failure instanceof PrototypeWriteError) || !failure.uncertain) pending.value = null; } }
  finally { if (mounted && run === generation) busy.value = false; }
}
watch(() => route.params.projectId, () => { generation += 1; packages.value = []; prototypes.value = []; selected.value = null;
  pending.value = null; busy.value = false; error.value = ""; notice.value = ""; void load(); }, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; });
</script>

<template>
  <section class="package-page" aria-labelledby="package-title" :aria-busy="busy">
    <p class="section-kicker">项目原型</p><h1 id="package-title">原型包</h1>
    <p class="warning"><strong>原型包只是项目内组织方式。</strong>设置成员会完整替换当前集合，但不会删除原型、固定版本、评审或审计历史。</p>
    <p><RouterLink :to="{ name: 'project-prototypes', params: { projectId: route.params.projectId } }">返回原型列表</RouterLink></p>
    <p v-if="!identity" role="status">尚未读取当前身份，请先登录。</p><p v-else-if="identity.password_change_required" role="status">当前账户须先修改密码。</p>
    <template v-else><button type="button" :disabled="busy" @click="load">{{ busy ? "正在读取…" : "刷新原型包" }}</button>
      <p v-if="error" role="alert">{{ error }}</p><p v-if="notice" role="status">{{ notice }}</p>
      <form v-if="canWrite" @submit.prevent="create()"><h2>创建原型包</h2><label>原型包名称<input v-model="createName" required maxlength="255"></label>
        <label class="confirm"><input v-model="createConfirmed" type="checkbox">我确认只创建组织容器，后续成员由我明确选择。</label>
        <button :disabled="busy || !createConfirmed || !!pending">创建</button></form>
      <p v-if="loaded && !packages.length">当前项目没有原型包。</p>
      <ol class="packages"><li v-for="item in packages" :key="item.prototype_package_id"><strong>{{ item.name }}</strong>
        <span>{{ states[item.state] }} · {{ item.etag }}</span><button type="button" :disabled="busy" @click="choose(item)">查看并维护成员</button></li></ol>
      <section v-if="selected" class="detail"><h2>维护：{{ selected.name }}</h2>
        <form v-if="canWrite && selected.state === 'ACTIVE'" @submit.prevent="patchName"><h3>修改名称</h3>
          <label>新名称<input v-model="rename" required maxlength="255"></label><label class="confirm"><input v-model="renameConfirmed" type="checkbox">我确认只修改名称。</label>
          <button :disabled="busy || !renameConfirmed">按当前ETag修改</button><p class="hint">名称PATCH无幂等键；未知结果只会独立GET对账。</p></form>
        <form v-if="canWrite && selected.state === 'ACTIVE'" @submit.prevent="saveMembers()"><h3>完整成员集合</h3>
          <p>勾选保存后，未勾选的原型会从此包移除，但原型本身和历史保持不变。允许保存空集合。</p>
          <label v-for="item in prototypes" :key="item.prototype_id" class="choice"><input v-model="members" type="checkbox" :value="item.prototype_id">{{ item.name }} · {{ item.state }}</label>
          <label class="confirm"><input v-model="membersConfirmed" type="checkbox">我已核对这是期望的完整集合，不是增量追加。</label>
          <button :disabled="busy || !membersConfirmed || !!pending">完整替换成员</button></form></section>
      <aside v-if="pending" class="pending"><strong>上次{{ pending.kind === 'create' ? '创建' : '成员替换' }}结果未知。</strong>
        <p>不要修改输入或生成新操作号；只能恢复首次操作。</p>
        <button v-if="pending.kind === 'create'" type="button" :disabled="busy" @click="create(pending)">恢复原创建操作</button>
        <button v-else type="button" :disabled="busy" @click="saveMembers(pending)">恢复原成员替换</button></aside>
    </template>
  </section>
</template>

<style scoped>
.package-page{max-width:68rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}.package-page form,.detail,.pending{display:grid;gap:.7rem;margin:1rem 0;padding:1rem;border:1px solid #d8dee7;border-radius:.8rem}.packages{display:grid;gap:.7rem;padding:0;list-style:none}.packages li{display:flex;gap:1rem;align-items:center;flex-wrap:wrap;padding:.8rem;border:1px solid #d8dee7;border-radius:.7rem}.package-page label{display:grid;gap:.35rem}.warning,.pending{padding:.8rem 1rem;border-left:.3rem solid #d29b42;background:#fff8e9}.confirm,.choice{display:flex!important;align-items:flex-start}.hint{color:#4b5563}.package-page [role=alert]{color:#a21d25}
</style>
