# PLAN-02-A04-P04-A04-P02-A03-P02-A02：Windows 显式 Trace 图启动模式

日期/版本：2026-10-19（2026-10-23 验收）/ `0.1.0-dev.0`。状态：Windows 显式模式内部验收通过；正式部署信任与 Pilot 仍未通过。

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `PLAN-02-A04-P04-A04-P02-A03-P02-A02`|
|输入基线|冻结API-02图查询、P02-A03-P01可选HTTP、P02-A03-P02-A01 Win11/PG受控组合工厂和独立当前账户`trace-graph-cursor-v1` Key来源|
|前置任务|现有`--platform`/`--platform-write`无图Key要求；正式目标账户Key未供给，不能静默加为旧模式启动前置|
|涉及模块/实体|Windows服务启动选择、生产组合根和可选图路由槽；无Schema实体变化|
|涉及API/权限|冻结图GET路径仅显式Trace模式挂载；现有Session/License/逐节点Project权限不变，缺Key拒绝启动|
|验收标准|新模式选择、路由存在、旧模式404、无Key/错Key/组合故障失败关闭且资源释放、定向/全量回归|
|风险|错误复用其他Cursor Key、旧模式启动回归、合成当前账户测试误报正式账户可信、正式Key供给缺失|

新增`--platform-trace`只读与`--platform-write-trace`读写模式，只改变显式组合选择，不把真实密钥写入配置、环境变量或Git。正式目标账户Key、正式License信任与安装恢复仍独立验收；本片不宣称Pilot或发行通过。

## 独立验收

- 定向合同：4 项通过，含 2 个模式选择子例；旧`--platform`维持图路由 404，新读模式挂载后无 Session 返回 401；缺少专用 Key 时启动拒绝且数据库运行时释放；读写模式明确选择写组合及图组合。
- 专用 Key 读取器的缺失、无效、异常及备份恢复由既有`test_windows_trace_graph_cursor.py`覆盖；本片不生成或提交正式 Key。
- Windows 11 后端完整回归：`3847 passed, 3 skipped, 6023 subtests passed`，退出码 0；`git diff --check`通过。本片无数据库迁移、冻结路径或默认启动模式修改。
- 适用边界：只证明本地代码与合成测试环境的显式装配；目标服务账户 Vault/ACL、公钥、安装/重启/升级和真实浏览器业务链均未在本片验收。
