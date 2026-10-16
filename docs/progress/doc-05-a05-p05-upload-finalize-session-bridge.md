# DOC-05-A05-P05 项目上传 Commit/Abort 私有传输

- 日期：2026-09-29；Phase 2 Platform Core；结果：`FRONTEND_CONTRACT_PASS`。输入：冻结 `DOCUMENT_UPLOAD_COMMIT/ABORT`、后端可选终结 Router、P01～P04；决策 `DEC-20260929-489`。
- Changed/Files：`apps/frontend/src/modules/auth/api/sessionClient.ts` 对 PROJECT 上传新增固定空体 Commit/Abort POST，发网前检查项目/上传 UUID、原 Key、Commit 可选强父 ETag；复用同源 Cookie、私有 CSRF、单次 60 秒中止、互斥及 401 清证明。Abort 无 If-Match；新建 Commit 无 If-Match，升版调用方须提供父文档原 ETag。测试覆盖两个固定路径/头/空体、无版本/坏 ID/Key/ETag、未登录/401、互斥与超时不重试。
- Tests：SessionClient 定向 149、前端全量 40 文件/916 项、`pnpm build`（含 typecheck）PASS；真实 PG/浏览器 Commit/Abort 未运行。
- Migration/API/Upgrade：无后端 API、Schema、Migration、权限或依赖变化；兼容冻结 `/api/v1` 和 DB `20260927_0049`，无升级步骤。
- Known Issues/Next：仅传输合同，无 201/200 安全回执、页面或实际解析证据。下一项 `DOC-05-A05-P06` 做 Commit/Abort 业务回执与确定性/未知结果；正式信任源、其他平台、Gate 3/程序包仍待。
