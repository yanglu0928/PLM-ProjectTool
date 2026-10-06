# Survey 定义基础 Schema 0103 增量

日期：2026-10-06

WBS：`SUR-01-A02`

迁移：`20261005_0102 -> 20261006_0103`

## 范围

本增量仅物理化冻结数据模型中的 SRV-01 Survey 与 SRV-02 SurveyVersion 定义基础，不开放
HTTP、导入客户资料或形成客户确认事实：

|表|职责|
|---|---|
|`srv_surveys`|PROJECT 范围的 Survey 身份、状态和当前批准版本指针|
|`srv_survey_versions`|不可变定义版本、内容指纹、声明计数和 Review 引用|
|`srv_questions`|稳定问题身份、顺序、题型、校验规则和预期输出|
|`srv_question_options`|选择题选项|
|`srv_question_source_refs`|类型化固定来源引用|
|`srv_target_departments`|同 Project 的目标部门|

## 来源与完整性边界

- `HANDOVER_ITEM` 固定到当前批准、同 Project 的 Handover Item/Version/Analysis。
- `CAPABILITY_ITEM` 固定到当前批准的 GLOBAL Capability Item/Version/Baseline。
- `TEMPLATE_DOCUMENT_VERSION` 固定到 GLOBAL 或同 Project、可用且类别为 `TEMPLATE` 的
  DocumentVersion；它只提供问题结构，不能作为客户答复或结论事实。
- `MANUAL` 只保存去首尾空白的来源说明，不冒充客户确认。
- 每个问题至少一个来源；选择题至少两个选项，非选择题不得带选项；声明的问题、选项、来源和
  目标部门计数必须与实际行一致。
- 创建阶段只接受 ACTIVE Survey 与 DRAFT Version 初始状态。正式 Owner 安装前，除合法初始插入外，
  更新、删除和清空均失败关闭。

## 迁移与回滚

- ORM 元数据、Alembic Migration 与约束名称保持一致，`alembic check` 无新增漂移。
- 空库及从 0102 含数据数据库均可升级；空 Survey 历史可降级至 0102 并再次升级。
- 任何 Survey 定义历史存在时拒绝物理降级，必须向前修复或恢复备份。
- 本增量不改变冻结 `/api/v1`、角色、License、安全机制、依赖或外发边界。

## 验证证据

- 定向单元测试：8 项通过。
- Windows 11 / PostgreSQL 18.6：含数据升级、空历史降级/重升、drift、四类来源、部门范围、
  TEMPLATE 边界、选择题完整性、Owner 关闭和历史拒降全部通过。
- 后端全量：2783 项通过，3 项按环境条件跳过。
- Wheel：1017 个条目，包含 0103 Migration 与 Survey ORM；SHA-256
  `b397d565ee4c26ee41d01b4800cb8117456efcab1bc379b31868de4a44f0785e`。

Windows Server 2025 与 Debian 13 未在本任务复验；不得据 Windows 11 结果将其描述为已验证。
