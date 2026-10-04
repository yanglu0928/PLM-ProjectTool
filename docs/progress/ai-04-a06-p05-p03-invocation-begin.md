# AI-04-A06-P05-P03 Invocation Begin 原子持久化

日期：2026-10-03；状态：`INTERNAL_PG_PASS`；依据 CR-AI-015/016、DEC-741～743、Schema0073。

新增内部 `AITaskInvocationBeginService` 与 PostgreSQL Repository。Grant Issuer提供调用方事务内签发入口；服务在同一短事务内重验当前Job Claim/Task/授权/License，插入下一 `PENDING` Invocation，并把Task当前Invocation指针、状态、开始时间和锁版本原子推进。事务提交后再次检查License；网络发送边界仍必须再检。Invocation只持久化版本身份、摘要、限制和引用，不保存Prompt、正文、参数值、Secret或Provider响应。

当前Plan Builder只支持 `no-retrieval.v1/NONE`，Repository因此写入空Retrieval/Context；若未来Plan要求RAG，Schema0073会拒绝与Plan不一致的写入，不能静默当空Context。`request_payload_fingerprint`取服务端Plan已批准摘要，后续外发前仍须重建Envelope并逐字节复核。

Windows 11/PostgreSQL 18.6真实UoW验证：精确PENDING Invocation与Task指针/状态一次提交；同Task第二次Begin失败关闭；在写入后注入故障使Invocation和Task更新全部回滚；全程零Provider I/O。首次验证暴露UoW需显式commit，补齐后从新数据库完整重跑通过。定向9项，后端全量 **2213项通过、3项既有条件跳过、无失败**；wheel SHA-256 `c6af40d3c0558987e475b1f0bc0c3a7528a48ff92190a99ea394ef4cbf815d0b`。

兼容/升级/回滚：无新Migration、公开API、依赖或生产Worker装配；0073必须先安装。未装配该服务即可回滚应用，已创建Invocation/Task状态历史不得删除或倒写，只能由后续终态命令收敛。提交后License变化会留下安全的PENDING记录但不返回可用Grant，后续P07/P08需提供终态/对账。下一项 `AI-04-A06-P05-P04` 组合真实Jobs Claim、Grant、Content Plan/Envelope与Begin，并验证fencing/attempt/发送前Proof；仍不进行Provider调用。
