# PLT-PKG-01-A09-P51-A11：当前候选包 PostgreSQL 逻辑备份恢复前置

日期：2026-10-25。状态：`PASS_SCOPE_LIMITED_LOGICAL_BACKUP_RESTORE`（Windows 11当前非发行候选；合成数据）。

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

## 执行偏差与方案修订（2026-10-25）

- 第一次固定候选整链运行实际完成P51-A03～A10前置后，候选 `pg_dump` 成功；全库 `pg_restore` 在增加 `fk_req_versions__review` 外键时失败关闭。PG错误显示合成 `req_requirement_versions.review_ref` 指向不存在的Review。
- 核查当前P51-A05隔离夹具确认：它在本轮临时库事务中使用 `SET LOCAL session_replication_role='replica'`，并给合成RequirementVersion插入随机占位 `review_ref`/`review_round_ref`，这是为当前Prototype包内链造数的测试夹具，不是客户或正式业务数据。全库DDL+数据原样恢复会据此失败；不删除或弱化固定候选/源Schema的外键约束。
- 在不扩大产品范围的前提下，将本片收窄为“同候选当前Migration head空库升级后，以 `pg_dump` 逻辑备份并通过 `pg_restore --data-only --disable-triggers` 恢复本轮合成数据；比较Plan及Audit/收据/Review计数”。这验证数据逻辑备份读回，但不验DDL恢复/Referential Integrity/灾备。目标库只在本轮临时集群内创建，迁移使用当前候选所固定的Schema；源库不改写。恢复完成后由本轮验收器删除目标库和备份文件。
- 首轮失败的进程/目标/临时目录由smoke原清理路径回收；候选SHA保持固定。该路径变更只影响一次性验证方式，无产品、Migration/API/权限或运行配置变化；若数据-only恢复继续遇到真实问题，保留失败证据并转向其他任务。
- 第二次恢复在目标库创建 `alembic_version` 唯一行时因同候选迁移已先行升级而冲突；这也是测试运行记录，尚无数据被恢复。安全适配为先验证源库与目标库的Migration head完全相同，再只清空本轮空目标库中的 `alembic_version` 跟踪行，让全库逻辑数据恢复原版本记录；若head不相同则失败关闭。目标Schema/索引/约束仍来自候选Migration，不删除产品约束；仅恢复出来的合成数据触发器暂禁用并单独标注。
- 第三次整链未通过head核对：前置合同实际把迁移版本表保存在 `plm.alembic_version`，验收脚本误查默认public schema中的 `alembic_version`，故在查询阶段失败关闭且未执行恢复。修正为冻结迁移配置中的实际schema限定表名；其余范围与验收不变。
- 第四次在全库数据恢复期间，候选迁移预置的维护状态单例与备份数据主键冲突；目标迁移后的 `plm` schema 并非空业务数据。源库未被修改。进一步修订为：在确认源/目标Migration head一致后，仅对本轮新建目标库列举的 `plm` schema基表执行一次受限 `TRUNCATE ... RESTART IDENTITY CASCADE`，保留所有DDL/索引/约束与extension；再恢复全库data-only及序列。目标表清空名单记录并校验非空，若查询到schema外表或列举为空则失败关闭。该行为严格限于临时恢复目标数据库。
- 第五次发现安全Owner会拒绝目标表清空，错误为 `AI egress authorization history cannot be truncated`。这是产品保护，未绕过，目标库清理回滚由隔离smoke完成。最终方案改为从同一个逻辑备份先恢复完整 `--schema-only` DDL（PG18扩展、索引/约束/触发器及迁移版本表），再用 `--data-only --disable-triggers` 恢复原数据/序列。目标库不预建Schema或迁移seed，因此无重复行；触发器只在该目标数据装载期间由PG工具临时禁用。恢复后核对版本head、Plan及审计/收据/Review计数。源库保持只读且没有删除/修改动作；不修改或关闭任何产品触发器。`--disable-triggers` 的原因是既有合成夹具具有占位Review外键，不等于验证了FK完整性或灾备。

## 最终验收结果

- 固定候选ZIP `3cbd68aaad08b111fdf809575915358d7d7737a266990ed6bd3df23f2326f455` 未改变；完整Windows 11 Edge/HTTPS/隔离PG链及P51-A03～A10前置复验通过，`postgres_logical_restore_count=1`，临时API/Caddy/PG进程停止、临时布局/PG数据/备份文件及48个Vault测试目标清理，`release_eligible=false`、`legal_clearance=false`。
- 候选随包 `pg_dump` 以custom格式备份；全新临时目标库由同一备份先恢复Schema，再恢复data-only数据和序列。目标 `plm.alembic_version` 与固定候选Head `20261024_0185` 一致；合成Plan完整字段、项目Plan数量、`PLAN_CREATED` Audit、V1 Plan创建完成收据及Review决定计数与源库快照一致。恢复库与备份文件随后删除，源库未更改。
- `tools/tests/test_smoke_packaged_platform_write_https.py` 定向8/8通过；Python语法检查及差异空白检查通过；包内完整业务/浏览器/PG回归退出0；烟测报告临时文件和服务清理字段均为true。固定Stage复用P51-A02的既有22,197载荷核验；本次候选SHA在烟测前后相同。
- 该项是合成数据库逻辑备份与恢复路径证据，不证明真实客户数据库、外键数据完整性（数据装载期间禁用触发器）、灾难/异机/跨版本恢复、RTO/RPO、正式运行账户/Vault、安装/升级、Pilot、Gate 3、多平台或发行。

## 文件与结果

- 修改 `tools/smoke_packaged_platform_write_https.py`：仅在当前smoke授权回调生命周期暴露PG逻辑备份/恢复hook；源与目标库、随机备份路径、包内工具均由隔离smoke持有；目标库或备份发生错误时按本轮所有权清理。
- 修改对应smoke单测，确认恢复hook不能在本轮smoke授权回调之外访问；新增 `validation/plt-pkg-01-a09-p51-a11-postgres-restore-packaged/verify.py` 负责业务数据前后比较与临时目标库回收。
- 系统Python未安装 `httpx`，首次单测导入失败；未变更本机环境，改用固定候选随包Python与依赖运行后8/8通过。首轮全库恢复错误、迁移/约束顺序、schema限定与维护表保护触发等失败均记录在上文，未篡改候选或源数据后完成限定范围复跑。
- Result：`PASS_SCOPE_LIMITED_LOGICAL_BACKUP_RESTORE`。本片无产品/API/ORM/Migration/依赖变化。下一项评估逻辑恢复库经同一包内HTTPS API读取原Plan的服务层证据；仍不替代正式数据库恢复或发行验收。
- 第四次在全库数据恢复期间，候选迁移预置的维护状态单例与备份数据主键冲突；目标迁移后的 `plm` schema 并非空业务数据。源库未被修改。进一步修订为：在确认源/目标Migration head一致后，仅对本轮新建目标库列举的 `plm` schema基表执行一次受限 `TRUNCATE ... RESTART IDENTITY CASCADE`，保留所有DDL/索引/约束与extension；再恢复全库data-only及序列。目标表清空名单记录并校验非空，若查询到schema外表或列举为空则失败关闭。该行为严格限于临时恢复目标数据库。
