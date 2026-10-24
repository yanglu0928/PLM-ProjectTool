<script setup lang="ts">
import { onMounted, ref, toRaw } from "vue";
import { RouterLink } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { ProjectMemberReadClient, type ProjectMemberView } from
  "@/modules/project/api/projectMemberReadClient";
import type { OutlineVersionDetail } from "@/modules/solution/api/outlineVersionReadClient";
import { OutlineVersionSubmitReviewClient, OutlineReviewSubmitError,
  type OutlineReviewSubmission } from
  "@/modules/solution/api/outlineVersionSubmitReviewClient";

const props = defineProps<{ session: SessionClient; detail: OutlineVersionDetail;
  members?: ProjectMemberReadClient; submitter?: OutlineVersionSubmitReviewClient }>();
const session = toRaw(props.session);
const members = toRaw(props.members ?? new ProjectMemberReadClient());
const submitter = toRaw(props.submitter ?? new OutlineVersionSubmitReviewClient(session));
const available = ref<readonly ProjectMemberView[]>([]);
const selected = ref<string[]>([]);
const busy = ref(false); const sending = ref(false);
const error = ref(""); const submitted = ref<OutlineReviewSubmission | null>(null);
const confirmScope = ref(false); const confirmRetry = ref(false); const locked = ref(false);
type Attempt = { actor: string; project: string; outline: string; version: string;
  reviewer_ids: readonly string[]; key: string };
const pending = ref<Attempt | null>(null);
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const manager = () => !!session.view && !session.view.password_change_required
  && session.canSubmit && session.view.authorized_projects.some(item =>
    item.project_id === props.detail.project_id && item.role === "PROJECT_MANAGER");
const key = () => `plm.sol.outline.review.pending.${session.view?.user.user_id ?? "none"}`
  + `.${props.detail.project_id}.${props.detail.solution_outline_id}`
  + `.${props.detail.solution_outline_version_id}`;
function restore() {
  if (!manager()) return;
  try {
    const raw = sessionStorage.getItem(key()); if (!raw) return;
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error();
    const item = value as Record<string, unknown>, ids = item.reviewer_ids;
    if (item.actor !== session.view!.user.user_id
      || item.project !== props.detail.project_id
      || item.outline !== props.detail.solution_outline_id
      || item.version !== props.detail.solution_outline_version_id
      || !Array.isArray(ids) || ids.length < 1 || ids.length > 32
      || ids.some(value => typeof value !== "string" || !uuid.test(value))
      || new Set(ids).size !== ids.length || typeof item.key !== "string"
      || !/^[\x20-\x7e]{16,128}$/.test(item.key)) throw new Error();
    pending.value = item as Attempt;
  } catch {
    locked.value = true;
    error.value = "原送审操作记录无法读取，已停止再次提交；请核对评审与审计记录。";
  }
}
async function loadMembers() {
  if (!manager()) return;
  busy.value = true;
  try {
    const all: ProjectMemberView[] = [], cursors = new Set<string>();
    let cursor: string | null = null;
    for (let page = 0; page < 20; page += 1) {
      const result = await members.list(props.detail.project_id, cursor);
      all.push(...result.items);
      if (!result.has_more) { cursor = null; break; }
      if (!result.next_cursor || cursors.has(result.next_cursor)) throw new Error("成员翻页无效");
      cursors.add(result.next_cursor); cursor = result.next_cursor;
    }
    if (cursor !== null || new Set(all.map(item => item.member_id)).size !== all.length) {
      throw new Error("成员列表不完整");
    }
    available.value = Object.freeze(all.filter(item => item.state === "ACTIVE"
      && (item.role === "CUSTOMER_MANAGER" || item.role === "CUSTOMER_MEMBER"))
      .sort((a, b) => a.user.display_name.localeCompare(b.user.display_name, "zh-CN")));
  } catch (failure) {
    available.value = [];
    error.value = failure instanceof Error ? failure.message : "暂时无法读取客户确认人。";
  } finally { busy.value = false; }
}
function ready() {
  const detail = props.detail;
  return manager() && !pending.value && !submitted.value && detail.version_state === "DRAFT"
    && detail.review_ref === null && detail.review_round_ref === null;
}
async function submit() {
  if (!manager() || busy.value || sending.value || locked.value) return;
  const actor = session.view!.user.user_id, detail = props.detail;
  let attempt = pending.value;
  if (attempt) {
    if (!confirmRetry.value || attempt.actor !== actor
      || attempt.project !== detail.project_id
      || attempt.outline !== detail.solution_outline_id
      || attempt.version !== detail.solution_outline_version_id) return;
  } else {
    if (!ready() || !confirmScope.value || !selected.value.length) return;
    attempt = { actor, project: detail.project_id,
      outline: detail.solution_outline_id,
      version: detail.solution_outline_version_id,
      reviewer_ids: Object.freeze([...selected.value].sort()),
      key: `outline-review-${crypto.randomUUID()}` };
    try { sessionStorage.setItem(key(), JSON.stringify(attempt)); }
    catch { error.value = "无法保存原操作号，本次未发送送审。"; return; }
    pending.value = attempt;
  }
  sending.value = true; confirmRetry.value = false; error.value = "";
  try {
    const result = await submitter.submit(attempt.project, attempt.outline,
      attempt.version, attempt.reviewer_ids, attempt.key);
    if (result.submitted_by !== actor || result.project_id !== detail.project_id
      || result.solution_outline_id !== detail.solution_outline_id
      || result.solution_outline_version_id !== detail.solution_outline_version_id) {
      locked.value = true; error.value = "送审回执与当前大纲不一致；请核对审计记录。"; return;
    }
    submitted.value = result;
    try { sessionStorage.removeItem(key()); pending.value = null; }
    catch { locked.value = true; error.value = "送审回执已收到，但原操作号清理失败；请勿再次提交。"; }
  } catch (failure) {
    const known = failure instanceof OutlineReviewSubmitError ? failure : null;
    error.value = known?.message ?? "送审结果无法确认；请保留原操作号。";
    if (known?.code === "CONFLICT_IDEMPOTENCY") locked.value = true;
    else if (known && !known.uncertain) {
      try { sessionStorage.removeItem(key()); pending.value = null; }
      catch { locked.value = true; }
    }
  } finally { sending.value = false; }
}
onMounted(() => { restore(); void loadMembers(); });
</script>

