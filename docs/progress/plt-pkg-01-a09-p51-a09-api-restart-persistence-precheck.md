# PLT-PKG-01-A09-P51-A09：当前候选包 API 重启持久性前置

日期：2026-10-25；状态：`PREFLIGHT_PASS_RUN_PENDING`。

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
