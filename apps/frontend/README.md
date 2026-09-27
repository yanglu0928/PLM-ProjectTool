# Frontend

Vue 3 + TypeScript + Vite 前端工程。源目录固定分为 `app`、`modules`、`shared`；浏览器只通过冻结的 REST/JSON、multipart 与 SSE Contract 访问后端。

## 当前能力

WBS 1.03 已建立响应式 App Shell、首页、404、安全错误边界和服务就绪状态。当前没有业务页面、认证界面或可信权限判断。

AUT-05-A01 已新增 `src/modules/auth/api/sessionClient.ts`，使用原登录/会话查询/续期/注销接口，Cookie由浏览器自动携带、CSRF仅私有内存。客户端投影不能代替服务器授权；GET不返回CSRF，因此刷新后仅能恢复只读身份，写操作需要重新登录。异常清本地状态不等于服务器会话已撤销，不自动重试写请求。当前尚未接入页面/实际浏览器，构建不会包含未导入客户端；下一AUT-05-A02接线。

AUT-05-A02 已将客户端接入 `/login` 中文页面及导航，登录/当前身份/续期/退出、密码清理与受限/重登提示可通过组件合同测试，前端63测试/类型/构建通过。以上A01“尚未接页面”是历史状态：当前build已包含页面和client，但真实后端/浏览器链尚未完成，开发代理仍仅health，下一A03核同源Auth代理与可信Origin。受限用户改密页面尚待，不能宣称完整程序包或正式生产可用。

```powershell
pnpm install --frozen-lockfile
pnpm test
pnpm build
pnpm dev
```

开发服务器将相对路径 `/health` 和 `/api/v1` 代理到本机 FastAPI `127.0.0.1:8000`，保原Host/Origin，不重写路径且显式关闭开发CORS。后端必须显式配置可信浏览器来源 `http://127.0.0.1:5173`；不要开启changeOrigin绕过检查，localhost/不同端口不自动互换。HTTP仅限loopback开发，生产须同源HTTPS部署，不使用此开发服务器。前端JS不读写Session Cookie或持久化CSRF/API Key；浏览器按原HttpOnly Cookie规则自动携带会话，CSRF仅内存。A03已验证真实代理和原来源策略，不代表真实PG认证/浏览器链完成。
