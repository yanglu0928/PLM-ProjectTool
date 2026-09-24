# Frontend

Vue 3 + TypeScript + Vite 前端工程。源目录固定分为 `app`、`modules`、`shared`；浏览器只通过冻结的 REST/JSON、multipart 与 SSE Contract 访问后端。

## 当前能力

WBS 1.03 已建立响应式 App Shell、首页、404、安全错误边界和服务就绪状态。当前没有业务页面、认证界面或可信权限判断。

```powershell
pnpm install --frozen-lockfile
pnpm test
pnpm build
pnpm dev
```

开发服务器只把相对路径 `/health` 代理到本机 FastAPI `127.0.0.1:8000`。前端不保存 Session Cookie、CSRF Token、API Key 或客户资料；后续认证实现中的 CSRF Token 也只能保存在内存。
