# AI-04-A06-P07-P03 Provider 持久发送栅栏

日期：2026-10-03；状态：`PROVIDER_SEND_FENCE_PASS`；依据 CR-AI-018、DEC-753/755、P06-P05-P04。

新增独立 `AITaskProviderSendFenceService` 与 PostgreSQL Repository，并接入唯一Provider发送编排。顺序固定为首次pre-send→Task Secret审计/精确SecretVersion→第二次pre-send→Route/Proof稳定性→短事务栅栏→Adapter。栅栏在当前Jobs Lease/fencing下重新核对Task/Invocation/Plan/payload，且只允许精确PENDING、无结果Invocation原子变为RUNNING、写数据库观察时间并递增lock version；提交成功才允许触网。同一Invocation随后不再满足pre-send或栅栏，不能重复发送。

Windows 11/PostgreSQL 18.6 实际Claim/Plan/Invocation/Secret/Audit链配合合成Adapter证明：两次pre-send后数据库先提交RUNNING，再调用一次Adapter；第二次调用在Secret访问前失败关闭，Adapter总调用数仍为1，Key/Response清零。新增3项Fence单元，相关定向12项/11子用例，后端全量 **2241项通过、3项既有条件跳过、2912子用例、无失败**；开发wheel SHA-256 `8e4cc572f2310f47aeaab4686722d9717ccfd4ad229073f031e00a76980d086c`。

兼容/回滚：无Schema、公开API、依赖或真实Provider外发；内部发送服务构造参数收紧，未装配生产Worker。可停止消费并撤应用组合，但已提交RUNNING不能回退PENDING或删除，必须由P08终态/对账收敛。RUNNING仅证明发送边界已越过，不证明远端收到。下一项P07-P04实现版本化Output Schema Owner与有界响应解析。
