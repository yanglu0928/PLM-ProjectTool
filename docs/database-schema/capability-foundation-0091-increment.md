# Schema0091：Capability 运行时基础增量

日期：2026-10-05

Revision：`20261005_0091`；前序：`20261004_0090`

## 目的与范围

为冻结的 CAP-01/CAP-02 建立 GLOBAL `CapabilityBaseline`、不可变 `BaselineVersion`、`CapabilityItem` 及逐项 Document/Evidence 固定引用。该增量只物理化两 Root/五表和提交期完整性边界，不开放 HTTP、Review 状态转换、正式指针更新或资料自动导入，也不创建任何 `APPROVED` 业务事实。

`source_collection_ref` 按 CR-CAP-001 固定为 `sha256:<64 lowercase hex>`。摘要输入为 UTF-8 文本 `capability-source-set.v1\n` 加按 UUID 文本升序排列、换行连接的去重 GLOBAL `DocumentVersionId` 集合；Baseline 与其 Version 必须保存相同引用。

## 表与不变量

- `cap_baselines`：GLOBAL Identity Root；代码唯一，初始仅 `ACTIVE`，正式版本指针必须为空，`lock_version=0`。
- `cap_baseline_versions`：不可变 Version Root；同 Baseline 版本号唯一，初始仅 `DRAFT`，Review 引用必须为空，声明 Item/Document/Evidence 数量必须为正且提交时精确匹配。
- `cap_items`：版本内稳定 `capability_item_id`、代码和顺序唯一；分类、名称、边界、前置和接口引用均有界。
- `cap_item_document_refs`：逐项绑定精确 `DocumentId + DocumentVersionId`；只接受 `GLOBAL`、`STANDARD_CAPABILITY`、ACTIVE Document 与 AVAILABLE Version。
- `cap_item_evidence_refs`：逐项绑定固定 Evidence；只接受 `GLOBAL`、`ELIGIBLE` 且与同一 Item 的 DocumentVersion 完全一致的 Evidence。

每个 Item 在事务提交时至少有一份 Document 和一份 Evidence。五表均禁止 UPDATE/DELETE/TRUNCATE；Baseline/Version 的 INSERT 还受未安装 Owner 的初始形态守卫约束。后续 CAP-01-A03/A04 只能以可追溯迁移替换守卫，不能绕过不可变历史或直接写其他模块表。

## 升级、降级与回滚

升级只追加五表、索引、外键、检查约束和 deferred validators，不推断或搬运现有标准能力库资料。部署后正式指针仍为零，因而不能把本迁移视为已形成客户能力基线。

无 Capability 历史时允许在线降回0090并可重升；离线降级始终关闭。任一五表存在历史时拒绝物理降级，应用应停止新写并向前修复或从受控备份恢复，不得删除历史规避保护。升级前应备份，在维护窗口运行 Alembic，并执行 drift 与合成 GLOBAL 来源验证。
