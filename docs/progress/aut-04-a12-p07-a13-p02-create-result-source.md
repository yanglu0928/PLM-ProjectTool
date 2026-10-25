# P07-A13-P02 用户创建结果真实来源

2026-09-27编码前检查：Phase2/WBS AUT-04-A12-P07-A13-P02；输入冻结64cdf09/0049/P01与既有真实创建链；前置owned publication PG/Vault fixture。Auth User/Credential1/first/Audit/收据来源验证，无生产/API/权限/Schema/算法/依赖变更。

验收：真实get未知返回None，record缺User或缺Credential拒绝；真实first与错配DTO拒绝不调用verifier；实际原Credential验证真/假，明确注入验密非bool/异常拒绝；实际SELECT1/0中止事务后三方法固定拒绝；实际record INSERT及get成功后显式故障返回None，创建Service九表全行回滚且密码清零，之后同名称正常创建成功。

边界：DTO/verifier/adapter返回故障显式注入，但SQL读取/插入/触发器原样执行，不mock成功SQL或禁触发器。合成License/TEST_ONLY fixture账户仅隔离验证；临时资源由fixture限定所有权清理，生产/客户数据不动。

风险/回滚：仅新增验证入口，无升级；原publication同轮回归；unit最近1491本批不重跑，coverage/性能/wheel未跑。旧82.186%/raw/Hash/90%保持，正式trust/CR008性能FAIL/Gate/可用包待。

首次执行exit1：实际Service按预期抛AUTH_CREATE_UNAVAILABLE，但验证脚本误从fixture模块获取未导出的异常类，捕获时AttributeError；原fixture清理。修正为正式模块直接导入异常类，生产不改，全部断言重新实际跑。

重跑结果exit0：真实get缺first返回None、record缺User/原Credential拒绝、原密码真实True/False；两个错配DTO在原源比对拒绝；四verifier非bool/异常在真实SQL后固定拒绝；三独立UOW实际SQL22012中止后get/record/verify固定拒绝。实际创建INSERT/get成功后显式None故障，Service固定拒绝、九表全行精确回滚/密码清零，随后同名称真正创建与first读回成功。原dualScope空/260publication回归同轮通过。仅已列行为PASS，unit1491/coverage/性能/wheel本批未跑；下一P07-A14独立User状态Service拒绝与无commit，后统一13链覆盖，不推算新比例/关闭Gate。
