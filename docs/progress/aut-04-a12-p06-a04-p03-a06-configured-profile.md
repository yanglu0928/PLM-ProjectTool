# AUT-04-A12-P06-A04-P03-A06：真实配置成本剖析

2026-09-27；0.1.0.dev0；状态INSTRUMENTATION_FUNCTIONAL_PASS / PERFORMANCE_FAIL。Phase2；前置A04/A05实际装配/混合正确性已验，性能FAIL；输入CR-AUT008/固定KDF/0049/冻结64cdf09。仅验证脚本/证据，无生产实现、Schema、API、权限、算法或依赖变化。

方案：旧cost profiler停止替换legacy模块gate；从首个工厂起通过真实PLM_PASSWORD_KDF_SLOTS配置共享预算。计时代理仅委托实际PasswordKdfCapacity acquire/release/snapshot，不再创建另一个Semaphore；两个Service返回同一代理及底层预算。保留五组20完整请求、KDF/slot/当前身份/global获取与持有计数和九表history不写检查。使用16独立进程一次实际剖析，报告内存与原1秒标准，不对旧测试报告追写。

风险/回滚：计时有开销，UOW包含多处身份与响应读取，分位数不可相加；ASGI/synthetic trust不是网络或生产负载。删除计时代理即回滚测试，不改生产默认4、不删历史，不放宽算法/指标；失败保留exit1。后续基于证据转向独立安全覆盖率与待实现Platform任务，不无限slots调参。完整包/Gate未完成。

实际16独立进程：五组各20成功，SQL错误为空、历史九表全量不变、first/reset ETag/新Credential/旧Session完整性通过；固定计数、共享budget peak16/end0/timeouts0、旧Windows状态及双Scope发布回归全部通过。HTTP P95 GET119.308ms/reset fresh1006.003/change fresh1604.868/reset history842.946/change history1627.173ms；整体exit1性能FAIL，GET及reset history单轮通过，不等于整体通过。

成本P95：reset fresh hash475.088/slot wait364.597/global获取359.509/持有至UOW退出54.021ms；change fresh hash475.494+verify494.884（不能将分位数相加推导总耗时）/slot833.308/global获取262.012/持有52.146ms。reset history verify472.340/slot299.709/global获取32.620/持有14.502ms；change history双verify每次492.401/slot838.009/global获取50.009/持有16.307ms。各组20slot+global，KDF reset20/change40；总体进程peak2285068288 bytes（约2.13GiB）。不输出secret、SQL正文/参数或连接字符串。

结论：功能性并发锁错误已消除，真实共享预算有效；16下双KDF和排队仍限制change，fresh短写global排队仍有数百ms。进一步单纯扩容量风险高且缺乏整体达标证据，默认4保留。CR-AUT008继续OPEN/FAIL，后续若调整接口/安全机制必须独立CR与兼容/迁移分析，不能默改标准或安全强度。下一AUT-04-A12-P07-A01实际分支/行安全覆盖率基线，处理独立验收缺项；不冒充性能已解决。本轮unit/wheel未重跑，无生产升级。
