# DOC-05-A06-P02 项目文档版本解析状态面板

- 日期/结果：2026-09-30；Phase 2；`FRONTEND_CONTRACT_PASS`。编码前检查：冻结 `DOCUMENT_PARSE_LIST`、后端 DOC-04-A05 和前端 A06-P01 安全客户端已具备；P08-A02 浏览器上传待确认但不阻塞此只读面板。决策 `DEC-20260930-495`。
- Changed/Files：`ProjectDocumentDetailView.vue` 在受权可用版本行加入按需“查看版本解析状态”，一次仅展示一个固定版本的 50 条 ParseRecord 状态/Job/时间安全元数据，支持续页与显式刷新。切版本、切项目/文档及刷新丢弃旧记录；迟到响应由代际/路由/文档/版本检查阻断；401/404 拒绝清除旧 ParseRecord。文案明确 PENDING 非处理完成、SUCCEEDED 不等于 Evidence 已核定或文内定位。新增定向面板测试。
- Tests：前端全量 44 文件/1012 项、typecheck/build PASS；覆盖按需与固定路径、第二版本迟到丢弃、续页/刷新空态、404/401 清旧及路由变化。无真实浏览器/PG 或正式 Worker 处理验收；页面入口不授权，服务器继续实时检查 Session/Project/License。
- 兼容/升级/回滚：仅前端面板/测试，兼容冻结 `/api/v1`、DB0049；无新路由、后端 API、ORM/Migration、权限或依赖变化。撤面板即可回滚，不修改任何文档或 ParseRecord。
- Known Issues/Next：实际 Windows 11 浏览器/PG 只读面板需单列验收；P08-A02 合成文件 UI 上传仍 `INCOMPLETE`。Phase3 Parser/OCR Worker、精确 Evidence Locator、正式信任、Server 2025/Debian 13、Gate3/UAT/可用程序包均未完成。下一项 `DOC-05-A06-P03` 可用隔离浏览器/PG 已存在的合成 ParseRecord 验证 UI，而不发送文件。
