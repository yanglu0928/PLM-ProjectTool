# PLG-03-A07 PluginExecution不可重试失败原子Owner实现同步

- 日期：2026-11-07
- Change Request：CR-EXEC-054
- 状态：PASS_SCOPE_LIMITED（GitHub Hosted PG18及全量后端/前端回归完成；同轮独立A08失败）
- 前置：PLG-03-A06恢复验收PASS_SCOPE_LIMITED（CR-EXEC-055；run 42350824543专项Job 128340182737）

## 本次实现

- 增加 PluginExecution Failure Owner 与 SQLAlchemy Repository；有效OutputGenerate claim和精确Project/Job/attempt/OutputRequest/Context绑定下，仅允许RUNNING进入FAILED。
- OutputGenerationFailureOwner增加调用方事务入口，原独立fail()包装保留；同一个UoW按Output→Jobs→Plugin顺序更新OutputRequest、Job/Lease/Attempt与PluginExecution，并各写对应Audit/状态事件。
- 错误码沿用冻结Output failure allowlist，Plugin与Jobs均标记不可重试；Audit/Owner任一失败由外层UoW全回滚。未新增API/Schema/Migration、Worker/ProcessHost、子进程、文件输出或默认装配。
- 新增单元测试与同轮Windows父包内临时PG18.6专项验证器/Hosted job；Secret扫描和Hosted独立验收待提交后执行。

## 边界

本项只建立可复用的事务失败Owner，不代表Worker/ProcessHost接线、真实插件执行、正式信任、输出文件生成、Windows 11实测、Gate、Pilot或Release通过。无客户数据或外部调用。

## Hosted验收结果（2026-11-07）

Hosted run [42354245934](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42354245934) 的A07 job 128350519897通过并输出 `PLG_03_A07_PG18_PASS`。事务成功、Audit故障整体回滚、fencing/worker/binding/error allowlist负例均通过。后端全量与wheel、前端测试与build也通过。整轮20个Jobs有19个成功；唯一失败是按CR-EXEC-039保持停止探查的独立A08 initdb 3221225781，因此整轮workflow非全绿。详见 [A07验收结果](plg-03-a07-result.md)。本结论不涵盖插件执行、正式信任、Windows 11实机、Gate/Pilot/Release。
