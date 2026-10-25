<script setup lang="ts">
import { computed, inject, onMounted, onUnmounted, ref, shallowRef, toRaw, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import { GlobalCapabilityReviewClient, GlobalReviewError, type GlobalCapabilityReview,
  type GlobalReviewDecisionKind, type GlobalReviewDecisionReceipt } from "@/modules/capability/api/globalCapabilityReviewClient";
import type { CapabilityItem, CapabilityVersion } from "@/modules/capability/api/capabilityReadClient";

const props = defineProps<{ session?: SessionClient; reviews?: GlobalCapabilityReviewClient }>();
const session = toRaw(props.session ?? inject(sessionClientKey, null) ?? new SessionClient());
const reviews = toRaw(props.reviews ?? new GlobalCapabilityReviewClient(session));
const route = useRoute();
const review = shallowRef<GlobalCapabilityReview | null>(null);
const version = shallowRef<CapabilityVersion | null>(null);
const items = shallowRef<readonly CapabilityItem[]>([]);
const receipt = shallowRef<GlobalReviewDecisionReceipt | null>(null);
const busy = ref(false); const deciding = ref(false); const locked = ref(false);
const error = ref(""); const decisionError = ref("");
const confirmScope = ref(false); const confirmRetry = ref(false); const returnComment = ref("");
type Pending = { actor: string; baseline: string; version: string; review: string; round: string;
  decision: GlobalReviewDecisionKind; comment: string | null; key: string };
const pending = shallowRef<Pending | null>(null);
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
let mounted = true; let generation = 0;
const baselineId = () => typeof route.params.baselineId === "string" ? route.params.baselineId : "";
const versionId = () => typeof route.params.versionId === "string" ? route.params.versionId : "";
const reviewId = () => typeof route.params.reviewId === "string" ? route.params.reviewId : "";
const actorId = () => session.view?.user.user_id ?? "";
const mayRead = () => mounted && !!session.view && !session.view.password_change_required
  && [baselineId(), versionId(), reviewId()].every(value => uuid.test(value));
const assigned = computed(() => !!review.value?.reviewer_ids.includes(actorId()));
const alreadyDecided = computed(() => !!review.value?.decisions.some(value => value.reviewer_id === actorId()));
const ready = computed(() => !busy.value && !deciding.value && !locked.value && !pending.value
  && !!review.value && !!version.value && items.value.length === version.value.declared_item_count
  && review.value.state === "IN_REVIEW" && assigned.value && !alreadyDecided.value
  && session.canSubmit && confirmScope.value);
function storageKey() { return `plm.cap.global.review.decision.${actorId()}.${reviewId()}`; }
function validPending(value: unknown): value is Pending {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const item = value as Record<string, unknown>;
  return Object.keys(item).length === 8 && item.actor === actorId()
    && item.baseline === baselineId() && item.version === versionId() && item.review === reviewId()
    && typeof item.round === "string" && uuid.test(item.round)
    && ["APPROVE", "RETURN"].includes(String(item.decision))
    && (item.decision === "APPROVE" && item.comment === null
      || item.decision === "RETURN" && typeof item.comment === "string" && !!item.comment.trim())
    && typeof item.key === "string" && /^[\x20-\x7e]{16,128}$/.test(item.key);
}
function restore(): void {
  pending.value = null; confirmRetry.value = false; locked.value = false; decisionError.value = "";
  if (!mayRead()) return;
  try {
    const raw = window.sessionStorage.getItem(storageKey()); if (!raw) return;
    const value: unknown = JSON.parse(raw);
    if (!validPending(value)) throw new Error("invalid");
    pending.value = value;
  } catch { locked.value = true; decisionError.value = "原决定记录无法安全读取，已停止重试；请核对评审和审计。"; }
}
function clearPending(attempt: Pending): boolean {
  try {
    if (window.sessionStorage.getItem(storageKey()) !== JSON.stringify(attempt)) throw new Error("changed");
    window.sessionStorage.removeItem(storageKey()); pending.value = null; return true;
  } catch { locked.value = true; decisionError.value = "决定已处理，但原操作号无法清除；请核对评审和审计。"; return false; }
}
function reset(): void {
  generation += 1; review.value = null; version.value = null; items.value = []; receipt.value = null;
  busy.value = false; deciding.value = false; error.value = ""; returnComment.value = ""; confirmScope.value = false;
  restore();
}
async function load(): Promise<void> {
  if (!mayRead() || busy.value) return;
  const baseline = baselineId(), targetVersion = versionId(), targetReview = reviewId();
  const actor = actorId(), run = ++generation;
  busy.value = true; error.value = ""; review.value = null; version.value = null; items.value = [];
  try {
    const current = await reviews.read(targetReview, baseline, targetVersion);
    const fixed = await reviews.fixedVersion(current);
    const collected: CapabilityItem[] = []; const cursors = new Set<string>();
    let cursor: string | null = null;
    do {
      const page = await reviews.fixedItems(current, fixed, cursor);
      if (page.items.length === 0 && page.has_more) throw new Error("empty page");
      if (page.items.some(item => (collected.length > 0 && item.ordinal <= collected.at(-1)!.ordinal)
        || collected.some(previous => previous.capability_item_id === item.capability_item_id))) {
        throw new Error("crossed page");
      }
      collected.push(...page.items);
      if (collected.length > fixed.declared_item_count) throw new Error("overflow");
      cursor = page.next_cursor;
      if (cursor !== null) {
        if (cursors.has(cursor)) throw new Error("cursor loop");
        cursors.add(cursor);
      }
    } while (cursor !== null);
    if (collected.length !== fixed.declared_item_count || collected.length === 0) throw new Error("count");
    if (!mounted || run !== generation || actor !== actorId()
      || baseline !== baselineId() || targetVersion !== versionId() || targetReview !== reviewId()) return;
    if (pending.value && pending.value.round !== current.review_round_id) {
      locked.value = true; decisionError.value = "评审轮次已变化，已停止原决定重试；请核对审计。";
    }
    review.value = current; version.value = fixed; items.value = Object.freeze(collected);
  } catch (failure) {
    if (mounted && run === generation) error.value = failure instanceof GlobalReviewError
      ? failure.message : "固定评审内容未能完整核对，请刷新后再决定。";
  } finally { if (mounted && run === generation) busy.value = false; }
}
async function decide(kind: GlobalReviewDecisionKind): Promise<void> {
  if (!review.value || !version.value || busy.value || deciding.value || locked.value) return;
  const actor = actorId(); const before = review.value; const run = generation;
  let attempt = pending.value;
  if (attempt) {
    if (!confirmRetry.value || attempt.round !== before.review_round_id) return;
  } else {
    if (!ready.value || kind === "RETURN" && !returnComment.value.trim()) return;
    attempt = { actor, baseline: baselineId(), version: versionId(), review: reviewId(),
      round: before.review_round_id, decision: kind,
      comment: kind === "RETURN" ? returnComment.value.trim() : null,
      key: `cap-global-review-decision-${crypto.randomUUID()}` };
    try {
      const encoded = JSON.stringify(attempt); window.sessionStorage.setItem(storageKey(), encoded);
      if (window.sessionStorage.getItem(storageKey()) !== encoded) throw new Error("write");
      pending.value = attempt;
    } catch { decisionError.value = "无法保存原决定操作号，本次未发送。"; return; }
  }
  deciding.value = true; confirmRetry.value = false; decisionError.value = "";
  try {
    const replay = before.state !== "IN_REVIEW" || alreadyDecided.value;
    const result = await reviews.decide(before, attempt.decision, attempt.comment,
      attempt.key, replay);
    if (!mounted || run !== generation || actor !== actorId()) return;
    receipt.value = result;
    if (!clearPending(attempt)) return;
    deciding.value = false;
    await load();
    if (!review.value || review.value.review_etag !== result.review_etag
      || review.value.state !== result.state) {
      locked.value = true; decisionError.value = "决定回执与当前评审不一致；请核对审计记录。";
    } else { returnComment.value = ""; confirmScope.value = false; }
  } catch (failure) {
    if (!mounted || run !== generation) return;
    const known = failure instanceof GlobalReviewError ? failure : null;
    decisionError.value = known?.message ?? "决定结果无法确认；请保留原操作号。";
    if (known?.code === "CONFLICT_IDEMPOTENCY") locked.value = true;
    else if (known && !known.uncertain) clearPending(attempt);
  } finally { if (mounted && run === generation) deciding.value = false; }
}
const unsubscribe = session.subscribe(() => { reset(); if (mayRead()) void load(); });
watch(() => [route.params.baselineId, route.params.versionId, route.params.reviewId],
  () => { reset(); if (mayRead()) void load(); });
onMounted(() => { restore(); if (mayRead()) void load(); });
onUnmounted(() => { mounted = false; generation += 1; unsubscribe(); });
</script>

<template>
  <section class="page-panel" aria-label="标准能力固定版本评审" :aria-busy="busy || deciding">
    <h1>标准能力正式内部评审</h1>
    <p>此处只处理指定版本的本轮内部评审，不代表客户签署、UAT 或发行通过。</p>
    <p v-if="!mayRead()" role="status">请登录后通过有效的评审链接进入。</p>
    <template v-else>
      <button type="button" :disabled="busy || deciding" @click="load">刷新固定内容与评审状态</button>
      <p v-if="busy" role="status">正在核对固定版本与全部条目…</p>
      <p v-if="error" role="alert">{{ error }}</p>
      <template v-if="review && version && !busy">
        <h2>第 {{ version.version_no }} 版 · {{ review.state }}</h2>
        <p>评审：{{ review.review_id }}；轮次：{{ review.review_round_id }}；固定版本：{{ version.baseline_version_id }}</p>
        <p>条目 {{ items.length }} / {{ version.declared_item_count }}；版本指纹：{{ version.content_fingerprint }}</p>
        <p v-if="session.view?.deployment_role === 'DEPLOYMENT_ADMIN'">
          <RouterLink :to="{ name: 'capability-baseline-detail', params: { baselineId: version.baseline_id } }">返回能力基线详情</RouterLink>
        </p>
        <ol><li v-for="item in items" :key="item.capability_item_id">
          <strong>{{ item.capability_code }} · {{ item.name }}</strong>
          <p>{{ item.domain_name }} / {{ item.module_name }} / {{ item.feature_name }}</p>
          <p>{{ item.description }}</p><p>边界：{{ item.boundary }}；状态：{{ item.state }}</p>
          <p>文档版本引用：{{ item.document_version_refs.join('、') || '无' }}</p>
          <p>证据引用：{{ item.evidence_refs.join('、') || '无' }}</p>
        </li></ol>
        <p>文档与证据显示的是固定引用标识；直接跳转原文的位置功能尚未完成。</p>
        <h3>本轮决定</h3>
        <ul><li v-for="person in review.reviewer_ids" :key="person">
          {{ person }}：{{ review.decisions.find(value => value.reviewer_id === person)?.decision ?? '待决定' }}
          <span v-if="review.decisions.find(value => value.reviewer_id === person)?.comment">；意见：{{ review.decisions.find(value => value.reviewer_id === person)?.comment }}</span>
        </li></ul>
        <p v-if="!assigned" role="status">你不是本轮评审人，只能查看评审状态。</p>
        <p v-else-if="alreadyDecided && !pending" role="status">你已完成本轮决定。</p>
        <p v-if="decisionError" role="alert">{{ decisionError }}</p>
        <template v-if="pending">
          <p role="status">存在原决定操作号：{{ pending.decision }}。请核对当前状态，不要创建新操作号。</p>
          <label><input v-model="confirmRetry" type="checkbox" :disabled="deciding || locked">已核对评审与审计，按原决定、意见和操作号重试</label>
          <button type="button" :disabled="deciding || locked || !confirmRetry" @click="decide(pending.decision)">按原操作号重试</button>
        </template>
        <template v-else-if="review.state === 'IN_REVIEW' && assigned && !alreadyDecided && !locked">
          <label><input v-model="confirmScope" type="checkbox" :disabled="deciding">
            我已逐条核对上方完整固定版本、来源引用与本轮范围</label>
          <button type="button" :disabled="!ready" @click="decide('APPROVE')">批准本轮版本</button>
          <label>退回意见<textarea v-model="returnComment" :disabled="deciding" /></label>
          <button type="button" :disabled="!ready || !returnComment.trim()" @click="decide('RETURN')">退回并填写意见</button>
        </template>
        <p v-if="receipt" role="status">决定回执已收到：{{ receipt.event_id }}；当前状态需以上方刷新结果为准。</p>
      </template>
    </template>
  </section>
</template>
