<template>
  <section class="state-panel" aria-labelledby="not-found-title">
    <p class="state-label">404</p>
    <h1 id="not-found-title">没有找到这个页面</h1>
    <p>该功能可能尚未开放，或地址已经失效。</p>
    <RouterLink to="/">返回首页</RouterLink>
  </section>
</template>

<script setup lang="ts">
import { RouterLink } from "vue-router";
</script>
