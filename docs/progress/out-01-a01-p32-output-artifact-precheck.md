# OUT-01-A01-P32 编码前检查：OutputArtifact 持久化基础

- 日期：2026-11-05
- 结论：PASS_WITH_LIMITATION，可按冻结模型进入实现
- 变更记录：[CR-OUT-028](../changes/CR-OUT-028-output-artifact-persistence.md)

## 问题与基线

OutputRequest 已经具备固定来源及 Job 状态，但尚无关系化的 OutputArtifact 持久化。冻结的 Output 模型要求仅在 FileObject、DocumentVersion、PluginExecution 和 Hash 完整且验证后才可将 OutputArtifact 标为 AVAILABLE。DB Schema V1/SC-01 已映射 OUT-02 根表 `out_artifacts` 与 `out_artifact_validation_results`；SC-02 指定 OUT-02 为 M-PRJ。此实现补齐冻结 Schema，不改变 Gate 2 基线。

源码检查：Output 模块当前仅有 OutputRequest/Context ORM及 P29-P31 状态转移；在现有模块树和 Alembic revisions 中未发现 OutputArtifact 表/Owner。Document ORM 已有 FileObject、DocumentVersion；Plugin ORM 有 PluginExecution；Jobs Lease Owner 有受 fencing 保护的 `finish`。这些现有能力不会被本WBS越界调用为发布事实。

## 执行边界

单一问题是建立 OutputArtifact 与验证结果的物理持久化基础：ORM、Migration、约束与索引。无生产写入口、公开API、插件/文件操作或请求成功转移。后续独立WBS再实现发布Owner，且只在跨Request/Project/DocumentVersion/FileObject/PluginExecution/Hash校验完整后AVAILABLE；Job `finish` 与 Output状态将同一事务收敛。

## 验收计划和限制

遵守冻结 M-PRJ/Append-only/复合ProjectId引用、状态白名单和Hash大小限制。托管PG18执行空库升级、既有合成数据升级、空库降级/重升，以及有历史时拒绝降级并留存。全量后端测试/Wheel和父包隔离PG smoke 通过后才标记PASS_SCOPE_LIMITED。

不生成文件、不执行插件、不调用外部API、不接客户数据；不代表Artifact发布、真实Output Create、Windows 11设备、Pilot、Gate 3或正式Release已通过。P25现存initdb问题独立保留，不通过削减/模拟它来验收P32。
