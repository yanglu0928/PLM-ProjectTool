# AI-04-A06-P02：Execution Grant 与载荷计划证明合同

- 日期：2026-10-03
- 结果：`INTERNAL_CONTRACT_PASS / NO_EXTERNAL_CALLS`
- 依据：CR-AI-015、DEC-721、冻结DM-04/API-03/Schema0064

新增纯内部、无正文 `AITaskExecutionGrant`，固定Task/Project/Job/原请求人/Trace/Attempt/Fencing、顺序InputRef与来源摘要、Prompt Policy/版本/模板哈希、Provider Policy、Output Schema版本、Context Policy、Task参数摘要、逐次授权快照身份、Provider/Config/Model/revision/region、数据类别、批准payload摘要及记录/字节/Token/重试/时限上限。字段构造即严格校验，指纹与授权摘要不出现在对象 `repr`。

新增 `AITaskPayloadPlanProof` 和准入函数。未来服务端构建器只能提交无正文证明；Task/Job/Attempt、Grant摘要、来源摘要和批准payload摘要必须精确一致，record/bytes/tokens不得越界，授权到期立即拒绝。Grant摘要采用平台现有规范化JSON SHA-256，覆盖所有上述元数据和InputRef顺序；正文、Prompt、Key、endpoint和响应均不进入该摘要对象或普通日志。

首轮测试失败来自测试夹具：不可变dataclass在 `replace()` 构造时即正确拒绝坏值，且 `payload_bytes` 是允许公开的计数元数据。只调整测试断言方式，没有放宽生产校验。定向4项、后端全量2161项PASS/3项既定跳过；开发wheel SHA-256 `eea3cec629b1cf64060dfb6faf7fea5ca755aaf9e42cd58779808c705af06401`。

Changed：内部Grant/Proof合同和单元测试。Files：`task_execution_grant.py`、`test_ai_task_execution_grant.py`及追溯文档。Migration/API/Dependencies：无。Compatibility：未接生产组合，不改变现有行为。Rollback：撤新增未装配模块即可，历史不变。Known Issues：PostgreSQL投影、Jobs当前Lease/Attempt Owner、正文Owner/模板构建、服务端Preview、Invocation和Provider调用均未实现。Next：`AI-04-A06-P03-P01` Jobs当前Claim绑定与PostgreSQL Execution Grant投影。
