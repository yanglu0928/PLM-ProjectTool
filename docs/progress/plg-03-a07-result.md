# PLG-03-A07 Hosted PG18 验收结果

- 日期：2026-11-07
- WBS：PLG-03-A07，CR-EXEC-054
- 结论：PASS_SCOPE_LIMITED
- Hosted run：[42354245934](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42354245934)
- 专项 Job：[128350519897](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42354245934)
- 验证来源提交：`abfd4f0384091103b676e6cfc98026f87f09bddf`（Pull Request merge ref）
- 环境：GitHub Hosted Azure Windows Server 2025，D: runner workspace/temp，父包临时 PostgreSQL 18.6
- 父包 SHA-256：`650027782c507f776e9d4f69c3f98ca296a414ed43a268c837ca935a2535cfa2`

## 通过的验收

- PluginExecution RUNNING、同绑定 OutputRequest 与 Job/Lease/Attempt 在同一 UoW 原子转为 FAILED；仅接受三个冻结错误码并设置不可重试。
- Plugin 状态事件和两个 Owner 的 Audit 与失败状态共用事务；注入 Plugin Audit 故障时，Output、Job/Lease/Attempt、PluginExecution root/event 全部回滚。
- stale fencing、错误 worker、错误绑定、非白名单错误码及不满足 RUNNING 前置均拒绝且无业务写。
- 无插件子进程、无 Worker 接线、无客户数据、无外部调用、无正式 trust，未具备发行资格。

专项日志 marker：`PLG_03_A07_PG18_PASS`，状态为 `PASS_SCOPE_LIMITED`。本项无 API、Schema 或 Migration 变化。

## 同轮回归与独立失败

同一 workflow 的 Backend 全量测试/wheel、Frontend 测试/build、PG18 sidecar、父包组装、A05、A06、P25、P40、A17、A34、A35、P24、P39 与 A50 均成功。20 个 Jobs 中 19 个成功，唯一失败为独立的 SUR-07-A08 packaged SurveyVersion：

`initdb.exe` 仍退出 `3221225781`；只读临时环境探针同码失败，`target_initdb_temp_env_applied=no`，阶段 `SUR_07_A08_STAGE_TARGET_PG_TEMP_ENV_PROBE_DONE)，没有业务 marker。依 CR-EXEC-039，该 TEMP/TMP 假设路线保持停止；A08 仍 NOT_PASSED。整轮 workflow 不是全绿。

该结果仅证明 A07 独立合成 PG18 Owner 验收。它不代表 Windows 11 实机、正式 Publisher trust、Gate 3、Pilot 或正式多平台 Release 通过。代码与验证只在 GitHub Hosted D: 执行，本机/C 盘未运行。
