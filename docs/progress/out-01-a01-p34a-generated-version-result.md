# OUT-01-A01-P34A 生成版本 Owner 验收结果

- 日期：2026-11-05
- 结论：PASS_SCOPE_LIMITED
- Change Request：CR-OUT-031；承接CR-OUT-030
- Hosted run：[42033255833](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42033255833)
- 代码提交：Owner/Repository f703c593；定向单测及后续修订见当前PR #61 head
- 执行环境：GitHub hosted Windows Server 2025 D盘临时目录、隔离PostgreSQL 18；未在用户本机/C盘运行

## 验收

父包PG18 smoke将P33旧夹具调整为无DocumentVersion初态。它先调用P34A Owner创建AVAILABLE DocumentVersion、OUTPUT_GENERATION来源引用、Document.latest_version_ref和SYSTEM Audit，然后以同一Claim精确重放并核对没有重复版本/Audit，最后继续运行P33完成Owner，验证OutputArtifact、OutputRequest、Job与Audit既有成功收敛仍通过。该PG smoke job成功，因此该顺序中的断言均通过。

同run后端全量测试/wheel、前端/build、PG18/pgvector sidecar、父包组装、A17/A34/A35/P24/A50均成功。定向单元测试还覆盖请求锁先于Job fence、错误Execution身份拒绝和Audit失败时不提交。

## 范围与剩余风险

Owner仅创建数据库版本事实；不提升文件、不创建Document/FileObject、不插OutputArtifact、不结束Job、不挂API/Worker/default composition。P34A是Output链局部PASS_SCOPE_LIMITED，不表示P34全项、Pilot、Gate或Release通过。

同run P25独立失败：initdb.exe以3221225781/0xC0000135退出且数据目录未创建，真实Output HTTP/Edge没有执行。该诊断阻塞不影响本次隔离PG18 P34A断言，仍由CR-OUT-021跟踪。

## 下一项

OUT-01-A01-P34B按CR-OUT-030/031实现staged→final同卷无覆盖提升协调、提交前后hash校验、fencing复核、final-only/linked-pair/unsafe恢复分类与故障后保留策略。不得盲删文件，不接生产组合/Worker/API。