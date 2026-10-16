# DOC-05-A06-P03 Windows 11 解析状态面板隔离验收

- 日期/结果：2026-09-30；Phase 2；`WINDOWS11_SYNTHETIC_BROWSER_PG_PASS`。编码前检查：冻结 `DOCUMENT_PARSE_LIST`、后端 DOC-04-A05、前端 A06-P01/P02 已具备；本项只读，不依赖 P08-A02 的浏览器文件上传确认。决策 `DEC-20260930-496`。
- Changed/Files：扩展 `validation/prj-05-a04-browser-project/serve.py` 的独立 `--document-parse-api-only` 和 `--document-parse-browser` 模式。在随机隔离 PostgreSQL 库与本机临时文件根内创建一个有 50 字节真实文件支撑的 DocumentVersion，并仅为该版本插入合成 Job 和 3 条 `PENDING` ParseRecord。没有修改生产代码、正式 Schema 或客户资料。
- Tests：API-only 真实 HTTP/PG 验证匿名 401、非成员 404、成员 2+1 游标分页、安全 PENDING 投影、跨项目 404，第三轮 exit0。实际 IAB 合成成员登录，沿项目→文档列表→文档详情→可用版本打开按需解析面板，看到第 3/2/1 次尝试均为“待处理”；显式刷新后仍为三条。退出 SQL 核实同一 Job/版本、外项目 0；随机库/角色/Vault/临时文件根清理 exit0。
- 偏差与修复：首轮 Job 合成载荷缺少 Document/Version 引用，被数据库约束拒绝；补齐后第二轮 API-only 会话数量断言误写为 1，实际 Admin+Member 为 2；修正并重新运行得到完整 PASS。失败轮次不计入通过证据。
- 兼容/升级/回滚：仅验证夹具和记录，兼容冻结 `/api/v1`/DB0049；无 ORM/Migration、生产 API、权限、依赖或升级要求。可撤销两个新验证模式，不触碰生产数据。
- Known Issues/Next：三条记录是合成 PENDING，不能证明 Parser/OCR Worker 已消费、解析成功、Evidence Locator 或文内定位。P08-A02 浏览器文件上传仍 `INCOMPLETE`；正式信任、Server 2025/Debian 13、性能/AI 质量、Gate 3/UAT/可用程序包均未因此通过。
