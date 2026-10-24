<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { isBackendReady } from "@/shared/api/healthClient";

type ConnectionState = "CHECKING" | "READY" | "UNAVAILABLE";

const state = ref<ConnectionState>("CHECKING");

const label = computed(() => {
  if (state.value === "READY") return "服务已就绪";
  if (state.value === "UNAVAILABLE") return "服务暂不可用";
  return "正在检查服务";
});

onMounted(async () => {
  state.value = (await isBackendReady()) ? "READY" : "UNAVAILABLE";
});
</script>

<template>
  <div
    class="connection-status"
    :data-state="state"
    role="status"
    aria-live="polite"
  >
    <span aria-hidden="true" />
    {{ label }}
  </div>
</template>