<template>
  <section class="outline-review" aria-labelledby="outline-review-title" :aria-busy="busy || sending">
    <h3 id="outline-review-title">客户方案大纲评审</h3>
    <p v-if="detail.review_ref">评审 {{ detail.review_ref }}，轮次 {{ detail.review_round_ref }}。
      <RouterLink :to="{ name: 'project-review-detail', params: {
        projectId: detail.project_id, reviewId: detail.review_ref } }">打开评审</RouterLink></p>
    <p v-if="!manager()" role="status">仅当前项目负责人可送审；客户确认人须在评审待办中独立作决定。</p>
    <template v-else>
      <p class="notice">只选择当前项目客户确认人。服务端会在送审时重新核查固定来源、覆盖与确认人资格；页面核对不代表来源验证，送审不等于客户批准或签署。</p>
      <p v-if="busy" role="status">正在读取客户确认人…</p>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="pending" role="status">原送审结果未确认，客户确认人：{{ pending.reviewer_ids.join('、') }}。请保持原操作号和原确认人。</p>
      <label v-if="pending"><input v-model="confirmRetry" type="checkbox" :disabled="sending || locked"> 我已核对评审记录，按原内容和操作号重试</label>
      <template v-else-if="ready()">
        <fieldset v-if="available.length" :disabled="sending">
          <legend>选择客户确认人（最多 32 人）</legend>
          <label v-for="item in available" :key="item.member_id"><input v-model="selected" type="checkbox"
            :value="item.user.user_id" :disabled="selected.length >= 32 && !selected.includes(item.user.user_id)">
            {{ item.user.display_name }}（{{ item.role }}）</label>
        </fieldset>
        <p v-else role="status">当前没有可选择的合格客户确认人。</p>
        <label><input v-model="confirmScope" type="checkbox" :disabled="sending">
          我已核对本固定方案大纲版本与拟送审范围；理解服务端会重新验证当前来源</label>
      </template>
      <p v-else-if="!submitted" role="status">当前版本不是未送审草稿；请刷新或查看已有评审。</p>
      <button v-if="pending || ready()" type="button" :disabled="sending || busy || locked
        || (pending ? !confirmRetry : !confirmScope || !selected.length)" @click="submit()">
        {{ sending ? '正在送审…' : pending ? '按原操作号重试送审' : '提交客户方案大纲评审' }}
      </button>
      <p v-if="submitted" role="status">已送审，评审 {{ submitted.review_id }}，首轮 {{ submitted.review_round_id }}；这不是批准。
        <RouterLink :to="{ name: 'project-review-detail', params: {
          projectId: submitted.project_id, reviewId: submitted.review_id } }">打开评审</RouterLink></p>
    </template>
  </section>
</template>

<style scoped>
.outline-review{margin-top:1rem;padding:1rem;border:1px solid #d8dee7;border-radius:.75rem}
.outline-review label{display:block;margin:.55rem 0}.outline-review button{margin:.6rem 0}
.notice{padding:.8rem;border-left:.3rem solid #d29b42;background:#fff8e9}
.outline-review [role=alert]{color:#a21d25}
</style>
