# PLG-03-A07 第二轮 Hosted 验收记录

- 日期：2026-11-07
- Change Request：CR-EXEC-054
- 结果：NOT_PASSED（验收fixture不符合Owner当前claim前置；A07 Failure Owner未调用）
- Hosted run：[42353151341](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42353151341)
- A07专项Job：[128347507564](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42353151341)

同轮父包内PG18.6启动、迁移与合成fixture建立后，OutputGenerationStartOwner以固定错误码OUTPUT_START_NOT_ELIGIBLE拒绝验收器手工构造的ClaimedJob。A07 Failure Owner没有被调用，因此本轮不是A07业务转换结论。

修复前检查已登记：对照已通过P30 Harness与Output start Owner契约，优先把fixture改为Jobs Repository实际签发的当前claim；不得修改Owner拒绝条件或合成无效lease。仅云端临时数据。
## 修复前只读定位（2026-11-07）

拒绝并非已证明的claim字段差异。Output start/failure Owner的port要求传入既有UoW后可调用的JobLeaseRepository方法；Harness传入的JobLeaseService是开UoW包装，不接受transaction参数，异常被Owner按合同归一为OUTPUT_START_NOT_ELIGIBLE。P30成功验收器直接注入SqlAlchemyJobLeaseRepository。A06已用相同手工claim通过真实lease proof，因此不据此认定claim无效。

已在CR-EXEC-054先记录精确修复：Hosted验收器分别构造JobLeaseService与SqlAlchemyJobLeaseRepository；Plugin事务Owner仍用Service，Output交易Owner改用Repository。不修改业务校验。