# DOC-05-A05-P04 项目上传内容摘要与回执客户端

- 日期：2026-09-29；Phase 2 Platform Core；结果：`FRONTEND_CONTRACT_PASS`。输入：冻结 `DOCUMENT_UPLOAD_CONTENT`、P02 意图结果、P03 私有 PUT；决策 `DEC-20260929-488`。
- Changed/Files：`apps/frontend/src/modules/document/api/documentUploadContentClient.ts` 对同一 Blob 使用 Web Crypto 计算 SHA-256，过期/无摘要环境阻止发网，调用 P03；严格绑定 200 JSON/trace、Upload ID、实际大小、摘要、detected MIME 与 no-store，仅返回白名单结果；已知拒绝/未知结果分离，不自动重传。测试覆盖摘要输入和原 Blob、过期、无 Web Crypto、未登录、权限/License/文件错误、伪回执与断线。
- Tests：定向 30 项及前端全量 40 文件/910 项 PASS，`pnpm build`（含 typecheck）PASS。首轮构建因测试文件引用未开放的 Node 类型失败，改用固定合成摘要样本后全量重跑通过。真实浏览器/PG 字节、浏览器原生 SHA/性能未运行。
- Migration/API/Upgrade：无后端 API、Schema、Migration、权限或依赖变化；兼容冻结 `/api/v1` 和 DB `20260927_0049`，无升级步骤。
- Known Issues/Next：最多 100 MB 文件摘要调用 `Blob.arrayBuffer()`，有浏览器内存峰值风险；下一项 `DOC-05-A05-P05` 做 Commit/Abort 的私有传输，再做安全回执、UI 和真实上传/解析验收。正式信任源、其他平台、Gate 3/完整程序包仍待。
