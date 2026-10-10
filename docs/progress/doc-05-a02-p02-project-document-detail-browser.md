# DOC-05-A02-P02 项目 Document 元数据详情 Windows 11 浏览器/PG 验收

- 日期：2026-09-29；Phase 2 Platform Core；结果：`WINDOWS_11_SYNTHETIC_BROWSER_PG_PASS`。输入为冻结 `DOCUMENT_GET`、DOC-05-A02-P01 页面和 A01 项目文档列表隔离夹具。
- Changed/Files：既有 `validation/prj-05-a04-browser-project/serve.py` 增加互斥 `--document-detail-browser`，复用随机库的 51 ACTIVE + 1 RESTRICTED + 1 FOREIGN 合成文档元数据。无生产程序、API、Schema、Migration、权限或依赖变化，撤此验收模式即可回滚。
- Browser：隔离应用内浏览器以合成项目成员登录，由“我的项目”→OWNED 项目详情→项目文档历史→首条 `Synthetic Browser Document 00` 进入固定详情路由。页面显示标题、`synthetic-00.pdf`、`PROJECT_RECORD`、有效、最新/当前版本引用“暂无”、元数据强版本 `"v0"`，并说明仅显示受权元数据、不提供正文或下载。点击刷新后相同元数据仍显示且无错误；浏览器可见状态已核，未保存截图文件。
- Database/cleanup：完整夹具 exit0，SQL 核 OWNED 51 ACTIVE + 1 RESTRICTED、FOREIGN 1、2 项目/1 Session/1 ACTIVE Member；随机库、角色、临时 Vault 凭据清理断言通过。PoC PostgreSQL 测试前停止，测试后正常 fast stop 恢复停止。
- Tests/compatibility/upgrade：P01 前端 814 项/typecheck/build、A01 API/PG 的详情 ETag/跨项目拒绝先前通过；本项实际浏览器/SQL/清理通过，没有重复前端全量或负向 HTTP 测试。兼容 DB0049/冻结 `/api/v1`，无升级步骤。正式 License/目标账户信任、Server 2025/Debian 13、性能质量、Gate 3/UAT/可用包未验。
- 下一项：继续 Phase 2 Document 版本历史/受权内容读取前端；实际文件定位与 Evidence 引用应待对应 Viewer/Parser 合同和验收，不把本元数据页冒充文件查看器。
