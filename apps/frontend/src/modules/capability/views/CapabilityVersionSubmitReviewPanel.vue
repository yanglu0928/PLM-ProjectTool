<script setup lang="ts">
import { onMounted, onUnmounted, ref, shallowRef, toRaw } from "vue";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { AdminUserListClient, type UserCandidate } from "@/modules/auth/api/adminUserListClient";
import type { CapabilityVersion } from "@/modules/capability/api/capabilityReadClient";
import { CapabilityVersionSubmitReviewClient, CapabilityReviewSubmitError,
  type CapabilityReviewSubmission } from "@/modules/capability/api/capabilityVersionSubmitReviewClient";

const props = defineProps<{ version: CapabilityVersion; session: SessionClient;
  users?: AdminUserListClient; submitter?: CapabilityVersionSubmitReviewClient }>();
const session = toRaw(props.session);
const users = toRaw(props.users ?? new AdminUserListClient());
const submitter = toRaw(props.submitter ?? new CapabilityVersionSubmitReviewClient(session));
const actorId = session.view?.user.user_id;
type Pending = { readonly actor: string; readonly baselineId: string; readonly versionId: string;
  readonly reviewerIds: readonly string[]; readonly key: string };
const available = shallowRef<readonly UserCandidate[]>([]);
const cursor = ref<string | null>(null); const selected = ref<string[]>([]);
const pending = shallowRef<Pending | null>(null);
const submitted = shallowRef<CapabilityReviewSubmission | null>(null);
const confirmScope = ref(false); const confirmRetry = ref(false);
const loading = ref(false); const sending = ref(false); const locked = ref(false);
const error = ref(""); let mounted = true; let generation = 0;
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
function canSubmit(): boolean {
  const current = session.view;
  return mounted && !!actorId && current?.user.user_id === actorId && !current.password_change_required
    && current.deployment_role === "DEPLOYMENT_ADMIN" && session.canSubmit
    && props.version.state === "DRAFT" && props.version.review_ref === null
    && props.version.review_round_ref === null;
}
function storageKey(): string {
  return `plm.cap.version.review.pending.${actorId ?? "none"}.${props.version.baseline_version_id}`;
}
function restore(): void {
  if (!actorId) return;
  try {
    const raw = window.sessionStorage.getItem(storageKey()); if (!raw) return;
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("invalid");
    const item = value as Record<string, unknown>; const ids = item.reviewerIds;
    if (Object.keys(item).length !== 5 || item.actor !== actorId
      || item.baselineId !== props.version.baseline_id || item.versionId !== props.version.baseline_version_id
      || !Array.isArray(ids) || ids.length < 1 || ids.length > 32
      || ids.some(value => typeof value !== "string" || !uuid.test(value))
      || new Set(ids).size !== ids.length || [...ids].sort().some((id, index) => id !== ids[index])
      || typeof item.key !== "string" || !/^[\x20-\x7e]{16,128}$/.test(item.key)) throw new Error("invalid");
    pending.value = item as Pending;
  } catch { locked.value = true; error.value = "原送审记录无法安全读取；请核对评审与审计，勿换号提交。"; }
}
function clearPending(attempt: Pending): boolean {
  try {
    if (window.sessionStorage.getItem(storageKey()) !== JSON.stringify(attempt)) throw new Error("changed");
    window.sessionStorage.removeItem(storageKey()); pending.value = null; return true;
  } catch { locked.value = true; error.value = "无法清除原送审操作记录；请核对评审与审计。"; return false; }
}
async function load(): Promise<void> {
  if (!canSubmit() || loading.value || !mounted || cursor.value === "") return;
  const current = cursor.value; const request = generation; loading.value = true; error.value = "";
  try {
    const page = await users.page(current);
    if (!mounted || request !== generation || !canSubmit()) return;
    if (new Set([...available.value, ...page.items].map(item => item.user_id)).size
      !== available.value.length + page.items.length) throw new Error("用户分页重复，请刷新。 ");
    available.value = [...available.value, ...page.items.filter(item =>
      item.account_state === "ENABLED")];
    cursor.value = page.next_cursor ?? "";
  } catch (failure) { if (mounted && request === generation) error.value = failure instanceof Error
    ? failure.message : "暂时无法读取管理员名单。"; }
  finally { if (mounted && request === generation) loading.value = false; }
}
function ready(): boolean {
  return canSubmit() && !pending.value && !submitted.value && !loading.value && !sending.value
    && !locked.value && selected.value.length >= 1 && selected.value.length <= 32
    && selected.value.every(id => available.value.some(item => item.user_id === id)) && confirmScope.value;
}
async function submit(): Promise<void> {
  if (!canSubmit() || sending.value || loading.value || locked.value) return;
  let attempt = pending.value;
  if (attempt) {
    if (!confirmRetry.value) return;
  } else {
    if (!ready()) return;
    attempt = { actor: actorId!, baselineId: props.version.baseline_id,
      versionId: props.version.baseline_version_id,
      reviewerIds: Object.freeze([...selected.value].sort()),
      key: `capability-version-review-${crypto.randomUUID()}` };
    try {
      const encoded = JSON.stringify(attempt); window.sessionStorage.setItem(storageKey(), encoded);
      if (window.sessionStorage.getItem(storageKey()) !== encoded) throw new Error("write");
      pending.value = attempt;
    } catch { error.value = "无法安全保存原送审操作号，本次未发送。"; return; }
  }
  if (attempt.actor !== actorId || attempt.baselineId !== props.version.baseline_id
    || attempt.versionId !== props.version.baseline_version_id) { locked.value = true; return; }
  sending.value = true; confirmRetry.value = false; error.value = "";
  try {
    const result = await submitter.submit(props.version, attempt.reviewerIds, attempt.key);
    if (!mounted || !canSubmit()) return;
    submitted.value = result;
    clearPending(attempt);
  } catch (failure) {
    if (!mounted) return;
    const known = failure instanceof CapabilityReviewSubmitError ? failure : null;
    if (known?.code === "CONFLICT_IDEMPOTENCY") locked.value = true;
    else if (known && !known.uncertain) clearPending(attempt);
    error.value = known?.message ?? "送审结果无法确认；请保留原操作号。";
  } finally { if (mounted) sending.value = false; }
}
const unsubscribe = session.subscribe(() => {
  generation += 1; available.value = []; cursor.value = null; selected.value = [];
  confirmScope.value = false; confirmRetry.value = false;
  if (pending.value || sending.value) error.value = "会话已变化；请核对原送审结果，勿换号重试。";
});
onMounted(() => { restore(); void load(); });
onUnmounted(() => { mounted = false; generation += 1; unsubscribe(); });
</script>

