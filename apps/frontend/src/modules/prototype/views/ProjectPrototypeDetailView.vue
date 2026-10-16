<script setup lang="ts">
import { computed, inject, onUnmounted, reactive, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { PrototypeIdentityReadClient, PrototypeVersionReadClient, type PrototypeVersionView,
  type PrototypeView } from "@/modules/prototype/api/prototypeReadClient";
import { PrototypeWriteClient, PrototypeWriteError } from "@/modules/prototype/api/prototypeWriteClient";
import { RequirementReadClient, type RequirementView } from "@/modules/requirement/api/requirementReadClient";

type Pending = { readonly kind: "mark"; readonly etag: string; readonly input: {
  readonly affected_requirement_version_refs: readonly string[]; readonly reason: string; readonly impact: string;
  readonly review_id: null; readonly review_round_id: null }; readonly key: string }
  | { readonly kind: "archive"; readonly etag: string; readonly key: string };
const props = defineProps<{ session?: SessionClient; identities?: PrototypeIdentityReadClient;
  versions?: PrototypeVersionReadClient; requirements?: RequirementReadClient; writer?: PrototypeWriteClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const identities = toRaw(props.identities ?? new PrototypeIdentityReadClient());
const versionsApi = toRaw(props.versions ?? new PrototypeVersionReadClient());
const requirementsApi = toRaw(props.requirements ?? new RequirementReadClient());
const writer = toRaw(props.writer ?? new PrototypeWriteClient(session));
const identity = session.view; const route = useRoute();
const root = ref<PrototypeView | null>(null); const versions = ref<readonly PrototypeVersionView[]>([]);
const requirements = ref<readonly RequirementView[]>([]); const busy = ref(false); const error = ref(""); const notice = ref("");
const rename = ref(""); const renameConfirmed = ref(false); const archiveConfirmed = ref(false); const pending = ref<Pending | null>(null);
const decision = reactive({ reason: "", impact: "", affected: [] as string[], confirmed: false });
let generation = 0; let mounted = true;
const projectId = () => typeof route.params.projectId === "string" ? route.params.projectId : "";
const prototypeId = () => typeof route.params.prototypeId === "string" ? route.params.prototypeId : "";
const role = computed(() => identity?.authorized_projects.find(item => item.project_id === projectId())?.role ?? null);
const live = computed(() => !!identity && !identity.password_change_required && session.canSubmit
  && session.view?.user.user_id === identity.user.user_id);
const canPatch = computed(() => live.value && ["PROJECT_MANAGER", "IMPLEMENTATION_MEMBER"].includes(role.value ?? ""));
const canDecide = computed(() => live.value && ["PROJECT_MANAGER", "CUSTOMER_MANAGER"].includes(role.value ?? ""));
const canArchive = computed(() => live.value && role.value === "PROJECT_MANAGER");
const approvedRequirements = computed(() => requirements.value.filter(item => item.current_approved_version_ref !== null));
const states = Object.freeze({ ACTIVE: "有效", NOT_REQUIRED: "明确不需要", ARCHIVED: "已归档" });

async function load() {
  if (!identity || identity.password_change_required || busy.value) return;
  const project = projectId(), prototype = prototypeId(), run = ++generation; busy.value = true; error.value = "";
  try {
    const [item, page, requirementPage] = await Promise.all([
      identities.get(project, prototype), versionsApi.list(project, prototype, 100), requirementsApi.listRequirements(project, 200),
    ]);
    if (!mounted || run !== generation || project !== projectId() || prototype !== prototypeId()) return;
    root.value = item; versions.value = page.items; requirements.value = requirementPage.items; rename.value = item.name;
  } catch (failure) {
    if (mounted && run === generation) { root.value = null; versions.value = []; requirements.value = [];
      error.value = failure instanceof Error ? failure.message : "暂时无法读取原型详情。"; }
  } finally { if (mounted && run === generation) busy.value = false; }
}
async function refreshAfter(run: number) { if (mounted && run === generation) { busy.value = false; await load(); } }
async function patchName() {
  if (!canPatch.value || !root.value || !renameConfirmed.value || busy.value) return;
  const project = projectId(), prototype = prototypeId(), expected = root.value.etag, requested = rename.value.trim();
  const run = ++generation; busy.value = true; error.value = ""; notice.value = ""; renameConfirmed.value = false;
  try {
    const result = await writer.patchPrototype(project, prototype, expected, requested);
    if (!mounted || run !== generation) return; root.value = { ...root.value, ...result } as PrototypeView;
    notice.value = "名称已更新；当前ETag已替换为服务端回执。";
  } catch (failure) {
    if (!mounted || run !== generation) return;
    if (failure instanceof PrototypeWriteError && failure.uncertain) {
      busy.value = false;
      try {
        const current = await identities.get(project, prototype);
        if (!mounted || run !== generation) return; root.value = current; rename.value = current.name;
        notice.value = current.name === requested ? "写入回执曾丢失；独立GET已证明名称更新成功。"
          : "写入结果未知且当前名称未匹配。已重新读取，请核对后决定是否再次修改。";
      } catch { if (mounted && run === generation) error.value = "写入结果未知，且独立GET对账失败；请勿盲目重试。"; }
    } else error.value = failure instanceof Error ? failure.message : "暂时无法更新名称。";
  } finally { if (mounted && run === generation) busy.value = false; }
}
async function mark(attempt: Extract<Pending, { kind: "mark" }> | null = null) {
  if (!canDecide.value || !root.value || busy.value || !decision.confirmed && attempt === null) return;
  const value = attempt ?? Object.freeze({ kind: "mark" as const, etag: root.value.etag, input: Object.freeze({
    affected_requirement_version_refs: Object.freeze([...decision.affected].sort()), reason: decision.reason.trim(),
    impact: decision.impact.trim(), review_id: null, review_round_id: null,
  }), key: `prototype-scope-${crypto.randomUUID()}` });
  const run = ++generation; busy.value = true; error.value = ""; notice.value = ""; pending.value = value;
  try {
    await writer.markNotRequired(projectId(), prototypeId(), value.etag, value.input, value.key);
    if (!mounted || run !== generation) return; pending.value = null; decision.confirmed = false;
    notice.value = "已记录正式“不需要原型”范围决定；这不是需求或后续阶段的自动批准。";
  } catch (failure) {
    if (!mounted || run !== generation) return; error.value = failure instanceof Error ? failure.message : "暂时无法确认范围决定。";
    if (!(failure instanceof PrototypeWriteError) || !failure.uncertain) pending.value = null;
  } finally { if (mounted && run === generation) busy.value = false; }
  if (pending.value === null && mounted && run === generation) await refreshAfter(run);
}
async function archive(attempt: Extract<Pending, { kind: "archive" }> | null = null) {
  if (!canArchive.value || !root.value || busy.value || !archiveConfirmed.value && attempt === null) return;
  const value = attempt ?? Object.freeze({ kind: "archive" as const, etag: root.value.etag,
    key: `prototype-archive-${crypto.randomUUID()}` });
  const run = ++generation; busy.value = true; error.value = ""; notice.value = ""; pending.value = value;
  try { await writer.archivePrototype(projectId(), prototypeId(), value.etag, value.key);
    if (mounted && run === generation) { pending.value = null; archiveConfirmed.value = false; notice.value = "原型已归档。"; } }
  catch (failure) { if (mounted && run === generation) { error.value = failure instanceof Error ? failure.message : "暂时无法确认归档结果。";
    if (!(failure instanceof PrototypeWriteError) || !failure.uncertain) pending.value = null; } }
  finally { if (mounted && run === generation) busy.value = false; }
  if (pending.value === null && mounted && run === generation) await refreshAfter(run);
}
watch(() => [route.params.projectId, route.params.prototypeId], () => {
  generation += 1; root.value = null; versions.value = []; requirements.value = []; pending.value = null;
  error.value = ""; notice.value = ""; busy.value = false; void load();
}, { immediate: true });
onUnmounted(() => { mounted = false; generation += 1; });
</script>

<template>
  <section class="prototype-detail" aria-labelledby="prototype-detail-title" :aria-busy="busy">
    <p class="section-kicker">项目原型</p><h1 id="prototype-detail-title">原型详情与人工维护</h1>
    <p class="warning"><strong>原型是经人工维护和评审的业务资产。</strong>模板、AI建议和校验结果都不会自动成为批准事实。</p>
    <p><RouterLink :to="{ name: 'project-prototypes', params: { projectId: route.params.projectId } }">返回原型列表</RouterLink></p>
    <p v-if="!identity" role="status">尚未读取当前身份，请先登录。</p><p v-else-if="busy && !root" role="status">正在读取原型…</p>
    <p v-if="error" role="alert">{{ error }}</p><p v-if="notice" role="status">{{ notice }}</p>
    <template v-if="root"><header><h2>{{ root.name }}</h2><span>{{ states[root.state] }} · {{ root.etag }}</span></header>
      <dl><dt>当前批准版本</dt><dd>{{ root.current_approved_version_ref ? "已形成" : "尚未形成" }}</dd>
        <dt>创建时间</dt><dd>{{ new Date(root.created_at).toLocaleString("zh-CN") }}</dd>
        <dt>更新时间</dt><dd>{{ new Date(root.updated_at).toLocaleString("zh-CN") }}</dd></dl>
      <nav><RouterLink :to="{ name: 'project-prototype-versions', params: { projectId: root.project_id, prototypeId: root.prototype_id } }">维护结构化版本</RouterLink>
        <RouterLink :to="{ name: 'project-prototype-links', params: { projectId: root.project_id } }">维护需求覆盖关系</RouterLink></nav>
      <section><h2>固定版本</h2><p v-if="!versions.length">尚无版本。需要人工选择固定模板、批准需求和文档制品后创建。</p>
        <ol v-else><li v-for="item in versions" :key="item.prototype_version_id">版本 {{ item.version_no }} · {{ item.state }} ·
          <RouterLink :to="{ name: 'project-prototype-version-detail', params: { projectId: root.project_id,
            prototypeId: root.prototype_id, versionId: item.prototype_version_id } }">查看结构、来源与固定原文</RouterLink></li></ol></section>
      <form v-if="canPatch && root.state === 'ACTIVE'" @submit.prevent="patchName"><h2>修改显示名称</h2>
        <label>新名称<input v-model="rename" required maxlength="255"></label><label class="confirm"><input v-model="renameConfirmed" type="checkbox">我确认只修改名称，不改变固定版本内容。</label>
        <button :disabled="busy || !renameConfirmed">按当前ETag修改</button><p class="hint">此PATCH不具备幂等键；回执丢失时页面会先重新读取，绝不自动覆盖。</p></form>
      <form v-if="canDecide && root.state === 'ACTIVE'" @submit.prevent="mark()"><h2>明确“不需要原型”</h2>
        <p>只有确实不需要原型时使用。必须说明业务原因、影响，并选择所有受影响的已批准需求；不能以空列表代替决定。</p>
        <label>原因<textarea v-model="decision.reason" required maxlength="2000"></textarea></label>
        <label>影响<textarea v-model="decision.impact" required maxlength="2000"></textarea></label>
        <fieldset><legend>受影响的已批准需求</legend><p v-if="!approvedRequirements.length">当前没有可选择的已批准需求，不能形成范围决定。</p>
          <label v-for="item in approvedRequirements" :key="item.requirement_id"><input v-model="decision.affected" type="checkbox"
            :value="item.current_approved_version_ref">{{ item.requirement_code }}</label></fieldset>
        <label class="confirm"><input v-model="decision.confirmed" type="checkbox">我已人工核对原因、影响和受影响需求，确认不是AI自动判断。</label>
        <button :disabled="busy || !decision.confirmed || !decision.affected.length">记录不可变范围决定</button></form>
      <form v-if="canArchive && root.state === 'ACTIVE'" @submit.prevent="archive()"><h2>归档原型</h2>
        <label class="confirm"><input v-model="archiveConfirmed" type="checkbox">我确认归档当前原型身份；历史版本与审计不会删除。</label>
        <button :disabled="busy || !archiveConfirmed">归档</button></form>
      <aside v-if="pending" class="pending"><strong>上次{{ pending.kind === 'mark' ? '范围决定' : '归档' }}结果未知。</strong>
        <p>不要生成新操作号。请用完全相同的输入、ETag和操作号恢复首次结果。</p>
        <button v-if="pending.kind === 'mark'" :disabled="busy" @click="mark(pending)">恢复原范围决定</button>
        <button v-else :disabled="busy" @click="archive(pending)">恢复原归档操作</button></aside>
    </template>
  </section>
</template>

<style scoped>
.prototype-detail{max-width:68rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}.prototype-detail header,.prototype-detail nav{display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap}.prototype-detail dl{display:grid;grid-template-columns:10rem 1fr}.prototype-detail form,.prototype-detail section,.pending{margin:1rem 0;padding:1rem;border:1px solid #d8dee7;border-radius:.8rem}.prototype-detail form,.prototype-detail label{display:grid;gap:.4rem}.prototype-detail textarea{min-height:5rem}.warning{padding:.8rem 1rem;border-left:.3rem solid #d29b42;background:#fff8e9}.confirm{display:flex!important;align-items:flex-start}.hint{color:#4b5563}.pending{background:#fff8e9}.prototype-detail [role=alert]{color:#a21d25}
</style>
