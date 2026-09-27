# P07-A15-P01 状态适配层入口拒绝

2026-09-27编码前检查：Phase2/WBS AUT-04-A12-P07-A15-P01；输入冻结64cdf09/0049/A14；前置状态Service/Access/Repo已实现。仅Auth UserState Repo非法ID与Access自停用错来源前SQL/未开启事务拒绝；实体User/Session/Proof/Result；无生产/API/权限/Schema/算法/依赖变。

验收：Repo两ID非法提前VALIDATION_FAILED；Access八自停用错来源返回False且不_session；篡改proof/result在SQL前拒绝；真正未启动SQLAlchemy Session在lock/Repo/self-final抛AuthTransactionError而不启动事务。Adapter原异常交给Service固定错误的合同保持，不虚报adapter自身已转换固定码。

风险/回滚：新增unit可撤，无升级，不mock成功SQL。完整unit本批实际跑；真实PG末核/缺行留P02。coverage/13PG/wheel/性能未跑，旧82.186%/raw/Hash/90%保持，正式trust/CR008性能FAIL/Gate/可用包待。

结果：4新增参数化方法，Repo八非法ID、Access八自停用来源错配、两个篡改DTO、真实inactive Session三个方法拒绝；前SQL路径_session未调用，真实Session拒绝后仍无事务，Adapter原异常传播符合现有合同。完整1501unit failures0/errors0/skipped2，exit0。仅P01 PASS，不冒充SQL当前行/回滚。下一P02真实自停用final正常→Session/时间/User/活Session/其他Admin变化拒绝及九表回滚、实际缺行/SQL异常，保原触发器/Scope/90%；本批未跑coverage/PG/wheel/性能，Gate/包未完成。
