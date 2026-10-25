# PLT-PKG-01-A09-P51-A11：当前候选包 PostgreSQL 逻辑备份恢复前置

日期：2026-10-25。状态：`PRECHECK_PASS_SCOPE_LIMITED`；编码前检查完成，尚未执行恢复验收。

## 编码前检查

|项目|结论|
|---|---|
|当前Phase/WBS|Phase 2 / `PLT-PKG-01-A09-P51-A11`|
|输入基线|`CR-EXEC-002`；固定P51候选SHA-256 `3cbd68aaad08b111fdf809575915358d7d7737a266990ed6bd3df23f2326f455`；冻结Plan GET/审计/幂等收据结构；A09 API进程与A10 PG进程重启限定证据|
|前置任务|P51-A03包内PG/HTTPS、A04 Survey Review、A05 Prototype、A06 Solution身份、A07 Plan身份、A08跨项目隔离、A09 API重启及A10 PostgreSQL正常重启均在限定范围通过|
|唯一问题|固定候选包携带的PostgreSQL工具能否将本轮隔离数据库逻辑备份恢复至新建的本轮隔离目标数据库，并保留被验Plan及其Audit/完成收据/Review决定计数|
|涉及模块/实体|仅调整包内smoke生命周期/只在本轮启动的PG二进制执行 `pg_dump`、`pg_restore` 与一次性验收器；不改产品API、ORM、Migration、安装或正式数据库|
|涉及权限|只使用本轮smoke的合成数据库角色、临时端口和合成Plan；不访问正式Vault目标以外的凭据，不连接现存数据库或客户数据|
|验收标准|Edge/HTTPS创建合成Plan；对源库作custom-format逻辑备份；新建空目标库并恢复；目标库Plan字段、Audit/收据/Review决定计数与备份时源库一致；备份文件及临时库、服务、Vault目标在验收结束后清理；固定候选SHA不变|
|风险|逻辑备份/恢复仅证明本候选包PG工具与合成Schema/数据路径可用，不代表物理备份、时间点恢复、异机/异版本恢复、正式服务账户授权、完整灾备RTO/RPO、Windows服务自动恢复、安装或发行；任一恢复失败均保留错误并由本轮smoke清理自有资源|

## 实施方案与回退

- 在 `smoke_packaged_platform_write_https.py` 中只向当前拥有的已授权回调暴露一次性备份/恢复hook；hook限定源连接参数、目标数据库名和备份路径均由smoke内部生成，使用参数数组启动候选包内工具，不经过shell。
- 使用 `pg_dump --format=custom --no-owner --no-privileges` 备份本轮数据库；通过本轮 `poc_admin` 在同一临时集群中创建唯一空目标数据库，再用包内 `pg_restore --exit-on-error --no-owner --no-privileges` 恢复。只读比较关键Plan字段与Audit、完成收据、Review决定数量，不改源库。
- 不切换产品API数据库连接、不暂停/删除源PG集群、不引入固定/生产路径；验证器断言仅接受本轮随机库名和临时目录。备份文件恢复后立即删除，源/目标数据库均随隔离PG集群整体清理。
- 如增加的动态hook穿过严格旧回调合同不兼容，则改为限定smoke生命周期内的 `ContextVar`，回调结束复位；不弱化权限或清单检查。回退只需移除新增测试hook/验证器，固定候选与P39安装流程不变。

## 预期文件与验收

- 修改 `tools/smoke_packaged_platform_write_https.py` 与对应定向单测；新增 `validation/plt-pkg-01-a09-p51-a11-postgres-restore-packaged/verify.py`；更新本记录、`STATUS.md` 和 `CHANGELOG.md`。
- 运行包内smoke定向单测、Python语法检查、固定候选完整Edge/HTTPS/隔离PG回归、候选SHA和Stage清单复核，以及临时进程/目录/Vault清理核验。
- 本片不涉及Migration/API/依赖，也不改变正式信任、Pilot、Gate 3或正式发行结论。若候选中缺少所需工具或restore失败，记录客观阻塞并转向其他独立任务，不宣称PASS。
