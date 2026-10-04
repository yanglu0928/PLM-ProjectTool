# Handover Analysis Foundation Schema 0096 增量

日期：2026-10-05。迁移：`20261005_0095 -> 20261005_0096`。范围：HND-01 `HandoverAnalysis` 与 HND-02 `HandoverAnalysisVersion`，不包含 HND-03 `ActionItem`。

## 物理对象

Schema 0096 新增八张 PROJECT Scope 表：

- `hnd_analyses`：Analysis identity、项目归属、当前批准版本指针与强锁版本；
- `hnd_analysis_versions`：不可变版本头、固定 Capability 版本、来源摘要及声明计数；
- `hnd_analysis_source_document_refs`：有序固定 Project DocumentVersion 集合；
- `hnd_analysis_ai_task_refs`：有序 GAP_ANALYSIS 成功任务 provenance；
- `hnd_analysis_items`：六类分析项、分类、候选状态和 NEED_CONFIRM 输入说明；
- `hnd_item_evidence_refs`：分析项到 PROJECT Evidence 的有序定位；
- `hnd_item_capability_refs`：分析项到固定 Approved Capability Version 中精确 Item 的引用；
- `hnd_item_options`：NEED_CONFIRM 的受控选项。

Analysis 同一时刻最多一个 `IN_REVIEW` 和一个 `APPROVED` Version。来源摘要由固定 DocumentVersion UUID 集合按规范顺序计算 `sha256:` 指纹，不接受路径、动态最新版或正文副本替代。

## 提交期完整性与 Owner 关闭

延迟约束触发器在事务提交时核对声明计数、来源指纹、Document/Project/Availability、当前 Approved Capability Version、Evidence 资格、Capability Item、AI Task Scope/类型/成功态以及 NEED_CONFIRM 最小结构。普通写入只允许合法初始 `ACTIVE` Analysis、`DRAFT` Version 和 `CANDIDATE` Item；更新、删除和 truncate 在正式 Owner 安装前失败关闭。

`source_missing=true` 仅保留冻结合同所需的缺资料表达能力，不代表事项已关闭。HND-03 尚未物理化，因此 A03/A04 不得把缺资料 Item 正式化；后续 `HND-02-A01` 必须把它与 ActionItem 创建/状态历史绑定。`required_input_spec.fields` 的字段级名称、格式、示例和必填规则由 A03 Validate Owner 完整校验，数据库只执行对象、非空数组与选项数量的最低防线。

## 迁移、兼容与回滚

增量只追加内部表、索引、外键和触发器，不修改冻结 `/api/v1`、既有表或依赖；没有客户资料导入、AI/网络调用或公开 Router。空 Handover 历史允许降级并可重升；任一 Analysis/Version/owned row 存在时拒绝 downgrade，要求向前修复或从已验证备份恢复。离线 SQL downgrade 因无法安全判断历史而拒绝生成。

## 验证

Windows 11/PostgreSQL 18.6 临时库验证覆盖：从 0095 的有数据升级、ORM drift、空历史降级/重升、真实约束下合法快照、错误来源指纹、缺失 NEED_CONFIRM 结构、Owner 未安装更新拒绝和保留历史拒降。定向 Schema/Migration 测试 8 项及后端全量 2601 项通过、3 项按环境条件跳过。
