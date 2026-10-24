<script setup lang="ts">
import { inject, onMounted, onUnmounted, ref, toRaw } from "vue";
import { RouterLink } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { ProjectMemberReadClient, type ProjectMemberView } from "@/modules/project/api/projectMemberReadClient";
import type { HandoverAnalysisVersionView } from "@/modules/handover/api/handoverReadClient";
import { HandoverVersionSubmitReviewClient, HandoverSubmitReviewError,
  type HandoverReviewSubmission } from "@/modules/handover/api/handoverVersionSubmitReviewClient";

const props = defineProps<{ version: HandoverAnalysisVersionView; session?: SessionClient;
  members?: ProjectMemberReadClient; submitter?: HandoverVersionSubmitReviewClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const members = toRaw(props.members ?? new ProjectMemberReadClient());
const submitter = toRaw(props.submitter ?? new HandoverVersionSubmitReviewClient(session));
const actorId = session.view?.user.user_id;
const available = ref<readonly ProjectMemberView[]>([]); const selected = ref<string[]>([]);
const loaded = ref(false);
const busy = ref(false); const sending = ref(false); const error = ref("");
const submitted = ref<HandoverReviewSubmission | null>(null);
const confirmScope = ref(false); const confirmRetry = ref(false); const locked = ref(false);
type Attempt = { actor: string; project: string; analysis: string; version: string;
  reviewer_ids: readonly string[]; key: string };
const pending = ref<Attempt | null>(null);
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
let mounted = true;
function manager(): boolean { const current = session.view;
  return mounted && !!actorId && current?.user.user_id === actorId
    && !current.password_change_required
    && current.authorized_projects.some(item => item.project_id === props.version.project_id
      && item.role === "PROJECT_MANAGER");
}
function storageKey(): string { const value = props.version;
  return `plm.hnd.version.review.pending.${actorId ?? "none"}.${value.project_id}.${value.handover_analysis_id}.${value.handover_analysis_version_id}`;
}
function restore(): void {
  if (!manager()) return;
  try {
    const raw = sessionStorage.getItem(storageKey()); if (!raw) return;
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("invalid");
    const item = value as Record<string, unknown>, ids = item.reviewer_ids, version = props.version;
    if (Object.keys(item).length !== 6 || item.actor !== actorId || item.project !== version.project_id
      || item.analysis !== version.handover_analysis_id || item.version !== version.handover_analysis_version_id
      || !Array.isArray(ids) || ids.length < 1 || ids.length > 32
      || ids.some(value => typeof value !== "string" || !uuid.test(value))
      || new Set(ids).size !== ids.length || typeof item.key !== "string"
      || !/^[\x20-\x7e]{16,128}$/.test(item.key)) throw new Error("invalid");
    pending.value = item as Attempt;
  } catch { locked.value = true; error.value = "原送审记录无法安全读取；请核对评审与审计，勿换号重试。"; }
}
async function loadMembers(): Promise<void> {
  if (!manager() || busy.value || sending.value || pending.value) return;
  busy.value = true; if (!locked.value) error.value = "";
  try {
    const all: ProjectMemberView[] = [], cursors = new Set<string>();
    let cursor: string | null = null;
    for (let page = 0; page < 20; page += 1) {
      const result = await members.list(props.version.project_id, cursor);
      all.push(...result.items);
      if (!result.has_more) { cursor = null; break; }
      if (!result.next_cursor || cursors.has(result.next_cursor)) throw new Error("成员翻页无效");
      cursors.add(result.next_cursor); cursor = result.next_cursor;
    }
    if (cursor !== null || new Set(all.map(item => item.member_id)).size !== all.length) {
      throw new Error("成员列表不完整");
    }
    if (!mounted || !manager()) return;
    available.value = Object.freeze(all.filter(item => item.state === "ACTIVE"
      && (item.role === "CUSTOMER_MANAGER" || item.role === "CUSTOMER_MEMBER"))
      .sort((a, b) => a.user.display_name.localeCompare(b.user.display_name, "zh-CN")));
    const allowed = new Set(available.value.map(item => item.user.user_id));
    selected.value = selected.value.filter(id => allowed.has(id)); confirmScope.value = false;
    loaded.value = true;
  } catch (failure) {
    if (!mounted) return; available.value = []; loaded.value = false;
    if (!locked.value) error.value = failure instanceof Error ? failure.message : "暂时无法读取客户确认人。";
  } finally { if (mounted) busy.value = false; }
}
function ready(): boolean { const value = props.version;
  return manager() && !pending.value && !submitted.value && value.state === "DRAFT"
    && value.review_ref === null && value.review_round_ref === null;
}
async function submit(): Promise<void> {
  if (!manager() || !session.canSubmit || busy.value || sending.value || locked.value) return;
  const actor = session.view!.user.user_id, version = props.version;
  let attempt = pending.value;
  if (attempt) {
    if (!confirmRetry.value || attempt.actor !== actor || attempt.project !== version.project_id
      || attempt.analysis !== version.handover_analysis_id
      || attempt.version !== version.handover_analysis_version_id) return;
  } else {
    if (!ready() || !loaded.value || !confirmScope.value || !selected.value.length) return;
    const allowed = new Set(available.value.map(item => item.user.user_id));
    if (selected.value.length > 32 || selected.value.some(id => !allowed.has(id))) return;
    attempt = { actor, project: version.project_id, analysis: version.handover_analysis_id,
      version: version.handover_analysis_version_id,
      reviewer_ids: Object.freeze([...selected.value].sort()),
      key: `handover-review-${crypto.randomUUID()}` };
    try {
      const encoded = JSON.stringify(attempt); sessionStorage.setItem(storageKey(), encoded);
      if (sessionStorage.getItem(storageKey()) !== encoded) throw new Error("write");
      pending.value = attempt;
    } catch { error.value = "无法保存原操作号，本次未发送送审。"; return; }
  }
  sending.value = true; confirmRetry.value = false; error.value = "";
  try {
    const result = await submitter.submit(version, attempt.reviewer_ids, attempt.key);
    if (!mounted || !manager()) return;
    if (result.submitted_by !== actor || result.project_id !== version.project_id
      || result.handover_analysis_id !== version.handover_analysis_id
      || result.handover_analysis_version_id !== version.handover_analysis_version_id) {
      locked.value = true; error.value = "送审回执与当前交接版本不一致；请核对审计。"; return;
    }
    submitted.value = result;
    try {
      if (sessionStorage.getItem(storageKey()) !== JSON.stringify(attempt)) throw new Error("changed");
      sessionStorage.removeItem(storageKey()); pending.value = null;
    } catch { locked.value = true; error.value = "送审回执已收到，但原操作号清理失败；请勿再次提交。"; }
  } catch (failure) {
    if (!mounted) return;
    const known = failure instanceof HandoverSubmitReviewError ? failure : null;
    error.value = known?.message ?? "送审结果无法确认；请保留原操作号。";
    if (known?.code === "CONFLICT_IDEMPOTENCY") locked.value = true;
    else if (known && !known.uncertain) {
      try { sessionStorage.removeItem(storageKey()); pending.value = null; }
      catch { locked.value = true; }
    }
  } finally { if (mounted) sending.value = false; }
}
const unsubscribe = session.subscribe(() => {
  submitted.value = null; confirmRetry.value = false;
  if (sending.value || pending.value) error.value = "会话已变化；请核对原送审结果，勿换号重试。";
});
onMounted(restore);
onUnmounted(() => { mounted = false; unsubscribe(); });
</script>

<template>
  <section v-if="manager()" aria-label="交接版本客户评审送审" :aria-busy="busy || sending">
    <h3>提交交接问题给客户确认人评审</h3>
    <p>仅送审当前固定 DRAFT 版本；校验通过也不保证此刻来源或资格仍有效。服务端会重新核对来源、问题、Action 和确认人。送审不是客户批准或签署。</p>
    <p v-if="!session.canSubmit && !sending" role="status">当前会话仅可查看；请重新登录后再送审。</p>
    <p v-if="version.review_ref">现有评审 {{ version.review_ref }}；请在评审待办中查看进展。</p>
    <p v-if="busy" role="status">正在读取当前项目确认人…</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="pending" role="status">原送审结果未确认；确认人集合与操作号已保留，请先核对评审记录。</p>
    <label v-if="pending"><input v-model="confirmRetry" type="checkbox" :disabled="sending || locked" />我已核对评审记录，按原确认人和操作号重试</label>
    <template v-else-if="ready()">
      <button type="button" :disabled="busy || sending || locked" @click="loadMembers()">
        {{ loaded ? '刷新当前项目确认人' : '读取当前项目确认人' }}</button>
      <fieldset v-if="available.length" :disabled="sending">
        <legend>选择当前项目客户确认人（最多 32 人）</legend>
        <label v-for="item in available" :key="item.member_id"><input v-model="selected" type="checkbox"
          :value="item.user.user_id" :disabled="selected.length >= 32 && !selected.includes(item.user.user_id)" />
          {{ item.user.display_name }}（{{ item.role }}）</label>
      </fieldset>
      <p v-else role="status">{{ loaded ? '当前没有可选择的合格客户确认人。' : '请先读取当前项目确认人；未完整读取时不能送审。' }}</p>
      <label><input v-model="confirmScope" type="checkbox" :disabled="sending" />
        我已核对本固定版本、问题卡片与拟送审范围，理解这不是客户确认</label>
    </template>
    <p v-else-if="!submitted" role="status">当前版本不是未送审草稿；请刷新详情或查看已有评审。</p>
    <button v-if="pending || ready()" type="button" :disabled="sending || busy || locked || !session.canSubmit
      || (pending ? !confirmRetry : !loaded || !confirmScope || !selected.length)" @click="submit()">
      {{ sending ? '正在送审…' : pending ? '按原操作号重试送审' : '提交交接版本评审' }}
    </button>
    <p v-if="submitted" role="status">已送审，评审 {{ submitted.review_id }}，首轮 {{ submitted.review_round_id }}；这不是批准。
      <RouterLink :to="{ name: 'project-review-detail', params: { projectId: submitted.project_id,
        reviewId: submitted.review_id } }">打开评审</RouterLink></p>
  </section>
</template>
