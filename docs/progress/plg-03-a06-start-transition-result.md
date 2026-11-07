# PLG-03-A06：PluginExecution PENDING→RUNNING 状态Owner验收记录

- 日期：2026-11-07
- Change Request：CR-EXEC-053
- 结果：PASS_SCOPE_LIMITED
- 源提交：e51389455c165e5081a9d72f61b800c13dbe549a
- Hosted run：[42348507961](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42348507961)
- 专项Job：128333157541（成功）

## 验收结果

同轮Windows非发行父包内的PostgreSQL 18.6临时库运行真实迁移与SQLAlchemy UoW。当前OutputGenerate lease/fencing与PluginExecution的Project/Job/attempt/OutputRequest/Context绑定一致时，Owner把PENDING变为RUNNING，并在同事务更新started_at/lock_version、追加状态事件和Audit。审计失败时root与事件回滚。RUNNING重放返回changed=false且无重复事件/Audit。stale fencing、错worker、错误Output绑定、attempt 2及终态均被拒绝且零事件/Audit写。

同轮Backend全量测试/wheel、Frontend/build、P40 live Edge/PG18及A34包替换/恢复演练通过。整run唯一失败为A08 packaged SurveyVersion flow：initdb与TEMP/TMP对照返回3221225781，替代环境未应用，详见CR-EXEC-039；不影响A06独立结论，但全run非全绿。

## 范围限制

仅合成数据与Hosted Windows Server 2025 D盘临时环境。没有插件子进程、默认Worker、真实客户数据、外部调用或正式信任；未改API/Schema/Migration，未验证Windows 11实机、Gate、Pilot或Release。
