# PLG-03-A07 PluginExecution不可重试失败原子Owner实现同步

- 日期：2026-11-07
- Change Request：CR-EXEC-054
- 状态：实现已同步；GitHub Hosted PG18与完整回归待验收
- 前置：PLG-03-A06恢复验收PASS_SCOPE_LIMITED（CR-EXEC-055；run 42350824543专项Job 128340182737）

## 本次实现

- 增加 PluginExecution Failure Owner 与 SQLAlchemy Repository；有效OutputGenerate claim和精确Project/Job/attempt/OutputRequest/Context绑定下，仅允许RUNNING进入FAILED。
- OutputGenerationFailureOwner增加调用方事务入口，原独立fail()包装保留；同一个UoW按Output→Jobs→Plugin顺序更新OutputRequest、Job/Lease/Attempt与PluginExecution，并各写对应Audit/状态事件。
- 错误码沿用冻结Output failure allowlist，Plugin与Jobs均标记不可重试；Audit/Owner任一失败由外层UoW全回滚。未新增API/Schema/Migration、Worker/ProcessHost、子进程、文件输出或默认装配。
- 新增单元测试与同轮Windows父包内临时PG18.6专项验证器/Hosted job；Secret扫描和Hosted独立验收待提交后执行。

## 边界

本项只建立可复用的事务失败Owner，不代表Worker/ProcessHost接线、真实插件执行、正式信任、输出文件生成、Windows 11实测、Gate、Pilot或Release通过。无客户数据或外部调用。