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

## 首轮执行记录（2026-10-25）

- 候选包全链在 Handover、Survey 前置通过后，于 P51-A05 Prototype browser 的 `package created` UI 等待超时；Edge已显示包列表页且相关HTTP只读请求成功，但数据列表未在等待时限内出现。异常发生在A11逻辑备份/恢复及A12 Credential Manager切换前；源URL未改写，恢复库hook未调用。
- smoke退出清理路径执行；候选SHA未变。本轮为已知P51-A05浏览器异步就绪竞态，按同一验收标准用新鲜隔离目录重试；不修改上游产品代码或降低UI断言。
- 第二轮再次在同一P51-A05 UI等待点超时，相关Prototype POST=201、列表HTTP=200，界面仍停留空态。A11全链此前已经在相同候选验证Prototype PASS。本A12只依赖Handover/Survey前置上下文及Plan/恢复/API链，因此在A12专用runner中保留已验的A05既有证据并跳过对不相关Prototype UI的重复重跑，继续执行P51-A07以后Plan/重启/恢复链；不修改A05产品代码、不把本轮记为Prototype复验PASS。
- 随后的隔离链成功运行，但最终JSON `api_restart_count=0` 且无A12 marker，证明A12恢复库API回调未执行；不能将该轮视为A12通过。核查发现`runpy.run_path`返回的命名空间dict与其中函数的`__globals__`不是同一对象；此前仅改了返回dict，未影响实际函数全局。将通过函数自身的`__globals__`注入A12后置回调与A05跳过钩子，再做新鲜全链复验。此前该轮源Credential Manager值未被改写，A11自身逻辑恢复检查仍通过。
- A12专用skip钩子接入后，Plan Edge对合成账户登录返回HTTP429，随后游览器拒绝继续。原因是被跳过的既有A05 Prototype验收原本会清理本轮临时PG里的合成 `plm.auth_login_rate_buckets`；检查发现A05只在隔离fixture库做此清理。将同样的清理仅加入A12专用skip钩子，保留既有完整限流规则与其他业务/审计数据；重跑时继续验证真实Edge登录行为。
- 再次运行已成功执行A12 skip、清除本轮限流桶、完成Plan Edge、A08跨项目及A11逻辑恢复；切换Credential Manager到恢复库后，包内API子进程未达到ready。A12安全恢复分支先把原URL写回并重启源库API；固定Credential Manager目标复查不存在，P51临时目录/子进程由清理器回收，恢复库查询尚未通过。本轮错误信息被旧restart helper按摘要隐藏，不能据此确认具体启动错误。
- 隔离Schema restore当前使用 `--no-owner` 且连接为 `poc_admin`，静态审查发现目标表/函数默认归该管理角色所有，API应用角色可能无法读取；后续前置修复在目标库Schema阶段仅授予合成应用角色 `plm` schema及其表/序列/函数所需权限，并在API重启失败时调用已有factory诊断（只返回异常类型/文件/行，不输出连接串）以区分实际原因。曾尝试 `REASSIGN OWNED`，但被系统扩展依赖限制而拒绝；已移除该方式。以上仅作用目标临时库，不改变源库/冻结授权。

## 最终执行结果（2026-10-26）

- P51-A12 PASS（限定合成隔离范围）。完整固定候选Edge/HTTPS/PG链通过；A12专用钩子确实执行：切换到A11逻辑恢复库后，原HTTPS授权Session以原请求继续读取同一Plan且字段完全一致；精确恢复本轮Credential Manager源URL、重启API回源库后，同一Session再次读取成功。API重启2次、PostgreSQL重启1次、逻辑恢复1次。
- 首次权限修复尝试使用 `REASSIGN OWNED`，PostgreSQL因管理角色拥有系统扩展所需对象而拒绝；在销毁前述隔离临时库后，将实现调整为仅向合成应用角色授予该临时恢复库 `plm` schema 的使用权及表/序列/函数权限，不转移系统对象或修改源库。最终整包复验通过。
- 单测8/8、Python语法与diff检查通过。固定候选SHA-256仍为 `3cbd68aaad08b111fdf809575915358d7d7737a266990ed6bd3df23f2326f455`；`api_restart_count=2`、`postgres_logical_restore_count=1`、`postgres_restart_count=1`；临时进程、文件、数据库/Vault目标及布局均由smoke清理，最终无临时Vault目标。
- 受范围限制：为避开A05已有合成数据中的占位Review外键，A11数据恢复仍使用 `--disable-triggers`，因此本项不证明外键一致性。A12运行复用A05先前已通过证据，因浏览器列表页就绪探针不稳定而未重复运行，不宣称本轮A05复验。候选仍 `release_eligible=false`、`legal_clearance=false`；不代表正式灾备、生产数据恢复、Pilot或Gate通过。
- 本轮未改产品代码/API/Schema/Migration/依赖，仅更新隔离smoke helper及一次性验证器；无生产凭据或客户数据参与。验证前后固定候选哈希一致。
- A12专用skip钩子接入后，Plan Edge对合成账户登录返回HTTP429，随后游览器拒绝继续。原因是被跳过的既有A05 Prototype验收原本会清理本轮临时PG里的合成 `plm.auth_login_rate_buckets`；检查发现A05只在隔离fixture库做此清理。将同样的清理仅加入A12专用skip钩子，保留既有完整限流规则与其他业务/审计数据；重跑时继续验证真实Edge登录行为。
- A12专用skip钩子接入后，Plan Edge对合成账户登录返回HTTP429，随后游览器拒绝继续。原因是被跳过的既有A05 Prototype验收原本会清理本轮临时PG里的合成 `plm.auth_login_rate_buckets`；检查发现A05只在隔离fixture库做此清理。将同样的清理仅加入A12专用skip钩子，保留既有完整限流规则与其他业务/审计数据；重跑时继续验证真实Edge登录行为。
- 随后的隔离链成功运行，但最终JSON `api_restart_count=0` 且无A12 marker，证明A12恢复库API回调未执行；不能将该轮视为A12通过。核查发现`runpy.run_path`返回的命名空间dict与其中函数的`__globals__`不是同一对象；此前仅改了返回dict，未影响实际函数全局。将通过函数自身的`__globals__`注入A12后置回调与A05跳过钩子，再做新鲜全链复验。此前该轮源Credential Manager值未被改写，A11自身逻辑恢复检查仍通过。
