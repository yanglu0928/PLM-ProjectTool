# WBS 1.03 Vue App Shell Validation

状态：`WINDOWS_11 / NODE_24 / VUE_3 / NO_BUSINESS_API / NO_EXTERNAL_CALLS`

验证内容：

- Vue/Router/Vite/TypeScript 的锁定直接版本；
- App Shell、Router、错误边界、健康客户端和构建产物完整性；
- 生产源码不使用 local/session storage、WebSocket、厂商 URL 或绝对外部 API；
- 健康检查只请求同源 `/health/ready`；
- 404、离线状态和异常降级由测试覆盖。

在 `apps/frontend` 完成 `pnpm test` 和 `pnpm build` 后运行：

```powershell
node ../../validation/wbs-1.03-vue-app-shell/verify.mjs --write
```

结果写入 `evidence/windows-11/result.json`。
