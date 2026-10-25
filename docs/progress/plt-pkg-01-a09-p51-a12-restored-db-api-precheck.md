# PLT-PKG-01-A09-P51-A12：恢复库经候选API读取前置

日期：2026-10-25。状态：`PRECHECK_PASS_SCOPE_LIMITED`；编码前检查完成，尚未执行服务层恢复库验收。

## 编码前检查

|项目|结论|
|---|---|
|当前Phase/WBS|Phase 2 / `PLT-PKG-01-A09-P51-A12`|
|输入基线|`CR-EXEC-002`；固定P51候选SHA-256 `3cbd68aaad08b111fdf809575915358d7d7737a266990ed6bd3df23f2326f455`；冻结Plan GET与成员Session合同；P51-A11限定逻辑恢复证据|
|前置任务|A11已在本轮临时PG中恢复Schema及合成数据并验证Plan/Audit/收据/Review计数；源库与恢复库同属一次性smoke，API/Caddy及当前合成Session仍在运行|
|唯一问题|当候选API的Credential Manager数据库URL暂指向A11恢复库并重启本轮API进程后，同一个既有HTTPS授权Session能否读取恢复出的同一Plan且字段一致|
|涉及模块/实体/API|只修改包内smoke验收编排和一次性验证器；调用冻结Plan GET，不改产品API/ORM/Migration/权限/启动配置|
|涉及权限/秘密|仅处理smoke刚创建且仍与精确源URL匹配的 `PLMProjectTool/Database` 测试凭据；不输出URL/密码、不写命令行或日志；授权Session仅为临时合成用户。对当前Credential Manager值任何不匹配均失败关闭，不覆盖/删除未知凭据|
|验收标准|记录源库Plan；调用A11同一恢复Hook；确认DB Credential Manager值等于本轮源URL后切换至恢复库URL；重启本轮API、保持Caddy/PG不变；原Cookie Session经HTTPS GET该Plan=200且字段匹配；无额外Plan/Audit/收据/Review写入；随后恢复原数据库URL、重启API回源库，确认原值读回、进程/临时Vault/数据库/目标库/备份/目录清理、候选SHA不变|
|风险/回滚|Windows Credential Manager值是宿主交互账户Secret，虽为smoke新建也须逐字确认拥有权，finally路径无条件恢复原URL；若写入、重启或读回失败，先恢复精确原值并让smoke停止所拥有进程，不能继续删未知Vault项或数据库。此验收仅合成运行态连接切换，不是正式服务账户、生产数据库切换或灾备批准|

## 方案与回退

- 复用A11当前callback生命周期内的隔离恢复库与已验证备份结果；新增 `activate_restored_database`/`restore_source_database` 成对hook，严格封装原URL、恢复URL与本轮API restart闭包。激活前读取并比较原URL，激活后只用当前smoke持有的URL更新目标；任何异常均尝试原URL恢复并重新启动原数据库API。
- 验证器先保存源Plan快照；激活恢复库后只通过原 HTTPS client 和原Cookie Session GET同一Plan；随后在finally执行恢复源库操作。调用API回读后再直接查恢复库，对照字段和Plan/Audit/收据/Review计数，且确认URL已恢复。
- 无产品/API/Schema/业务数据修改；若修改smoke helper无法保证凭据总能恢复，则停止A12并保持A11结果独立，不扩大到任何宿主服务。

## 预计文件与验证

- 修改 `tools/smoke_packaged_platform_write_https.py`、对应单测，新增 `validation/plt-pkg-01-a09-p51-a12-restored-db-api/verify.py`；更新本记录、`STATUS.md`、`CHANGELOG.md`。
- 候选包内运行完整Edge/HTTPS/隔离PG链，定向smoke单测、语法、Stage/hash、临时Vault/进程/备份/目录清理全验；固定候选SHA不变。
- 本片不证明正式启动、Pilot、Gate 3、客户事实、生产数据恢复或Release通过。
