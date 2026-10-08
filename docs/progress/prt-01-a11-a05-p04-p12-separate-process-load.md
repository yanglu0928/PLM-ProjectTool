# PRT-01-A11-A05-P04-P12：独立客户端进程20并发校准

2026-10-08 / 状态：`DIAGNOSTIC_COMPLETE_PERFORMANCE_FAIL`。

编码前检查：Phase2；以CR-PRT-005、P11同进程时间线和Windows11隔离PostgreSQL18.6/pgvector合成Approved Prototype/Review/Trace/文件链为输入。只新增隔离httpx客户端子进程和工具入口；合成Cookie仅经标准输入传递，不进入命令行、日志、Git或外部网络。20并发、每项预热/三轮、HTTP200/强ETag/PROTOTYPE断言不变；最外层ASGI以无敏感值的探针ID计时。无生产程序、API、Schema、权限或连接池更改。进程时钟在父进程启动/结束区间校准，若不一致应失败而非强算跨进程阶段。风险是仍为Windows11 loopback/合成数据，非发行环境SLA。

两次真实Uvicorn loopback20并发独立客户端，业务P95中位约651/655及652/644ms，`/health/live`约68及64ms；均高于500ms。第一轮业务ASGI前P95约90–122ms、ASGI内约561–587ms、响应后约6–7ms；第二轮`PROTOTYPE_SCOPE_DECISIONS`约84/579/4ms。与P11同进程测试的“ASGI前约500ms、ASGI内约90ms”明显不同，因此同进程客户端/服务端竞争确实扭曲了定位，不能据P11把生产瓶颈归在接入前。独立负载下预览服务P50/P95约466/519ms、峰值并行20；Prototype Owner约368/423ms、Requirement Owner约165/205ms、Prototype制品/Review约110/144ms；Session validate约39/64ms。嵌套区间及各分布P95不可相加，现有证据指向服务端20并发下数据库/线程/CPU争用的组合，不足以唯一归因。两次脚本均退出0，临时实例/目录由既有验证流程清理。

结论：真实性能目标仍FAIL，不能开放Prototype正常生产入口或关闭Gate3。下一项在独立客户端负载下比较默认与临时20连接池，并测连接等待与非SQL成本；只有目标、权限/撤权和文件/Review证明同时通过才可变更生产配置。无需Schema/数据迁移；撤独立客户端工具可回滚，原业务历史不变。本项未重跑后端全量，沿用P09的3253通过/3跳过/4795子测试，不将其记为本项测试。
