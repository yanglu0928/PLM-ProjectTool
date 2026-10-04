# DOC-05-A05-P03 项目上传内容私有 PUT 桥接

- 日期：2026-09-29；Phase 2 Platform Core；结果：`FRONTEND_CONTRACT_PASS`。输入：冻结 `DOCUMENT_UPLOAD_CONTENT`、P01/P02 UploadIntent 客户端、后端可选内容 PUT；决策 `DEC-20260929-487`。
- Changed/Files：`apps/frontend/src/modules/auth/api/sessionClient.ts` 新增固定 PROJECT 内容 PUT，校验项目/上传 UUID、43 位 token、64 位小写 SHA-256、已知 Blob 大小 1～100,000,000 字节；只传同源 Cookie、私有 CSRF、token/hash 与 `application/octet-stream`，5 分钟超时中止、互斥、401 清写证明，不自动重传。对应测试覆盖单次请求/固定路径/头、非法输入、未登录/401、互斥与超时。
- Browser `Content-Length`：按 Fetch 标准由已知 Blob 长度生成，应用层禁止手设；实际 Windows 11 浏览器到 FastAPI 的请求头尚未验证，不能据此标记网络 PUT PASS。
- Tests：SessionClient 定向 143、前端全量 39 文件/880 项、`pnpm build`（含 typecheck）PASS；真实浏览器/PG 文件字节与 Hash 未运行。
- Migration/API/Upgrade：无后端 API、Schema、Migration、权限或依赖变化；兼容冻结 `/api/v1` 和 DB `20260927_0049`，无升级步骤。
- Known Issues/Next：本项仅传输，不计算文件 SHA-256、不解析 200 回执，也无 Commit/Abort/UI。下一项 `DOC-05-A05-P04` 做内容 SHA 与 200 安全业务客户端；正式信任、其他平台、Gate 3/程序包仍待。
