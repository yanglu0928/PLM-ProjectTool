# CR-OUT-028：OutputArtifact 持久化基础

- 日期：2026-11-05
- 阶段/WBS：Phase 2 Platform Core / OUT-01-A01-P32
- 状态：编码前检查 PASS_WITH_LIMITATION；按冻结模型实施
- 基线：Gate 2 冻结 Data Model V1、DB Schema V1 的 OUT-02；SC-01 映射 `out_artifacts` 与 `out_artifact_validation_results`，SC-02 将 OUT-02 定为 M-PRJ。
- 来源：P31 完成 Job/Output retry/failure 状态收敛后，真实成功发布仍需要独立的 OutputArtifact 数据事实。

## 编码前检查结论

当前 Output ORM 与生产 Migration 已包含 OutputRequest/Context 和 P29-P31 转移，但没有 OutputArtifact 根或 validation result 子表。Document Owner 已有 FileObject/DocumentVersion，Plugin Owner 已有 PluginExecution；不代表这些对象已经能在 Output 成功发布中通过一致性校验。Jobs Lease Owner 已有 `finish`，必须等待 Artifact 发布 Owner 验证完成后才可用于 Output 成功路径。

因此，本WBS只补齐已冻结 OUT-02 的关系持久化：SQLAlchemy ORM、Alembic revision、约束/索引和迁移验收夹具。此项不开放任何生产写入入口，不能把测试插入当作已发布文件。

## 决策与范围

- 新增 `plm.out_artifacts`，PROJECT Scope；按冻结 OutputArtifact 字段保存请求/项目关联、Artifact kind/media type、DocumentVersion/PluginExecution 引用、SHA-256、大小、VALIDATING/AVAILABLE/RESTRICTED/REVOKED状态、验证摘要、创建/发布时间和并发版本字段。
- 新增 owned table `plm.out_artifact_validation_results`，追加验证结果及受控检查码；验证摘要不得包含客户正文、绝对路径或 Secret。
- 用 ProjectId 复合外键保护 OutputRequest、DocumentVersion、PluginExecution 的项目一致性；遵循被冻结的可用性不变量。FileObject 经 GENERATED_ARTIFACT DocumentVersion 关联验证，不复制绝对路径或文件正文。
- Migration 从当前 schema head `20261104_0230` 前进；必须通过空库升级、既有合成数据升级、空库 downgrade/reupgrade；有Artifact历史时 downgrade 必须拒绝并保留行。
- 本WBS不实现 Artifact 创建/发布Owner、插件/文件执行、下载/预览API、OutputRequest成功状态转移或文件写入；这些必须在后续独立任务验证 Hash、DocumentVersion、FileObject、PluginExecution 和 Project一致性之后才允许接入。

## 风险、回滚与验收

- 风险：DDL存在但无生产Owner，属于不可用的内部持久化骨架；任何API不得直接写表。
- 回滚：因为本WBS不建立正式Artifact行，空库可正常降级；出现历史时由Migration guard拒绝降级，保留所有记录。移除应用 ORM 依赖及新增代码前先确认没有后续写Owner。
- 验收：hosted PostgreSQL 18.6 验证约束/复合FK/状态枚举/哈希长度/大小/time字段、Append-only validation rows、跨项目拒绝、空库与有数据升级、空库downgrade/reupgrade及有历史降级保护；后端全量/Wheel和父包PG smoke。Secret扫描后同步GitHub。
- 环境：只用GitHub hosted Windows runner D盘临时工作区/隔离合成数据库；用户本机与C盘不执行代码。

