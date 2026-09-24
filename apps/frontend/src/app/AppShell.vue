<script setup lang="ts">
import { RouterLink, RouterView } from "vue-router";

import AppErrorBoundary from "@/app/components/AppErrorBoundary.vue";
import ConnectionStatus from "@/shared/components/ConnectionStatus.vue";
</script>

<template>
  <a class="skip-link" href="#main-content">跳到主要内容</a>
  <div class="app-shell">
    <header class="app-header">
      <div>
        <p class="app-eyebrow">PLM PROJECT TOOL</p>
        <p class="app-brand">项目实施辅助工具</p>
      </div>
      <div class="header-actions">
        <nav aria-label="主导航">
          <RouterLink to="/">首页</RouterLink>
        </nav>
        <ConnectionStatus />
      </div>
    </header>

    <main id="main-content" class="app-main" tabindex="-1">
      <AppErrorBoundary>
        <RouterView />
      </AppErrorBoundary>
    </main>

    <footer class="app-footer">
      基础工程版本 · 业务能力将按已批准 WBS 逐步开放
    </footer>
  </div>
</template>
