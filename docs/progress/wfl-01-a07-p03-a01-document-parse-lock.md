# WFL-01-A07-P03-A01：Document ParseRecord 固定来源共享锁

2026-10-02 / Phase 2 / `INTERNAL_REPOSITORY_PASS`。输入 `CR-WFL-005`、冻结 Workflow 固定 Evidence 引用要求与现有 Document ParseResult 只读 Port。按 `DEC-20261002-602` 在 Document-owned 仓储新增 `get_for_trace`，维持普通 `get` 不加锁；调用方必须持活跃事务，查询继续精确绑定 Scope、ProjectId、DocumentVersionId、已成功 ParseRecord/ResultRef 同一摘要、无错误且不可重试，并对两行 `FOR SHARE OF`，刷新 ORM identity map。此入口只提供固定元数据，不授权用户、不返回正文到 Workflow；后续应用 Port 必须复验 Session/目标项目/License 与实际文件/解析内容。

定向新单元 2/2 验 SQL 锁形、Scope/版本条件、identity refresh、普通读取无锁和无事务拒绝。旧隔离 PG18 解析结果脚本扩展后两轮退出 0：新路径取正确固定引用，错误 Project 与 FAILED 记录为空；另一个真实 PostgreSQL 连接对 ParseRecord 与 ResultRef 分别 `FOR UPDATE NOWAIT` 均获 `55P03`，证明锁持续到调用方事务结束。原存储哈希、精确节点、撤权与篡改拒绝回归 PASS；临时 PG/目录清理。后端全量 1832 测试通过/3 跳过，开发 wheel 由本地无依赖构建生成 SHA-256 `dbc169edc6be7b1672b977da80d652dd87b3dd86db367ef122154d0c575791d8`。首次 `python -m build` 因环境未装 `build` 退出 1，改用已安装 pip 的 `--no-deps --no-build-isolation` 本地构建，未下载依赖。

兼容/升级/回滚：无 Schema/Migration、公开 API、依赖或普通读取行为变化；应用未调用新入口，回滚可撤独立方法，Checklist/Gate 写路由保持关闭。当前锁定的是数据库元数据，真实文件快照、解析内容、Document 授权与 Evidence 当前资格尚未在**同一调用方事务**组合，不宣称完整 Owner、客户确认或 Gate 通过。下一任务 `WFL-01-A07-P03-A02` 以此锁入口实现 Document 应用层固定来源证明；Review/例外 Owner、正式信任/法律、Server2025/Debian、浏览器、AI质量/UAT仍开放。
