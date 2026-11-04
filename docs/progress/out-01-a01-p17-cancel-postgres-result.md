# OUT-01-A01-P17：OutputRequest Cancel Owner PostgreSQL 18验收结果

- 日期：2026-11-04
- 状态：PASS_SCOPE_LIMITED
- 变更：CR-OUT-013（承接CR-OUT-012）
- 验收：GitHub hosted run [41799812913](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41799812913)，13/13 jobs成功
- 最终验收HEAD：e0cf6ddf08d2c6e12e01522d1ae92375576c8bf1
- 执行环境：GitHub hosted Windows Server 2025，runner临时目录位于D盘；临时PostgreSQL 18.6/pgvector，未在用户本机运行项目代码或测试

## 验收结果

完整Hosted运行完成backend 4,006 tests及wheel、前端测试/typecheck/build、PG18/pgvector重建、同run非发行父包组装、清洁解包临时数据库生命周期、A17/A34/A35/A50，13/13成功。父包含20,197项，候选SHA-256为1377ca1ab3b6404fbc7d53447ea906d7440cd3c6ad33e475ce33165d4a00f9b5，非发行产物。

新增验证器经PG18.6真实Service/Repository及隔离synthetic rows执行，摘要均通过：

- PENDING OutputRequest和OUTPUT_GENERATE Job在同一UOW原子变为CANCELLED。
- RUNNING Job/Lease写入CANCEL_REQUESTED，仅代表请求登记，不表示Worker确认。
- 陈旧If-Match、跨Project、错误Job绑定、无权角色均不产生持久行、Audit或幂等receipt变更。
- 相同幂等键并发调用收敛，只有一份Audit和receipt。
- 注入Audit失败后Output/Job/Audit/receipt全回滚。
- CANCELLED完成时间来自PostgreSQL clock_timestamp()，持久值不晚于数据库采样。

## 托管验证器偏差与处置

run 41796636992及41798124112的负向断言误把clock_timestamp()动态读数包括在快照整体比较中，产生假失败。两次均在修复前分别登记于CR-OUT-013；修复仅把无写入断言限定到Output/Job持久字段和Audit/receipt计数，时间边界仍独立断言，未删减任何业务拒绝或回滚用例。最终run 41799812913通过。

## 限制与后续

此PASS仅针对取消Owner的合成PG18事务边界。API router仍未装入Windows显式write composition，默认模式不挂载；Output成功/失败Worker不存在，无法证明真实进程停止；没有Windows 11实机、正式License信任、服务ACL/TLS、Gate 3、Pilot或Release结论。下一项P18按CR-OUT-014接入显式Windows write composition并做HTTP/Session/Project权限组合验证。
