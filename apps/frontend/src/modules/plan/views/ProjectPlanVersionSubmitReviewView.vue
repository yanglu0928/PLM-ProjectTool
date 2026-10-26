<script setup lang="ts">
import { inject, onUnmounted, ref, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { ProjectMemberReadClient, type ProjectMemberView } from "@/modules/project/api/projectMemberReadClient";
import { PlanVersionReadClient, type PlanVersionDetail } from "@/modules/plan/api/planVersionReadClient";
import { PlanVersionWriteClient, PlanVersionWriteError, type PlanVersionReviewSubmission } from "@/modules/plan/api/planVersionWriteClient";

const props = defineProps<{ session?: SessionClient; reader?: PlanVersionReadClient; members?: ProjectMemberReadClient; submitter?: PlanVersionWriteClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const reader = toRaw(props.reader ?? new PlanVersionReadClient());
const members = toRaw(props.members ?? new ProjectMemberReadClient());
const submitter = toRaw(props.submitter ?? new PlanVersionWriteClient(session));
const route = useRoute(); const current = ref<PlanVersionDetail | null>(null);
const eligible = ref<readonly ProjectMemberView[]>([]); const selected = ref<string[]>([]);
const receipt = ref<PlanVersionReviewSubmission | null>(null);
const loading = ref(false); const busy = ref(false); const sending = ref(false); const loaded = ref(false);
const confirmed = ref(false); const retryConfirmed = ref(false); const locked = ref(false); const error = ref("");
type Attempt = { actor: string; project: string; plan: string; version: string; reviewer_ids: readonly string[]; key: string };
const pending = ref<Attempt | null>(null); let generation = 0; let mounted = true;
const projectId = () => typeof route.params.projectId === "string" ? route.params.projectId : "";
const planId = () => typeof route.params.planId === "string" ? route.params.planId : "";
const versionId = () => typeof route.params.versionId === "string" ? route.params.versionId : "";
const actor = () => session.view?.user.user_id ?? "";
function manager() { return mounted && !!actor() && !!session.view && !session.view.password_change_required
  && session.view.authorized_projects.some(item => item.project_id === projectId() && item.role === "PROJECT_MANAGER"); }
function ready() { return manager() && !!current.value && current.value.version_state === "DRAFT"
  && current.value.review_ref === null && current.value.review_round_ref === null && !pending.value && !receipt.value; }
function storageKey() { return `plm.plan.version.review.pending.${actor()}.${projectId()}.${planId()}.${versionId()}`; }
function restore() {
  if (!manager()) return;
  try {
    const raw = window.sessionStorage.getItem(storageKey()); if (!raw) return;
    const value: unknown = JSON.parse(raw);
    if (typeof value !== "object" || value === null || Array.isArray(value)) throw Error();
    const item = value as Record<string, unknown>, reviewers = item.reviewer_ids;
    if (Object.keys(item).length !== 6 || item.actor !== actor() || item.project !== projectId()
      || item.plan !== planId() || item.version !== versionId() || !Array.isArray(reviewers)
      || reviewers.length < 1 || reviewers.length > 32 || reviewers.some(id => typeof id !== "string"
        || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(id))
      || new Set(reviewers).size !== reviewers.length || typeof item.key !== "string"
      || !/^[\x20-\x7e]{16,128}$/.test(item.key)) throw Error();
    pending.value = item as Attempt;
  } catch { locked.value = true; error.value = "原送审操作号或评审人记录无法安全读取；请先核对评审与审计，勿更换操作号。"; }
}
async function load() {
  const project = projectId(), plan = planId(), version = versionId(), run = ++generation;
  current.value = null; receipt.value = null; eligible.value = []; selected.value = []; loaded.value = false;
  pending.value = null; locked.value = false; error.value = ""; busy.value = false;
  if (!manager()) { loading.value = false; return; }
  loading.value = true;
  try {
    const snapshot = await reader.detail(project, plan, version);
    if (!mounted || run !== generation || project !== projectId() || plan !== planId() || version !== versionId()) return;
    current.value = snapshot; restore();
  } catch (failure) { if (mounted && run === generation) error.value = failure instanceof Error ? failure.message : "无法读取固定计划版本。"; }
  finally { if (mounted && run === generation) loading.value = false; }
}
async function loadReviewers() {
  if (!ready() || busy.value || sending.value) return;
  const project = projectId(), actorAtStart = actor(), run = generation;
  busy.value = true; error.value = ""; eligible.value = []; loaded.value = false;
  try {
    const all: ProjectMemberView[] = [], seenCursors = new Set<string>(); let cursor: string | null = null;
    for (let page = 0; page < 20; page += 1) {
      const result = await members.list(project, cursor); all.push(...result.items);
      if (!result.has_more) { cursor = null; break; }
      if (!result.next_cursor || seenCursors.has(result.next_cursor)) throw Error("成员分页未能完整读取");
      seenCursors.add(result.next_cursor); cursor = result.next_cursor;
    }
    if (cursor !== null || new Set(all.map(item => item.member_id)).size !== all.length) throw Error("成员列表不完整或存在重复");
    if (!mounted || run !== generation || !manager() || actorAtStart !== actor()) return;
    eligible.value = Object.freeze(all.filter(item => item.state === "ACTIVE"
      && (item.role === "CUSTOMER_MANAGER" || item.role === "CUSTOMER_MEMBER"))
      .sort((a, b) => a.user.display_name.localeCompare(b.user.display_name, "zh-CN")));
    const allowed = new Set(eligible.value.map(item => item.user.user_id)); selected.value = selected.value.filter(id => allowed.has(id));
    loaded.value = true; confirmed.value = false;
  } catch (failure) {
    if (mounted && run === generation) { eligible.value = []; loaded.value = false;
      error.value = failure instanceof Error ? failure.message : "暂时无法读取完整的当前项目评审人。"; }
  } finally { if (mounted && run === generation) busy.value = false; }
}
async function send() {
  if (!manager() || !session.canSubmit || busy.value || sending.value || locked.value || !current.value) return;
  const project = projectId(), plan = planId(), version = versionId(), actorAtStart = actor(), run = generation;
  let attempt = pending.value;
  if (attempt) {
    if (!retryConfirmed.value || attempt.actor !== actorAtStart || attempt.project !== project
      || attempt.plan !== plan || attempt.version !== version) return;
  } else {
    if (!ready() || !loaded.value || !confirmed.value || selected.value.length < 1 || selected.value.length > 32) return;
    const allowed = new Set(eligible.value.map(item => item.user.user_id));
    if (selected.value.some(id => !allowed.has(id)) || new Set(selected.value).size !== selected.value.length) return;
    attempt = { actor: actorAtStart, project, plan, version, reviewer_ids: Object.freeze([...selected.value].sort()),
      key: `plan-review-${crypto.randomUUID()}` };
    try {
      const encoded = JSON.stringify(attempt); window.sessionStorage.setItem(storageKey(), encoded);
      if (window.sessionStorage.getItem(storageKey()) !== encoded) throw Error(); pending.value = attempt;
    } catch { error.value = "无法安全保存原评审人集合和操作号；本次未送审。"; return; }
  }
  sending.value = true; retryConfirmed.value = false; error.value = "";
  try {
    const result = await submitter.submitReview(project, plan, version, attempt.reviewer_ids, attempt.key);
    if (!mounted || run !== generation || project !== projectId() || plan !== planId() || version !== versionId()
      || actorAtStart !== actor()) return;
    if (result.submitted_by !== actorAtStart || result.project_id !== project || result.plan_id !== plan
      || result.plan_version_id !== version || result.state !== "IN_REVIEW") {
      locked.value = true; error.value = "送审回执与当前固定版本不一致；请核对评审记录和审计。"; return;
    }
    receipt.value = result;
    try {
      if (window.sessionStorage.getItem(storageKey()) !== JSON.stringify(attempt)) throw Error();
      window.sessionStorage.removeItem(storageKey()); pending.value = null;
    } catch { locked.value = true; error.value = "送审回执已收到，但原操作记录无法安全清理；请勿重复提交。"; }
  } catch (failure) {
    if (!mounted || run !== generation) return;
    if (failure instanceof PlanVersionWriteError) {
      error.value = failure.message;
      if (failure.code === "CONFLICT_IDEMPOTENCY") locked.value = true;
      else if (!failure.uncertain) {
        try { window.sessionStorage.removeItem(storageKey()); pending.value = null; }
        catch { locked.value = true; }
        eligible.value = []; selected.value = []; loaded.value = false; confirmed.value = false;
      }
    } else error.value = "送审结果无法确认；请保留原评审人集合和操作号。";
  } finally { if (mounted && run === generation) sending.value = false; }
}
const unsubscribe = session.subscribe(() => {
  generation++; receipt.value = null; retryConfirmed.value = false; current.value = null;
  loading.value = false; busy.value = false; sending.value = false;
  if (pending.value) { locked.value = true; error.value = "会话已变化；请核对原送审结果，勿更换操作号。"; }
  else { eligible.value = []; loaded.value = false; selected.value = []; }
});
watch(() => [route.params.projectId, route.params.planId, route.params.versionId], () => { void load(); }, { immediate: true });
onUnmounted(() => { mounted = false; generation++; unsubscribe(); });
</script>

<template><section class="plan-version-submit-review" aria-labelledby="plan-version-review-title" :aria-busy="loading || busy || sending">
  <p class="section-kicker">项目实施</p><h1 id="plan-version-review-title">提交计划版本评审</h1>
  <p class="warning">送审会创建评审并将固定版本置为 IN_REVIEW；这不是批准或客户签署。服务器会在同一事务重新检查版本、现时来源、Validate readiness及评审人资格。</p>
  <p><RouterLink :to="{ name: 'project-plan-version-detail', params: { projectId: route.params.projectId, planId: route.params.planId, versionId: route.params.versionId } }">返回固定版本</RouterLink></p>
  <p v-if="!session.view" role="status">尚未读取当前身份，请先登录。</p><p v-else-if="session.view.password_change_required" role="status">当前账户须先修改密码。</p>
  <p v-else-if="!manager()" role="status">仅当前项目负责人可以提交正式评审。</p>
  <template v-else><p v-if="loading" role="status">正在读取固定计划版本…</p><p v-if="busy" role="status">正在读取完整的项目成员历史…</p>
    <p v-if="error" role="alert">{{ error }}</p><p v-if="!session.canSubmit" role="status">当前会话仅可查看，请重新登录后再送审。</p>
    <p v-if="pending" role="status">原送审结果未确认；评审人集合和操作号已保留，请先核对评审记录。</p>
    <label v-if="pending"><input v-model="retryConfirmed" type="checkbox" :disabled="sending || locked" />我已核对评审记录，按原评审人集合和操作号重试</label>
    <template v-else-if="ready()"><h2>固定版本 {{ current!.version_no }} · DRAFT</h2>
      <button type="button" :disabled="busy || sending || locked" @click="loadReviewers">{{ loaded ? "重新读取项目评审人" : "读取项目评审人" }}</button>
      <fieldset v-if="eligible.length" :disabled="sending || busy"><legend>选择当前活动的客户评审人（最多32人）</legend>
        <label v-for="member in eligible" :key="member.member_id"><input v-model="selected" type="checkbox" :value="member.user.user_id"
          :disabled="selected.length >= 32 && !selected.includes(member.user.user_id)" />{{ member.user.display_name }}（{{ member.role === "CUSTOMER_MANAGER" ? "客户经理" : "客户成员" }}）</label>
      </fieldset><p v-else-if="loaded" role="status">没有可选择的活动客户评审人。</p>
      <label v-if="loaded && eligible.length"><input v-model="confirmed" type="checkbox" :disabled="sending" />我已核对这个固定版本和所选评审人，确认提交；送审不代表批准</label>
      <button type="button" :disabled="busy || sending || locked || !session.canSubmit || !loaded || !confirmed || selected.length < 1 || selected.length > 32" @click="send">{{ sending ? "正在送审…" : "确认提交正式评审" }}</button>
    </template><p v-else-if="current && !receipt && !pending" role="status">此固定版本不是尚未送审的草稿；请返回查看版本状态。</p>
    <button v-if="pending" type="button" :disabled="sending || busy || locked || !session.canSubmit || !retryConfirmed" @click="send">{{ sending ? "正在送审…" : "按原操作号重试送审" }}</button>
    <p v-if="receipt" role="status">已进入正式评审 {{ receipt.review_id }}（第1轮 {{ receipt.review_round_id }}）；尚未批准。
      <RouterLink :to="{ name: 'project-review-detail', params: { projectId: receipt.project_id, reviewId: receipt.review_id } }">打开评审</RouterLink></p>
  </template>
</section></template>

<style scoped>.plan-version-submit-review{max-width:56rem;margin:1rem auto;padding:1.5rem;background:#fff;border-radius:1rem}.warning{padding:.8rem 1rem;border-left:.3rem solid #d29b42;background:#fff8e9}.plan-version-submit-review fieldset{display:grid;gap:.55rem;margin:.8rem 0;padding:1rem}.plan-version-submit-review fieldset label{display:flex;gap:.5rem}.plan-version-submit-review [role=alert]{color:#a21d25}</style>
