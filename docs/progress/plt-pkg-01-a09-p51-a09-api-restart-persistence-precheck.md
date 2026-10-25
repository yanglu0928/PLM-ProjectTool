# PLT-PKG-01-A09-P51-A09：当前候选包 API 重启持久性前置

日期：2026-10-25；状态：`PASS_SCOPE_LIMITED_API_RESTART_PERSISTENCE`（Windows 11 当前非发行候选；合成数据）。

## 编码前检查

|项目|结论|
|---|---|
|当前Phase/WBS|Phase 2 / `PLT-PKG-01-A09-P51-A09`|
|输入基线|`CR-EXEC-002`；固定P51候选SHA `3cbd68aaad08b111fdf809575915358d7d7737a266990ed6bd3df23f2326f455`；冻结Plan GET与Session合同|
|前置任务|P51-A03包内PG/HTTPS；A04 Survey Review；A05 Prototype；A06 Solution Outline身份；A07 Plan身份；A08 Plan跨项目读取隔离均在限定范围通过|
|唯一问题|在临时PostgreSQL继续运行时，停止并按同一候选配置重启包内API进程，确认既有合成Plan及数据库会话仍可被授权成员HTTPS读取|
|涉及模块|P51 package smoke临时API进程控制与新增一次性验证；不改产品Owner/API/ORM/Migration/启动配置/服务安装|
|验收标准|Edge/HTTPS创建Plan；重启API而保持同一临时PG/Caddy及HTTP配置；既有成员会话经HTTPS读取该Plan为200且字段与数据库一致；重启前后不新增Plan/Audit/收据/Review决定；候选SHA不变，所有进程、48个临时Vault目标及布局清理|
|风险与回滚|仅操作由本轮验收器启动的临时API进程与一次性数据库；不触碰用户运行的Edge、正式SCM/服务、`C:\PLMTool`、现有数据库或客户数据。若Session非持久或重启失败，记录失败证据并保持Release/Pilot状态不变|

## 代码与组合核查

- `tools/smoke_packaged_platform_write_https.py` 在 `smoke()` 内持有本轮 API `Popen`、固定bootstrap、隔离env、loopback API端口及就绪探测；只需向可选验收probe暴露受限的 `restart_api` 回调，重启同一候选命令并以 `/health/ready` 等待就绪。清理仍停止最终持有的进程句柄。
- P51-A07/A08 Edge已证明Plan身份存在；package callback上下文同时提供 `observer_client`、项目ID及独立PG读连接。新增验收可先由Edge创建合成Plan，再重启API，通过仍持有的授权成员HTTPS Session读取；PG对比Plan/Audit/幂等收据数量和计划字段。
- 仅一次合成数据库；Caddy和PG不重启、不升级；不以候选API健康返回代替业务读取，也不把进程重启测试解释为OS/服务账户/自动恢复/正式安装或Pilot通过。
- 无冻结API、Schema、权限或产品行为变化，不需要CR。编码前检查已覆盖对象、输入、方案、失败处理、回滚与验收，允许新增测试编排代码。

## 最终验收结果

- 固定候选SHA-256 `3cbd68aaad08b111fdf809575915358d7d7737a266990ed6bd3df23f2326f455` 未改变。全包Windows 11 Edge/HTTPS/隔离PG18链退出码0；P51既有Handover、Survey、Prototype、Solution身份、Plan身份与跨项目隔离回归均通过。
- Edge先创建合成Plan；通过隔离PG连接核对Plan身份后，`restart_api` 仅停止并重启本轮smoke创建的候选API进程。PostgreSQL与Caddy保持运行。重启后原授权成员的既有HTTP Session仍可经HTTPS读取同一Plan，状态200且响应字段与重启前一致。
- 数据库前后对比：Plan总数、`PLAN_CREATED` Audit数、`V1_PLAN_CREATE`完成收据数及项目Review决定数均无变化；目标Plan仍ACTIVE、批准指针NULL。未产生新的Plan/Audit/收据/Review决定。
- Smoke结果 `api_restart_count=1`、`temporary_processes_stopped=true`、`temporary_files_removed=true`、48个临时Vault目标清理、`fixed_candidate_unmodified=true`；测试后复核候选SHA一致，未发现本轮P51-A09服务进程或临时目录残留。
- 验证：当前候选内包依赖路径下 smoke 定向单测7/7通过；Python AST、`git diff --check`通过；固定Stage清单22,197项核对通过。

## 执行偏差与兼容性

- 首次完整运行未触发API重启：重启hook作为新关键字一路穿过既有strict参数验证适配器，旧Owner以`TypeError`拒绝。Smoke异常清理成功；没有产品请求失败或候选变更证据。
- 调整为在包内smoke调用期间通过 `ContextVar` 暴露一次性重启hook，并在回调退出后复位；不向旧业务探针签名增加参数，不影响普通smoke调用。新增测试确认生命周期之外取不到hook，再完成7项单测和完整候选包重跑。
- 初次单测误将Python字节码写入复用Stage，严格清单检查拒绝继续。已按精确Stage/包目录核对路径后，只清除本轮测试生成的501个`.pyc`文件，未删除源payload；Stage重新核验22,197项通过，随后用`-B`运行测试避免重写。该拒绝保护有效，不放宽清单策略。
- 兼容性：仅变更smoke测试编排和新增隔离验证脚本/单测；无产品/API/Schema/Migration/依赖变化。候选仍`release_eligible=false`、`legal_clearance=false`。本项不证明Windows服务管理器自动恢复、PostgreSQL重启/备份恢复、正式安装/信任、Pilot、Gate、其他平台或正式发行。

## 文件与结果

- 修改 `tools/smoke_packaged_platform_write_https.py`：暴露仅在当前smoke回调动态上下文内有效的owned API restart hook；离开probe后立即复位，最终cleanup继续停止新进程。
- 修改 `tools/tests/test_smoke_packaged_platform_write_https.py`，新增hook越界不可取单测；新增 `validation/plt-pkg-01-a09-p51-a09-api-restart-packaged/verify.py` 执行Plan/Session重启持久性真实包验收。
- Result：`PASS_SCOPE_LIMITED_API_RESTART_PERSISTENCE`。下一项继续在固定候选包内核查临时PostgreSQL正常停止/启动后的Plan与授权Session读取；不把此项推断为备份恢复或生产数据库恢复能力。
