# AUT-04-A12-P06-A04-P01 KDF资源校准与历史重放测量

编码前检查：Phase2/Gate3未通过；输入64cdf09/API02/CR-AUT007/008/0049，前置abd3d98实际事务外KDF与20成功但普通写超标。仅验证脚本，不改生产slots4/算法/权限/API/依赖/Schema。新隔离进程中分别替换测试专属8/16/20-slot信号量，运行原实际Windows Factory/PG/Scrypt20请求及完整来源核对；组间不同时运行，不冒充正式配置。

DEC-20260927-327：比较4-slot原基线与8/16/20实验，记录真实活动峰值/5秒等待失败和本进程peak working set（非主机或PG内存）。现有本机约32GiB允许最大20个固定128MiB KDF实验，OpenSSL单次上界256MiB不变；不访问客户数据/生产DB或外发。P95仍nearest-rank/GET500ms/write1000ms，全部结果保留，未达即FAIL，不随手加production slots。

另测原4-slot历史reset/change20独立历史请求，在实际后来正常Credential3/有效新Session下原Key+原password重放，安全200与固定503分别记，九表快照无写，首结果/ETag不变；禁止用旧Session绕过认证。故障不省略回归，最后非零明确性能FAIL。校准需当前单进程ASGI实测，不代表持续负载/TLS/三平台/正式trust/安装包；回滚仅撤实验工具，生产行为不变。

## 真实实验结果（2026-09-27）

各实验独立fixture/进程，顺序运行，无其它本轮压测并行。生产源码仍abd3d98/4 slots；固定Scrypt不变，实际Windows write Factory、PG18、完整ASGI HTTP、Session/CSRF/first/Audit均原链，正向trust合成。所有新写组20/20成功、SQL错误空、20reset first/20change first及正常凭据3/旧Session失效均实际核对。

|实验上限|GET P95 ms|reset fresh P95 ms|change fresh P95 ms|实测reset/change活动峰值|进程peak working set bytes|
|---|---:|---:|---:|---|---:|
|8|113.325|1110.913|2142.248|8/8|1208188928|
|16|113.571|1064.465|1674.781|16/16|2281807872|
|20|105.435|957.033|1446.926|20/20|2818846720|
|4（含历史组）|109.969|1604.189|3181.737|4/4|807968768|

所有slot等待失败计数0、结束active0。20-slot仅reset单轮达到1000ms（max966.181ms），change仍未达且内存显著增大；不据此直接改变生产上限或声称跨平台/持续负载达标。4-slot原新写功能已经修复，资源上限影响延迟，但“简单增大slots能完成全部验收”被实际证据否定。每个实验最后实际exit1明确FAIL，非进程观察超时。

原4-slot历史组：实际later Credential3下原Key/原临时密码reset重放20/20成功、P95 6014.758ms；change以当前正常新Session和原两密码重放14成功/6个503、P95 7908.389ms。六实际SQL错误全55P03/deployment advisory lock；两组前后九表完整快照不变，所有200正文与首结果一致，reset ETag仍原v2，没有覆盖/复活/新Credential或收据。旧Windows状态和原双Scope发布回归运行通过后才报告性能FAIL。

本轮只新增/扩展验证及文档，没有新生产源码/Migration/API/依赖/配置/升级。1400 unit/wheel749932为上一轮证据，本轮未重跑/重建；未将实验信号量写到正式代码。本进程peak working set不是整个主机/PG/跨进程KDF总额或资源最小要求，现场内存观测可供下一有界调度设计，不能替代正式安装硬件验收。

下一P06A04P02：先新增caller-UOW只读已完成幂等收据hint及实际first/immutable credential detached source设计/验证，再在无DB锁阶段执行历史KDF、最后原global事务当前权/同scope/fingerprint/first/source完整重验；hint和密码匹配都不是当前权限，不跳过License/CSRF/目标绑定/历史拒绝。源缺失/并发出现first/提交未知的有界回退须单独实测，避免盲retry新写。资源校准记录保留，普通写原1秒目标及整个CR/Gate/完整包仍未通过。
