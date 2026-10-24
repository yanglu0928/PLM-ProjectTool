# AI-04-A06-P03-P01-A01：AI Task 当前 Job Claim Owner 合同

- 日期：2026-10-03
- 结果：`INTERNAL_OWNER_CONTRACT_PASS / NO_EXTERNAL_CALLS`
- 依据：CR-AI-015、DEC-721/722、Jobs Lease/Fencing基线

新增Jobs-owned `AITaskExecutionClaim`，固定当前Job、AITask、Project、原actor、Trace、EgressAuthorizationRef、Input fingerprint、fencing token、attempt和max attempts；Input摘要不进入对象repr。`AITaskExecutionClaims` 只在调用方短事务中接受Jobs Repository给出的当前证明，并严格复核请求Job/token与证明身份，Repository异常统一失败关闭为Jobs安全错误。

该合同弥补通用 `ClaimedJob` 不包含原actor和最大尝试数、不能单独证明AI Task/授权来源的问题；它不是业务权限、License、外发授权或可跨事务复用的permit。P03-P01-A02须由Jobs PostgreSQL实现核当前ACTIVE Lease/Attempt、RUNNING Job、原Outbox和不可变payload绑定，再由AI模块组合Grant。

定向7项（含P02 Grant）、后端全量2164项PASS/3项既定跳过；开发wheel SHA-256 `ae993dc1a638c20c488df2d86e3eea4c04bc7417b58508e3c75f42778eab5e52`。Changed：Jobs内部Owner DTO/Service和单测。Migration/API/Dependencies：无。Compatibility：未装配，无运行行为变化。Rollback：撤未引用合同即可。Known Issues：PostgreSQL Repository、实际claim、完整Grant投影和后续正文Envelope仍待。Next：`AI-04-A06-P03-P01-A02`。
