# PLT-PKG-01-A09-P51-A10：当前候选包 PostgreSQL 重启持久性前置

日期：2026-10-25；状态：`PASS_SCOPE_LIMITED_POSTGRES_RESTART_PERSISTENCE`（Windows 11 当前非发行候选；合成数据）。

## 编码前检查

|项目|结论|
|---|---|
|当前Phase/WBS|Phase 2 / `PLT-PKG-01-A09-P51-A10`|
|输入基线|`CR-EXEC-002`；固定P51候选SHA `3cbd68aaad08b111fdf809575915358d7d7737a266990ed6bd3df23f2326f455`；冻结Plan GET与Session合同|
|前置任务|P51-A03包内PG/HTTPS、A04 Survey Review、A05 Prototype、A06 Solution身份、A07 Plan身份、A08跨项目隔离及A09 API进程重启持久性均在限定范围通过|
|唯一问题|在API/Caddy继续运行时，对本轮smoke拥有的隔离PostgreSQL执行正常fast stop/start后，既有Plan与授权成员Session能否继续经HTTPS使用|
|涉及模块|仅改包内smoke生命周期编排和新增一次性验证器/单测；不修改产品API、SQLAlchemy、Migration、PG安装、服务配置或生产数据|
|验收标准|创建Plan并记录PG状态；仅通过该临时PG `pg_ctl` fast stop、同数据目录/端口/配置start；等待PG与API健康后用原授权成员HTTP Session读Plan=200且响应一致；Plan/Audit/收据/Review决定计数不变；临时PG/API/Caddy、Vault目标与目录清理，固定候选SHA不变|
|风险与回滚|仅操作本轮唯一临时`pgdata`与本轮启动进程；正常停止而不删数据目录直至验证通过；失败时继续尝试精确数据目录停止并保留故障诊断，不触碰现存服务/数据库、`C:\PLMTool`、客户资料或SCM|

## 代码与组合核查

- `tools/smoke_packaged_platform_write_https.py` 在当前smoke中独占`pgdata`、随机loopback端口、PG二进制路径及`pg_started`清理状态，初始start已使用确定的`pg_ctl -D <owned-data> -l <owned-log> -o "-h 127.0.0.1 -p <owned-port>" -w start`组合。
- 新的PostgreSQL重启hook只在本轮`licensed_https_probe`期间通过隔离动态上下文暴露；同A09相同，不能影响产品、其他回调签名或在smoke外取得。先fast stop，重新标记清理责任，再用原数据目录/日志/端口参数启动；API/Caddy保持运行。
- A09的Plan创建器及`observer_client`已提供真实Edge写入的Plan ID/会话。测试回调在重启前后读取同一目标、核对Session和响应，并对照Plan、Audit、完成收据及Review决定计数；重启后如pool连接失效，不进行自动隐藏重试，按实际HTTP结果记录。
- 不更改运行时迁移、DB数据、权限或冻结API，无需CR。该项不等于异常断电恢复、物理备份/恢复、Windows Service自动恢复、正式安装或Release结论。

## 最终验收结果

- 固定候选SHA-256 `3cbd68aaad08b111fdf809575915358d7d7737a266990ed6bd3df23f2326f455` 未改变；Windows 11当前候选Edge/HTTPS/隔离PG18完整链退出码0。
- 浏览器创建Plan后，验收器保留Caddy与API进程，只使用本轮随机临时数据目录对候选内PostgreSQL执行 `pg_ctl fast stop` 并按相同数据目录、日志与loopback端口执行 `pg_ctl start`；PG readiness和SQL `SELECT 1`通过。
- 原授权成员Session在PG停止/启动后仍经候选HTTPS读取同一Plan=200，响应字节对应字段不变；DB仍保存ACTIVE Plan、批准指针NULL。Plan/Audit/完成收据/Review决定计数前后不变。
- Smoke结果 `postgres_restart_count=1`、`api_restart_count=0`、`temporary_processes_stopped=true`、`temporary_files_removed=true`、48个临时Vault目标已清理、`fixed_candidate_unmodified=true`。候选SHA复核一致，无本轮A10临时目录/服务残留。
- 验证：包内smoke定向单测8/8通过，Python AST语法通过，Stage全量22,197项与Hash清单一致。仅此项运行包内PostgreSQL正常fast stop/start；未做备份/restore、异常断电、Windows Service恢复或产品升级。

## 文件与兼容性

- 修改 `tools/smoke_packaged_platform_write_https.py`，增加作用域受限的PostgreSQL重启hook；smoke外或回调外无法获取；cleanup仍保有同一PG数据目录停止责任。
- 修改对应smoke单测，确认重启hook不能在拥有的隔离回调外获取；新增 `validation/plt-pkg-01-a09-p51-a10-postgres-restart-packaged/verify.py` 完成包内数据与Session验收。
- 无产品、API、ORM、Migration、权限或依赖变化；不影响候选包字节。候选 `release_eligible=false`、`legal_clearance=false`。
- Result：`PASS_SCOPE_LIMITED_POSTGRES_RESTART_PERSISTENCE`。该结果不证明物理备份或灾难恢复。下一项按 `SOL-03-A06-P03-A03` 复核路线，先实现项目当前已批准RequirementVersion全集的受权同事务只读Port，作为Outline覆盖证明的可信全集输入。
