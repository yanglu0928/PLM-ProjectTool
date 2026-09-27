# AUT-04-A12 密码流程验收矩阵（2026-09-27）

最新P07A16：1501unit无失败/2既有跳过与14实际链全通过；完整Auth3200/3364行95.125%、837/988分支84.717%，综合92.762%不替代分支、false/exit1。密码91.146%保持、工厂362/369行8/10分支另列；完整范围/分母/90%不变，旧raw保留、新Hash7d6fbfc0…。下一仅SessionHTTP拒绝/安全错误响应；性能/wheel未跑，正式trust/CR008/Gate/可用包待。

最新P07A11：1480unit无失败/2既有跳过与12实际链全通过；完整Auth3190/3364行94.828%、812/988分支82.186%，综合91.958%不替代分支，ALL_AUTH false/exit1。原密码98.472%/91.146%与工厂362/369、8/10保持。生产/完整范围/分母/90%不变，旧Hash保留，新a2fb0a38…。下一仅User创建Service防御，实际Repo另项；性能/wheel未跑，正式trust/性能CR008/Gate/可用包待。

最新P07A08：1470unit无失败/2跳过，原五密码链+六非密码Windows/Vault链共11同轮通过；完整Auth3168/3364行94.174%、792/988分支80.162%，原21密码98.472%/91.146%保持，工厂362/369行8/10分支单列。新增完整Auth独立90%退出控制false/exit1，不以综合90.993%关闭安全；范围/分母不改，旧raw保留、新Hashf6a57106…。下一Session时间/结果/异常与无commit边界；无生产变更，性能CR008/正式trust/Gate/包待。

最新P07A07P02：局部with单行guard复现后仅两Service分行，对c004980 AST完全相等；完整1470unit无失败/2跳过与五实际链全通过。原21密码1031/1047行98.472%、350/384分支91.146%达到本范围90%/exit0，行分母+30/分支+14、未删范围或排除；统计变化包含排版对应改善，不是新增用例提升。全Auth92.717%/78.239%与工厂362/369行8/10分支仍未完整达标，完整安全行不关闭；新Hash57390683…与全部旧raw保留。下一完整Auth非密码实际链纳入/真实缺口补测，性能CR008/正式trust/Gate/包待。

最新P07A06P03：Result输入/事务异常与两实际Service八final故障九表回滚、两正常提交控制后，同轮1470unit无失败/2跳过、五实际PG/Windows链全通过；密码1007/1017行99.017%、321/370分支86.757%，全Auth92.831%/76.386%，工厂362/369行8/10分支单列。exit1保90%分支缺口，综合95.746%不替代，原范围/JSONHash不覆，新Hashd45e9dd3…；下一逐边核对报告/已有拒绝用例与真实缺口，不无证认定不可达或测量误差。无生产变更，性能CR008/正式trust/Gate/包待。

最新P07A05P03：Repo/Access非法输入与事务异常专测后，1467unit无失败/2既有跳过及同轮四实际PG/Windows全通过；密码完整21文件1003/1017行98.623%、317/370分支85.676%，全Auth92.711%/75.975%，工厂362/369行8/10分支单列。exit1为90%分支仍未达，不是功能测试失败；新独立JSON/Hash45c4d14a…与旧历史保留，无生产变更。下一A06结果来源/真实current-final故障，不把95.169%综合数替代安全门槛；性能CR008/正式trust/Gate/包仍待。

最新P07A04P02：新增5新写Service Port防御参数化方法/正向唯一commit Spy通过，1452unit无失败/2跳过与四实际PG/Windows全通过。密码同21文件97.443%行/82.432%分支（991/1017、305/370），全Auth92.352%/74.743%，工厂单列，exit1未达90；不将综合93.439%或Mockcommit作为真实SQL/全安全证明。A04历史写hint-first遗留下一P03，原Hash与性能CR008/正式trust/Gate/包缺项保留。

最新P07A03：新增8个HTTP防御参数化方法专测通过，完整1441unit无失败/2跳过与四实际PG/Windows入口全通过，两个密码API行/分支100%。同一密码21文件行96.559%/分支79.189%（982/1017、293/370），全Auth92.082%/73.511%，工厂单列；整体分支未达90/exit1，不能用综合91.925%关闭安全行。下一Service Port违约/时间/依赖与擦除，无生产变化；性能CR008/正式trust/Gate/可用包待。

最新P07A02：同一coverage实际1433unit无失败/2跳过+四组PG reset/change history-atomic及Windows HTTP全部通过，密码行95.182%/分支76.216%（968/1017、282/370），全Auth91.662%/72.382%，工厂另362/369行8/10分支；综合90.123%不抵消分支未达，exit1安全未关闭。A01原Hash保留，21全文件分母/test-report与下一HTTP防御缺口可追溯；性能CR008/Gate3/正式trust/包待，不把真实集成PASS替代安全完整验收。

最新P07A01真实coverage：1433 unit/contract无失败/2既有跳过，新增scrypt边界异常后49/49行12/12分支；密码21文件791/1017行77.778%、204/370分支55.135%，全Auth82.124%/59.138%，Windows工厂另355/369行7/10分支。覆盖率行仍未达90/exit1，不把测试数或单文件100%作为所有Auth安全PASS；下一真实PG与Windows场景coverage补证。完整报告含范围/分母/原JSONHash/首次错误修正，可追溯；性能FAIL/Gate未关闭。

最新A04/A05：Windows非敏感配置默认4/严格1..16、进程唯一reset-change容量装配及不同配置dispose/九表不变已验；1430 unit为A04结果。A05真实Windows10+10混合fresh/history，4/16独立配置各20成功/30真KDF/peak4或16/end0/SQL0、原结果/历史九表无写/旧Session失效/原回归通过。4 P952199.128/2507.062ms；16 1218.475/999.713ms，history16单轮临界PASS但整体FAIL/exit1。默认4不改，原1秒标准/固定KDF/Gate缺项保持；下一旧cost profiler迁移真实配置/共享预算。当前功能通过不替代全部性能与正式服务持续负载。

最新P06A04P02A04：change历史双KDF事务外及fullfirst双来源/当前身份末核已验，1419 unit/实际PG竞争/peer提交撤旧Session-新login恢复通过。20五组全20成功，actual SQL错误为空，原六history global55P03消除；history change P95 3220.477ms/reset1650.695ms、fresh change3157.216/reset1642.030ms仍超1秒。两history九表不写，功能恢复不抵消性能FAIL；CR008/Gate开放，下一固定KDF成本与资源调度剖析，不降标准/强度。

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
