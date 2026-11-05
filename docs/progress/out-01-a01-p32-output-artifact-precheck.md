# OUT-01-A01-P32 编码前检查：OutputArtifact 持久化基础

- 日期：2026-11-05
- 结论：BLOCKED_DEPENDENCY；未开始Artifact编码
- 变更记录：[CR-OUT-028](../changes/CR-OUT-028-output-artifact-persistence.md)

## 问题与基线

OutputRequest 已经具备固定来源及 Job 状态，但尚无关系化的 OutputArtifact 持久化。冻结的 Output 模型要求仅在 FileObject、DocumentVersion、PluginExecution 和 Hash 完整且验证后才可将 OutputArtifact 标为 AVAILABLE。DB Schema V1/SC-01 已映射 OUT-02 根表 `out_artifacts` 与 `out_artifact_validation_results`；SC-02 指定 OUT-02 为 M-PRJ。此实现补齐冻结 Schema，不改变 Gate 2 基线。

源码检查：Output 模块当前仅有 OutputRequest/Context ORM及 P29-P31 状态转移；在现有模块树和 Alembic revisions 中未发现 OutputArtifact 表/Owner。Document ORM 已有 FileObject、DocumentVersion；Plugin ORM 当前没有 PluginExecution ORM或 `plg_executions` 表；Jobs Lease Owner 有受 fencing 保护的 `finish`。PluginExecution只在冻结模型中定义，并非现有实现。

## 执行边界

P32 暂停：无法在遵守冻结DB外键合同的前提下引用尚未持久化的PluginExecution。已将依赖任务转为 PLG-03-A01；待其Root和Migration在hosted PG18通过后，再恢复P32。

## 验收计划和限制

遵守冻结 M-PRJ/Append-only/复合ProjectId引用、状态白名单和Hash大小限制。托管PG18执行空库升级、既有合成数据升级、空库降级/重升，以及有历史时拒绝降级并留存。全量后端测试/Wheel和父包隔离PG smoke 通过后才标记PASS_SCOPE_LIMITED。

不生成文件、不执行插件、不调用外部API、不接客户数据；不代表Artifact发布、真实Output Create、Windows 11设备、Pilot、Gate 3或正式Release已通过。P25现存initdb问题独立保留，不通过削减/模拟它来验收P32。


## 更正记录（2026-11-05）

最初文档把“已在冻结模型定义”误写成“已有Plugin ORM/表实现”。对当前分支 `plugin/infrastructure/orm.py`、Migration树与 OutputArtifact AVAILABLE 不变量复核后确认该描述不准确。更正前未开始Artifact代码/DDL，也未触发任何数据库写入。CR-OUT-028同步调整为依赖阻断；先完成PluginExecution持久化基础。


编码前补充：`artifact_kind`与OutputRequest的固定`output_type`绑定；GENERATED_ARTIFACT Document、DocumentVersion、PROJECT FileObject、Execution、Request均以复合候选键/FK组成一个不可漂移引用链。Validation摘要只接受受控代码字段，不接纳自由文本。以上仅是冻结字段的物理约束化，不扩展业务范围。


AVAILABLE状态附加约束：数据库要求format、structure、hash、content四个受控验证结果码均为`PASSED)，同时必须设置published_at；Root引用内容在DB层不可改写。写入口仍关闭，状态表达式不构成发布Owner。


## 执行结果更正（2026-11-05）

本文件前文记录的是 P32 启动前因 PluginExecution 物理Root缺失而阻断的历史检查。PLG-03-A01 后续完成后，P32 重新执行检查，按 CR-OUT-028 补齐 OutputArtifact ORM/Migration，并于 hosted run [41988323089](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41988323089) 以 `PASS_SCOPE_LIMITED` 完成专项 PG18 验收。详细结论见 [P32验收结果](out-01-a01-p32-output-artifact-result.md)。P25仍为独立 `BLOCKED_DIAGNOSTIC`；Pilot、Gate 3及发行状态未变化。