<template>
  <section v-if="canSubmit()" aria-label="能力版本正式送审" :aria-busy="loading || sending">
    <h4>正式送审</h4>
    <p>选择已启用用户作为本轮评审人；服务端会重验当前版本、来源和资格。送审只进入评审，不等于批准。</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="loading" role="status">正在读取评审候选人…</p>
    <template v-if="submitted">
      <p role="status">已进入评审：{{ submitted.review_id }}，轮次 {{ submitted.review_round_id }}。请刷新版本详情查看状态；尚未批准。</p>
    </template>
    <template v-else-if="pending">
      <p role="status">原送审结果未确认，评审人 {{ pending.reviewerIds.join('、') }}；请先核对评审与审计记录。</p>
      <label><input v-model="confirmRetry" type="checkbox" :disabled="sending || locked" /> 已核对历史，按原评审人与操作号重试</label>
      <button type="button" :disabled="sending || loading || locked || !confirmRetry" @click="submit">按原操作号重试送审</button>
    </template>
    <template v-else>
      <fieldset v-if="available.length" :disabled="sending || locked">
        <legend>选择已启用评审人（最多 32 人）</legend>
        <label v-for="item in available" :key="item.user_id">
          <input v-model="selected" type="checkbox" :value="item.user_id"
            :disabled="selected.length >= 32 && !selected.includes(item.user_id)" />
          {{ item.username_display }}
        </label>
      </fieldset>
      <p v-else-if="!loading" role="status">当前列表没有可选的已启用用户。</p>
      <button v-if="cursor && cursor !== ''" type="button" :disabled="loading || locked" @click="load">加载更多候选人</button>
      <label><input v-model="confirmScope" type="checkbox" :disabled="sending || locked" />
        我已核对当前 DRAFT 和评审人；理解服务端将重新校验，送审不是批准</label>
      <button type="button" :disabled="!ready()" @click="submit">提交正式评审</button>
    </template>
  </section>
</template>
