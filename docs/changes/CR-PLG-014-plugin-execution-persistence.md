# CR-PLG-014：PluginExecution 持久化基础

- 日期：2026-11-05
- 阶段/WBS：Phase 2 Platform Core / PLG-03-A01
- 状态：编码前检查 PASS_WITH_LIMITATION，可按冻结模型实现持久化基础
- 基线：Gate 2 冻结 PluginExecution R-PRJ Aggregate、PLG-03；SC-01 映射 `plg_executions`、`plg_execution_result_files`、`plg_execution_state_events`。
- 来源：P32证明后续OutputArtifact固定FK依赖PluginExecution物理Root；OutputArtifact必须等待本项。

## 编码前核查

当前冻结模型已定义单次插件执行身份、PROJECT Scope、installation/operation、固定OutputContext/fingerprint、Job/attempt/idempotency、PENDING/RUNNING/SUCCEEDED/FAILED/CANCELLED、result manifest/fingerprint、安全错误码、时间及trace。当前分支已有Package/Installation/EnabledOperation/RuntimeValidation数据及Jobs/Output/Document基础，但没有PluginExecution ORM/表/Migration与Owner。

## 决策及范围

本WBS只建立冻结PLG-03持久化结构：Execution Root、append-only result-file references与state events，ORM/Alembic/DB约束/索引；约束ProjectId与OutputRequest/Context、PluginInstallation/EnabledOperation及Job关系。没有执行器、文件移动/创建、生产写Owner、API、默认Worker挂载或Plugin subprocess。执行表初始写入保持DB trigger closed；迁移验证夹具仅用隔离合成行。

Result field只保存安全引用/指纹和受控错误码，不存储stdout、完整客户Context、绝对工作路径、traceback、Secret或文件正文。合法生成内容进入Artifact的流程仍必须以后独立核验FileObject/DocumentVersion/PluginExecution/Hash全部一致。

## 风险与验收

- 状态与事件表必须保持同一Project与Execution身份；结果文件必须引用已有FileObject并拒绝跨Project记录。
- empty DB升级、含既有合成数据升级、空库downgrade/reupgrade；有Execution历史时downgrade必须拒绝并保留行。
- 验证状态白名单、时间约束、Attempt/Job幂等唯一语义、复合FK、result-file引用、append-only、TRUNCATE保护和Owner write closed。
- 后端全量测试/wheel、hosted PostgreSQL 18.6真实Migration/verifier及父包PG smoke；测试通过前不得称Artifact链可用。
- 仅GitHub hosted Windows runner D盘；无客户数据、Plugin运行或外部API调用。P25仍独立blocked。
