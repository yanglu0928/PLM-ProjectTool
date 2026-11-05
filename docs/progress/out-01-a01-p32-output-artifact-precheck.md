# OUT-01-A01-P32 编码前检查：OutputArtifact 持久化基础

- 日期：2026-11-05
- 结论：PASS_WITH_LIMITATION（编码前检查已满足；Artifact ORM/Migration hosted PG18 验收待完成）
- 变更记录：[CR-OUT-028](../changes/CR-OUT-028-output-artifact-persistence.md)
- 依赖证据：[PLG-03-A01 验收结果](plg-03-a01-execution-persistence-result.md)

## 冻结基线及依赖复核

OutputRequest 已具备固定来源及 Job 状态；OutputArtifact尚无持久化。冻结 Data Model V1/DB Schema V1 (OUT-02) 要求Artifact只在 FileObject、DocumentVersion、PluginExecution、Hash与OutputRequest一致且验证后才可成为AVAILABLE；SC-01映射 `out_artifacts` 和 `out_artifact_validation_results`，SC-02指定M-PRJ。

PLG-03-A01已在 hosted PG18.6 独立验证通过，创建 `plg_executions`、`plg_execution_result_files`、`plg_execution_state_events`。迁移链和 ORM现已存在稳定Execution Root及PROJECT关系，因此原物理Root缺失阻断解除。P25的Windows `initdb.exe` 诊断仍独立未通过，不能据此推断产品环境兼容。

## 单一实现范围与设计

按 CR-OUT-028 新增 SQLAlchemy ORM、Alembic `20261105_0232` 和独立迁移验证：
- M-PRJ root绑定 OutputRequest 与 Project，并以复合 FK绑定同一Project中的 PluginExecution + OutputRequest；关联DocumentVersion、其FileObject、scope/project、SHA-256、字节数与MIME均由复合外键锁定。
- 在 PLG Execution、DocumentVersion 上增加仅用于支持这些冻结跨Root复合关系的候选唯一键；不得改变其Owner行为/状态或打破既有migration。
- Artifact仅允许冻结状态 `VALIDATING / AVAILABLE / RESTRICTED / REVOKED`；唯一字节指纹/长度和验证时态须一致。Validation child为append-only，只记录受控校验码、枚举和指纹，不接受客户正文/路径。
- Artifact root所有写入默认关闭，由专属GUC trigger预留未来Owner边界；Validation只允许同一GUC下插入且拒绝更新/删除。两表阻断TRUNCATE。没有发布Owner/API/worker/文件I/O/plugin执行。

## 风险、回滚与验收计划

风险为跨Project或错配Request/Execution/DocumentVersion/file/hash以及错误AVAILABLE状态；以复合FK、唯一键、状态与指纹约束、关闭写入守卫和PG18负例覆盖。新迁移降级先检查两表均为空，否则拒绝并保留历史；空库降级/重升必须通过。验证在GitHub hosted Windows Server 2025 runner D:临时目录完成：backend全量/wheel、空库/有既有数据 migration lifecycle、约束与trigger负例、父包PG18 smoke。不得把Artifact基础持久层PASS描述成可生成/发布文件；P25、Pilot、Gate、Release继续分别记状态。

## 先前阻断更正

最初文档把“已在冻结模型定义”误写成“已有Plugin ORM/表实现”。更正前未开始Artifact代码/DDL，也未发生数据库写入。CR-OUT-028先记录缺项，转入PLG-03-A01。PLG-03-A01独立PG18验收完成后，本次重新盘点确认依赖已经满足并恢复P32。
