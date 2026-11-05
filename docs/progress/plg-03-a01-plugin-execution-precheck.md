# PLG-03-A01 编码前检查：PluginExecution 持久化基础

- 日期：2026-11-05
- 结论：PASS_WITH_LIMITATION，可实现冻结的持久化骨架
- 变更记录：[CR-PLG-014](../changes/CR-PLG-014-plugin-execution-persistence.md)

## 源码与冻结基线

冻结Data Model规定 PluginExecution 是 PROJECT R-PRJ Aggregate，保存 plugin_execution_id、project_id、Installation/operation、固定OutputContext/fingerprint、Job/attempt/idempotency、受控状态、结果清单指纹、错误码和执行时间。SC-01明确主表 `plg_executions`，owned tables包括 `plg_execution_result_files` 和 `plg_execution_state_events`。SC-02要求R-PRJ Scope/Project隔离与不可变运行历史。

本分支已经有 PLG-01/PLG-02 包、Installation、EnabledOperation、RuntimeValidation表，以及 Job、OutputRequest/Context、FileObject和DocumentVersion；当前plugin ORM/migrations中没有PLG-03 Execution表/Root/Owner。这是后续OutputArtifact(Project FK)无法实现的真实依赖。

## 单一范围

本WBS建立PLG-03三张表的ORM/Migration/约束/索引，并在隔离synthetic PostgreSQL fixture中验证引用与历史保护。数据库生产写入Trigger继续关闭，不增加API/默认组合；不执行插件子进程，不创建/移动/打开任何产品文件。

依赖设计采用项目复合FK，避免Execution、OutputRequest、Context、Installation/EnabledOperation和Job跨项目/对象漂移。Result File只能指向同项目现有FileObject并记录受控结果元数据；StateEvent追加且禁止update/delete/truncate。stdout/客户正文/绝对路径/traceback/Secret不进入表。

## 验收和限制

由GitHub hosted Windows Server 2025 runner在D盘临时区执行：空库升级、既有合成数据升级、空库降级/重升、有历史降级拒绝、Owner write-closed、项目隔离/Attempt和state event负例，以及后端全量/wheel和父包PG smoke。

本WBS通过只证明持久化Schema，不证明Plugin签名验证、运行隔离、真实插件执行、Artifact发布、Windows 11实机、Pilot、Gate 3或正式Release。P25的initdb问题独立保留。
