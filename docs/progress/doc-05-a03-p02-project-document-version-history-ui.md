# DOC-05-A03-P02 项目 Document 版本历史界面

- 日期：2026-09-29；Phase 2 Platform Core；结果：`FRONTEND_CONTRACT_PASS`。
- 输入/Trace：冻结 `DOCUMENT_VERSION_LIST`、DOC-05-A03-P01 安全版本客户端、现有项目 Document 详情页；`DEC-20260929-480`。
- Changed/Files：`apps/frontend/src/modules/document/views/ProjectDocumentDetailView.vue` 加入按需版本历史、续页、空态及安全错误呈现；同目录测试覆盖首屏不多取、成功/空态/拒绝、翻页、刷新清旧和跨路由迟到响应。
- 安全边界：仅在先读取到受权 Document 详情后加载其版本列表；前端使用现有同源 Session 客户端和固定 PROJECT 路径。版本元数据面板没有正文、下载或本地路径；实际 Session、Project、License、AVAILABLE 过滤由后端强制。
- Tests：定向视图 Vitest 10 PASS；前端全量 38 文件/839 项 PASS；`pnpm build`（含 typecheck）PASS。实际浏览器/PG 对本 UI 未运行。
- Migration/API/upgrade：无 Schema/Migration/后端 API/权限/依赖变化；兼容冻结 `/api/v1` 与 DB0049，无升级步骤。
- Known Issues/Next：下一项 Windows 11 隔离浏览器/PG 验收需构造至少一个已发布 AVAILABLE 版本；正式目标账户信任、Server 2025/Debian 13、性能质量/Gate3/UAT/可用包仍待。
