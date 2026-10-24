# AUT-04-A12-P06-A04-P03-A02：8/16-slot posthistory成本比较

## 编码前检查

- Phase2/Auth test-only，单一问题：已修history后的8/16并发资源上限与4基线成本/内存比较。输入f844f72成本证据/CR008/0049；已读项目Skill development/testing约束。
- 只扩现验证脚本CLI，默认4；真实Fixed Scrypt/实际Factory/PG18/5×20及old state/publication链保持。测试各自独立进程/临时库顺序执行，避免两次并发测试互相污染。
- 无生产源码/参数/权限/API/Migration/依赖/配置变化；生产slot仍4，试验最多16，即单类活跃固定KDF内存预计约2GiB，实际进程峰值需测，不宣称全Auth/cross-process已限额。
- 计时/峰值样本聚合，不打印秘密/SQL/客户正文；分位数不相加，global持有度量为上界；计时开销和单轮观测不能证明正式持续负载或最低硬件配置。
- 测试必须20全成功/无SQL错/历史九表无写/KDF及slot计数正确，最终active0/peak≤testsize/无slottimeout；失败仍exit1。记录CPU竞争使单KDF变慢或资源只换取部分延迟的结果，不降低原1秒目标或标Gate通过。
- 回滚撤CLI/跟踪扩展保旧证据，无生产升级。本轮unit/wheel无生产变更不重跑。下一按两轮实际结果选择具体可逆实现或继续独立必需工作，不无限重复同一测试。

## 8-slot 实际结果

- 独立验证进程/PG临时库，全部五组20/20成功、实际SQL错误空、20+20 first/latest3/旧Session一致、history九表无写；原Windows state/publication回归通过。
- HTTP P95 GET107.959/reset fresh1076.548/change fresh2148.421/reset history1135.454/change history2159.915ms；四密码组仍超1秒，脚本最终实际exit1 FAIL。
- slot等待P95 fresh reset632.188/change1397.862/history reset612.332/change1387.246ms；KDF P95 hash fresh reset364.773/change395.036、verify fresh change388.977/history reset386.549/history change374.453ms。等待减少，但每KDF比4-slot约310～321ms更慢，不能直接相加不同分位数。
- global获取P95 reset fresh154.080/change82.481/history8.832/14.031ms；持有至UOW退出35.438/33.009/9.939/10.408ms。原锁序与权限没变，不把变慢取锁隐藏。
- reset/change实际活动peak8/end0/timeout0，计数reset20/change40 KDF及20slot/global全assert通过；process peak working set1210707968 bytes，仅本进程。
- 只读当前机器观测：24 cores/32 logical processors，Windows报告最大clock2200MHz（不是实际Turbo频率）；可见内存33163780KiB，空闲采样17681400KiB，电源方案名称Turbo。未修改系统电源/硬件，不推定正式容量或全负载可用资源。
- 16-slot 另一个独立进程顺序执行，已实际终止exit1；未与8-slot并发。生产4不变。

## 16-slot 实际结果

- 五组全部20成功、fresh/history SQL错误空、20+20 first/current3/旧Session一致、history九表不写；原Windows state/publication回归通过，计数全部assert正确。
- HTTP P95 GET110.106/reset fresh975.244/change fresh1618.757/reset history859.607/change history1616.897ms；本轮reset两组达原1秒标准，但change两组仍FAIL，不能用局部PASS关闭CR/Gate，最终实际exit1。
- slot等待P95 fresh reset370.986/change839.765/history reset325.469/change819.393ms。KDF P95 hash fresh reset487.289/change490.155、verify fresh change480.826/history reset492.796/history change475.870ms；较8单KDF更慢，资源竞争有实测证据。
- global获取P95 reset fresh322.144/change211.190/history40.222/67.958ms；获取后至UOW退出40.664/43.660/14.372/16.995ms，global排队随更集中完成增大但无超时。
- actual peak16/end0/slot等待timeout0；process peak working set2285113344 bytes，仅本进程，非整机/PG最低配置。默认生产4未修改。

## 比较与下一选择

|test slots|reset fresh P95 ms|change fresh P95 ms|reset history P95 ms|change history P95 ms|进程peak bytes|
|---|---:|---:|---:|---:|---:|
|4（P03上一轮）|1627.491|3182.044|1618.416|3180.777|674357248|
|8（本轮）|1076.548|2148.421|1135.454|2159.915|1210707968|
|16（本轮）|975.244|1618.757|859.607|1616.897|2285113344|

- Changed/Files：仅cost profiler CLI与slot跟踪、本记录及DEC333/CR008/STATUS/CHANGELOG；Migration/API/依赖/生产升级：无。Unit1419/wheel751532沿用上一生产轮，本轮未重跑/构建。
- Result：比较完成，所有功能与计数PASS，整体性能FAIL；不能由一次reset达标推定各环境/持续负载或对全部Auth资源限额。
- 选择：下一P03-A03记录并设计显式、可恢复的非敏感容量配置与reset/change共同进程预算，保安全默认和当前数据；不能直接把两个独立16 gates作为生产总内存限制（混合负载最多32活跃，未验）。再独立实施/混合实际验收，提供高资源部署可选而不擅改所有目标默认。
- 不再盲目重复8/16未变测试或提高锁超时/降低密码强度；固定KDF/原1秒目标、同步API/完整Scope保留，change不足继续性能任务与独立必需工作，不伪造PASS。
- Known：覆盖率、跨进程/整个Auth资源控制、正式信任、浏览器/TLS/持续负载/三平台、业务/UI/安装/UAT仍待；CR008/Gate3开放，最终交付目标不缩减。
