# EVD-01-A04-P03-A05：资格隔离 PostgreSQL/HTTP 实证

日期：2026-10-01；Phase 2 Platform Core；结论：`ISOLATED_WINDOWS11_PG18_HTTP_PASS / PRODUCTION_COMPOSITION_OPEN`。

输入为 P03-A04 可选 HTTP、P03-A03 同事务命令、Document 来源 Port 与冻结 EVIDENCE_SET_ELIGIBILITY。编码前核查：只使用 PoC 已验证 PostgreSQL 18.6/pgvector 二进制的临时复制、随机 loopback 端口、全新数据目录及合成记录；不连接原 55432 集群、正式库/客户数据或真实 License。范围仅验收脚本与验证，未改生产组合。

脚本初始化全新 PG18、迁移到当前 head，创建合成 Auth Session/项目成员/Document/FileObject/Version/Evidence。真实 SQLAlchemy UoW 中检验当前 Session/CSRF、Document 固定可用来源、首次 ELIGIBLE、同 Key 重放不重复审计、不同 Key 不得重裁、模板 ELIGIBLE 拒绝及 INELIGIBLE 可裁定；跨项目 Evidence、License 无效、已撤销 DocumentVersion、撤权成员均拒绝；注入 Audit 失败后 Evidence 仍 CANDIDATE 且无收据。真实 TestClient→FastAPI→PG POST 200/同 Key 200，缺 CSRF 403。SQL 读回仅 3 次成功裁定 Audit/收据，审计失败项 lock_version 仍0。

首轮脚本把不同 Key 的旧 ETag 预期误写为状态冲突，实际返回正确的版本冲突；修正测试预期后重跑通过。扩展跨项目、License 和撤销版本后再次完整重跑退出0。脚本 finally 确认 `pg_ctl status` 已停止再删除自有临时目录；事后 Temp 同前缀目录与 postgres 进程均为0。使用 trust 认证只限全新 loopback 测试实例，不能代表生产安全配置。

未验证：双请求并发锁竞争、正式 Windows 11 目标账户装配、Windows Server 2025、Debian 13、发行 License/HTTPS/密钥恢复、真实浏览器人工确认与 Gate3。回滚不接正式路由，脚本可保留复验；不清理或修改旧环境。
