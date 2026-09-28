<script setup lang="ts">
import { provide } from "vue";
import { RouterLink, RouterView } from "vue-router";

import AppErrorBoundary from "@/app/components/AppErrorBoundary.vue";
import { SessionClient } from "@/modules/auth/api/sessionClient";
import { sessionClientKey } from "@/modules/auth/api/sessionContext";
import ConnectionStatus from "@/shared/components/ConnectionStatus.vue";

provide(sessionClientKey, new SessionClient());
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
        <nav class="primary-nav" aria-label="主导航">
          <RouterLink to="/">首页</RouterLink>
          <RouterLink to="/login">账户与登录</RouterLink>
          <RouterLink to="/projects">我的项目</RouterLink>
          <RouterLink to="/projects/new">创建项目</RouterLink>
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
