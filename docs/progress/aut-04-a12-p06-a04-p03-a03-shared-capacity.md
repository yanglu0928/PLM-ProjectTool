# AUT-04-A12-P06-A04-P03-A03 reset/change共享容量核心

## 编码前检查与设计

- Phase2 Auth；单一问题：可信装配可注入同一有界capacity，reset/change fresh/history合计受限。输入CR008/0049/4ada5c3，按Skill development/testing/architecture约束，原锁段与两个历史接口已验。
- 新内部PasswordKdfCapacity slots严格int1..16、默认4，固定5秒等待；仅资源调度，不授权/缓存密码/降低算法。现有Service构造增加可选capacity可信Port，无HTTP/Schema/依赖变更。
- 未注入保原模块4-slot（兼容旧装配/验证），显式注入用同一capacity；不能本项就声称当前Windows工厂/登录/创建/全部Auth或多进程已统一限额。Windows配置/进程唯一预算与装配下一个独立任务。
- 成功acquire严格True、失败无release；每线程持有计数避免未持有线程释放他人预算，BoundedSemaphore与计数锁保护；多个可信Service共享，同线程可信嵌套计数可配对，不把内部test interleaving误作真实请求。
- 风险：混合负载内存翻倍、释放泄漏/异常、capacity错配置/多工厂不同预算；slots/活动/峰值只非敏感运维快照，不能推定整个Auth跨进程预算。
- 验证：严格配置/非法等待/未拥有释放/5秒timeout/真实线程争用；新旧unit与真实PG10reset+10change同步fresh和history合计界、原first/旧Session/九表无写/故障回归，wheel。
- 实施后再设计持久非敏感配置+唯一进程装配，先不改Bootstrap。回滚撤可选注入保0049/全部历史，原默认行为恢复。原1秒标准/性能FAIL保留，无生产升级/包/Gate完成。

## 执行结果

- PASS，仅内部共享容量核心：1426 tests无失败（2既有跳过）；容量5 unit含严格1..16/非法等待/未持有及他线程不得释放/实际5秒超时无泄漏/3线程总界2与工作异常恢复；两个Service新增strict acquire True/timeout无release/KDF异常只释放自己且擦除。1424后补这两个测试再全量通过。
- 实际PG同时10reset+10change，可信装配明确共享一个4-slot对象；fresh30真实KDF调用、history30真实KDF调用，合计活动KDF/预算峰值都4、结束0，40命令全部成功并擦除秘密。
- fresh各20结果为Credential/User版本2、旧Session全部实际失效；历史20结果严格等于各自first，九表完整快照不写。原reset atomic链含真实change/self/disabled/故障回滚/丢确认及dualScope publication回归通过。
- 新源码默认未注入仍用既有两个4 gates；生产Windows配置/工厂尚未改，本项不宣称现有工厂已共享、全部Auth/多进程/HTTP性能通过。本轮不重复未改默认20性能；上轮P95不足保持FAIL。
- wheel构建752486 bytes，SHA256 `1dba15b025e9d5599c1fbdfbffefdefebb3b7e8da96ed59bb05aabf34048da10`，仅内部开发构建，不上传、不当安装包。无Migration/API/依赖/生产升级，0049兼容。
- Files：auth application capacity/两个Service、capacity/两个Service unit、actual验证、本记录及DEC334/CR008/STATUS/CHANGELOG。
- Next P03-A04：Bootstrap非敏感显式slots严格allowlist、默认4、1..16；Windows write factory取同一进程预算并注入两Service，多个工厂不能悄悄新增总预算，不同容量须明确重启且安全拒绝动态不一致。独立证明无环境/JSON秘密新增、错误配置不半启动、真实Factory混合fresh/history总界；保其他模式入口，正式信任与性能/Gate继续验。
