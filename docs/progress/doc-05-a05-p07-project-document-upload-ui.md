# DOC-05-A05-P07 项目文档新建/升版上传页面

- 日期：2026-09-30；Phase 2 Platform Core；结果：`FRONTEND_CONTRACT_PASS`。输入：冻结项目文档上传协议、P01～P06 客户端、项目文档历史/详情页；决策 `DEC-20260930-491`。
- Changed/Files：新增 `ProjectDocumentUploadView.vue` 与双路由，项目文档历史加入“上传新文档”，ACTIVE 文档详情按当前项目写角色显示“上传此文档的新版本”。页面读取升版原文档/强 ETag/最新版本引用，明确确认后按 Create→Content→Commit 执行；阶段/原文件/原 Key 仅留本页内存。未知结果停止，核对后才可显式复用原阶段；确定性内容/提交拒绝可显式 Abort，未知 Abort 复用原终止 Key；Commit/Abort 仅展示首次回执且要求独立重读。会话丢失与跨项目迟到结果阻止后续发网。
- Tests：上传页面定向 8，三视图相关 26，前端全量 42 文件/970 项、`pnpm build`（含 typecheck）PASS。复查修复 401 会话清除后页面滞留“处理中”的状态，并补单测；真实浏览器/PG 上传未运行。
- Migration/API/Upgrade：无后端 API、Schema、Migration、权限或依赖变化；兼容冻结 `/api/v1` 和 DB `20260927_0049`，无升级步骤。页面角色仅用于入口提示，后端继续最终授权。
- Known Issues/Next：本页内存中的原操作记录在刷新/离页后不恢复，明确提示需先核对文档历史/审计。下一项 `DOC-05-A05-P08` 为 Windows 11 隔离真实文件浏览器/PG 上传及 Parse 队列验收；100 MB Web Crypto 内存/耗时、正式信任源、Server 2025/Debian 13、Gate 3/完整程序包仍待。
