# SOL-01-A03-P01：OutlineVersion Schema 0137 增量

日期：2026-10-08；依据冻结 DM-05、SC-01/02、API-04 与 CR-SOL-002。原 Gate 2 冻结提交不改写。

|对象|表|数据库边界|
|---|---|---|
|SOL-03 目录版本|`plm.sol_outline_versions`|同 Outline 版本号唯一；`(version_id,outline_id,project_id)` 固定身份；同父 supersedes FK；32 字节指纹、JSONB 数组声明、独立 Review 引用/状态|
|有序章节身份引用|`plm.sol_outline_sections`|ordinal>0 且版本内唯一；同版本 Section 不重复；Version 与 Section 均经相同 Outline/Project 复合 FK|
|固定需求版本引用|`plm.sol_outline_requirement_refs`|ordinal>0 且版本内唯一；同版本 RequirementVersion 不重复；RequirementVersion/Requirement/Project 三元 FK|

0137 还为 `sol_sections` 增加 `(section_id,outline_id,project_id)` 唯一键，并为 `sol_outlines.current_approved_version_ref` 增加同 Outline/Project 的可延迟复合 FK。该 FK 仅验证指针归属，不证明目标状态为 APPROVED；正式指针写入必须等 Review Owner 同事务证明。三个新表在 Owner 未装配前 DML 全拒、TRUNCATE 全拒；不能由 Schema 直接产生业务事实。

冻结的 `sol_outline_reference_refs` 在本增量中未建：SOL-01 ReferenceSolutionVersion 尚无真实表和可核验来源，先写无目标 FK 的 UUID 会弱化固定版本语义。后续 SOL-01 落地时需按 CR-SOL-002 补建与迁移，不删减产品范围。章节顺序目前引用稳定 Section 身份，正式输出仍需明确列出其 Approved SectionVersion。

Win11 一次性 PG18.6 完成空/已有 Project 与 User 数据升级、空表降级重升、三次 Alembic drift check、Owner/历史闭锁、同 Outline 章节和跨项目需求 FK、顺序唯一、无效声明/指纹、跨 Outline 批准指针拒绝、有历史拒降；旧 A02 验证脚本随新子表 FK 调整后复跑通过。后端全量 `3263 passed, 3 skipped, 4815 subtests passed`。已有 pgvector 索引表达式及生成列比较警告不属于本增量，不据此宣布全局质量通过。

兼容性/升级：旧 API/权限/配置/依赖不变，按 Alembic 线性升级；三张新表均为空才允许降到 0136，保留 A02 身份数据。无客户数据外发。真实 Version CREATE/读、参考方案、SectionVersion、Review/Trace/Workflow、Server2025 与 Release 验收仍待。
