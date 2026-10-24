# AUT-04-A12-P06-A04-P03：密码流程成本剖析

## 编码前检查

- Phase2 Auth 验证单一问题：固定KDF/slot等待/global锁等待与持有/UOW成本实际剖析，决定下一有证据的优化；输入CR008/0049与已同步9f38868，无生产代码更改。
- 使用项目development/testing/architecture Skill约束；当前五组20成功无SQL错但普通写P95 FAIL，不缩Scope/降算法或标准。
- 测试进程仅计时包装真实Scrypt、4-slot、UOW和既有global锁；五批顺序，实际Windows factory/PG、来源/版本/Audit/旧Session与九表不写原矩阵全保留。
- 只保留阶段名称、次数、时长分位数、活动峰值、内存聚合；不输出密码/hash/token/SQL/参数/连接串/客户资料。无API/Migration/依赖/配置/权限变更。
- 风险：计时开销、group串扰、UOW被错误重入、把分位数相加或所有UOW误当一个业务事务；记录明确统计范围，不把profile轮当正式负载或硬件最低要求。
- 验证group期间所有实际计时；线程安全样本、计数/元数据检查，原完整正确性/失败exit1保持；测试结束恢复包装。当前生产slot=4不改。
- 回滚删除test-only profiler保所有旧证据；单元/wheel本轮无生产变更不重复构建。下一按实际贡献比较，不用设计意图当PASS。

## 真实结果（仅本项测量完成，性能 FAIL）

Windows11实际Factory/PG18/固定Scrypt/4 slots/20并发，正向信任合成；每批20实际请求，所有计数assert通过，无SQL错误，20+20 first/latest3/旧Session一致，history两组九表不写。

|批次|HTTP P95 ms|slot等待P95 ms|实际KDF次数/P95 ms|global获取P95 ms|global获取后至UOW退出P95 ms|
|---|---:|---:|---|---:|---:|
|GET|111.595|无|0|无|无|
|reset fresh|1627.491|1181.524|20 hash/309.940|38.314|22.633|
|change fresh|3182.044|2446.818|20 verify/320.654 + 20 hash/313.253|33.898|24.823|
|reset history|1618.416|1145.744|20 verify/314.204|7.056|8.860|
|change history|3180.777|2423.986|40 verify/318.078|6.617|7.539|

- 全局写UOW样本20各批；不持global的UOW计数GET40/reset40/change60，含endpoint身份/响应读取，不误称一个业务事务。不同样本分位数不能直接相加；global hold度量到UOW退出，commit已先释放锁时此值为上界。
- 四写批全部20成功，slot等待成功20/无timeout，KDF计数reset20/change40与源码预期相符；测量实际global获取/持有各20。history first保持、数据库错误空。原Windows状态与publication回归通过。
- process peak working set674357248 bytes，仅此进程；不是PG/整机峰值或发行最低内存。profile包装有计时开销，本轮不是正式网络/TLS/持续负载。
- 脚本实际exit1（明确原性能FAIL，不是诊断超时/计数断言失败）；unit1419/wheel751532沿用上轮，本轮未重跑/构建，因为仅test-only新增。
- 证据支持下一优先比较KDF资源槽位，而不是放宽DB锁/去权限/增锁超时；未由单轮推定全部硬件不可能达标。生产4不改，整体Auth/cross-process资源上限还需独立验收。
- Next P03-A02：历史锁段修复后的8/16-slot test-only剖析与内存/P95/当前权及全结果比较，保留原1秒标准/固定KDF；按实际证据决定资源配置，不盲目生产20或掩盖失败。CR008/Gate3不关闭，全部业务/UI/安装/UAT继续按原计划。
