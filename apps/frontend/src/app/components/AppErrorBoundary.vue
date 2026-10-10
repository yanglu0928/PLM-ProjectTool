<script setup lang="ts">
import { onErrorCaptured, ref } from "vue";

const failed = ref(false);

onErrorCaptured(() => {
  failed.value = true;
  return false;
});

function reload(): void {
  window.location.reload();
}
</script>

<template>
  <section v-if="failed" class="state-panel" role="alert">
    <p class="state-label">页面暂时无法显示</p>
    <h1>请重新加载后再试</h1>
    <p>错误详情不会显示在页面中。如问题持续，请联系系统管理员。</p>
    <button type="button" @click="reload">重新加载</button>
  </section>
  <slot v-else />
</template>
