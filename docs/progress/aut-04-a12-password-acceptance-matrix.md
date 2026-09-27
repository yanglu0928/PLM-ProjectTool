# AUT-04-A12 密码流程验收矩阵（2026-09-27）

最新P06A04P02A03：reset历史KDF已事务外/4 slots、写事务新权/fullfirst-source末核、miss中途真实提交有界回退已验；1414 unit/实际PG竞争/Windows reset完整链通过。20历史reset20成功1634.794ms（原6014.758）；fresh reset1598.708ms、fresh change3195.512ms；未改change历史14成功6actual55P03/8114.279ms，两历史九表无写。完整性能仍FAIL，不能关闭本矩阵/CR008/Gate；下一change历史，不调整原1秒标准。

输入CR-AUT007/008、冻结API02/64cdf09、Schema0049、实际进度及当前源码。内部验收不等于正式生产/完整Auth或Gate3完成。

|要求|当前证据|结论/剩余|
|---|---|---|
|当前强制改密事实与五业务proof零授权|P01实际PG/Scrypt五proof拒绝/七表不写、正常新Credential恢复|内部通过；未来业务入口仍需统一源回归|
|受限login/GET/renew/logout最小身份|P02实际Windows required=true/NONE/空项目、项目reader不调用/退出清Cookie|内部通过；初始来源TEST_ONLY，实际reset链P05A07补证|
|真实本人change/历史双密码来源/当前有效身份恢复|P03/P04真实PG/Scrypt及Windows登录链|内部通过；License无门槛保持冻结|
|reset正常/disabled/self/唯一Admin可达性|P05A05/A06/A07实际Service与HTTP|内部通过；角色来源明确TEST_ONLY，不是正式账户证明|
|强If-Match/Key/CSRF/来源/write-only/Cookie|P04A03及P05A06完整真实矩阵，A07实际Factory|内部通过；实际浏览器/TLS未验|
|不可变first/幂等同不同Key及后来凭据改变|0048/0049真实Schema、source及原子Service实际竞争/历史重放|内部通过；未执行生产迁移|
|全Session含expired撤销/写后与precommit回滚/丢确认恢复|P04A02/P05A05真实Port/SQL/commit故障，A06末读503|内部通过；正式生产灾备未验|
|20并发GET/普通写正确性与P95|P06A01真实20客户端Factory/PG/Scrypt：GET达标、reset超标、change六55P03/503，失败无半写|FAIL；CR-AUT008设计后修复，不能关闭完整CR|
|权限安全覆盖率>=90%、全部异常和真实服务/TLS持续负载|当前1388测试数不能证明覆盖率；本轮只ASGI20 burst|未完成，需实际覆盖率/服务压测|
|正式信任/目标账户/Server2025/Debian/UI/安装升级/UAT|根STATUS客观缺项仍在|未完成；Debian验证按用户延期但目标保留|

本轮只验证/文档，无新生产代码/Migration/依赖/API规则变更；原冻结及历史保留。下一CR-AUT008预计算proof设计与有界资源/生命周期验证，不降低密码强度或删scope。完整项目交付继续推进，不以该矩阵代替程序包。

P06A02增量：reset预认证结束后4-slot固定KDF/原写事务重新授权已实施，实际PG独立锁可用及撤权/logout/renew/目标版本/License拒绝九表无额外写，原原子/Windows/发布通过。最新20并发GET106.973ms、reset1634.810ms（20成功）、change7559.374ms（14成功/6个55P03），性能行仍FAIL，下一change及history；正式trust/覆盖率/浏览器/服务/三平台/包缺项不变。

P06A03增量：本人change current source精确快照、verify/new hash事务外、写UOW当前身份+相同Credential ID/version/flag再核已验；真实锁释放/logout/renew/disable/reset竞争及原原子/Windows两链通过。20并发三组均20成功、无SQL错误、20/20first、新凭据3和旧Session失效一致；GET111.960ms/reset1631.262ms/change3178.707ms，功能恢复但普通写仍超1秒，性能行仍FAIL/CR OPEN；下一资源校准/history锁段，不改正式缺项。

P06A04P01增量：8/16/20-slot仅验证进程实验，新写全部20成功/无SQL错误但change仍2142/1675/1447ms；20-slot reset单轮957ms需更多证据且峰值工作集约2.63GiB，生产4不改。原4-slot历史reset20成功6015ms、change14成功6个实际global55P03/7908ms，两组九表不写/first保持；历史并发功能与性能新增FAIL证据，下一源/KDF事务外与当前权最终核验，原Scope/标准不缩减。
