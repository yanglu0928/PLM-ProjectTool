# P07-A20-P01 用户名称Repo前SQL拒绝

2026-09-27编码前检查：Phase2/WBS AUT-04-A12-P07-A20-P01；输入冻结64cdf09/0049/A19与现有名称修改Service/Repo；Auth User/CanonicalUsername/版本输入，仅前SQL合同，不修改生产/API/权限/Schema/算法/依赖。

验收：user/actor ID与版本非法、名称对象类型错误或与规范化来源不一致在_session前VALIDATION_FAILED；非法display沿Domain UsernameValidationError拒绝（不声称Repo自行固定码）；真实inactive Session/错误Session拒绝且不启动事务；_session底层异常原样传播，Service层已有固定码合同不更改。禁止mock成功SQL。

风险/回滚：只新增unit可撤，无升级。完整测试实跑；真实缺User/原normalized错配/最大版本/唯一约束与其他IntegrityError留P02，不关闭当前来源验收。coverage/14PG/wheel/性能不重跑，旧84.717%/raw/Hash/90%保持；正式trust/CR008 FAIL/Gate/可用包待。

执行结果：新增4项参数化测试，完整1524项unit/contract于2026-09-27运行21.643秒，失败0、错误0、既有跳过2，exit0。非法ID/版本/名称来源在SQL前拒绝；真实未激活Session不启动事务；底层异常原样传播。不模拟成功SQL，不把本轮结果计为实际数据库或完整覆盖率通过。下一项A20-P02实际数据库来源验证。
