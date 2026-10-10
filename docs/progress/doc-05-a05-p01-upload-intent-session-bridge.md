# DOC-05-A05-P01 项目上传意图 Session 桥接

- 日期：2026-09-29；Phase 2 Platform Core；结果：`FRONTEND_CONTRACT_PASS`。输入：冻结 `DOCUMENT_UPLOAD_CREATE`、后端可选项目 UploadIntent POST、私有 Session/CSRF；决策 `DEC-20260929-485`。
- Changed/Files：`apps/frontend/src/modules/auth/api/sessionClient.ts` 新增固定 PROJECT UploadIntent POST，仅规范项目 UUID、原请求体和原幂等键通过既有私有命令通道；测试文件覆盖固定同源 Cookie/私有 CSRF/原 Key、坏路径/Key/体积拒绝、未登录与 401 清本地证明、互斥与超时一次不重发。
- Tests：定向 SessionClient 139 项、前端全量 38 文件/845 项、`pnpm build`（含 typecheck）PASS；未运行真实 PG/浏览器上传。
- Migration/API/Upgrade：无后端 API、Schema、Migration、权限或依赖变化；兼容冻结 `/api/v1` 和 DB `20260927_0049`，无升级步骤。
- Known Issues/Next：仅传输桥接，无 UploadIntent 响应校验、内容 PUT、Commit/Abort、页面或真实解析证据。下一项 `DOC-05-A05-P02` 做上传意图的安全业务客户端；正式信任源/其他平台/Gate 3/完整程序包仍待。
