# AI-04-A06-P05-P01 Invocation 生命周期与持久化前置核查

日期：2026-10-03；状态：`PRECHECK_PASS`；依据 CR-AI-015/016、DEC-721/740/741、冻结 DM-04/API-03、Schema0064/0072。

静态交叉核对确认：`ai_invocations`、ContextRef、Task 当前 Invocation 指针及 PENDING→RUNNING→终态数据库状态机已经由 Schema0064 提供；Schema0072追加了可空且不可变的 `content_plan_ref`。当前生产代码没有 Invocation 创建/开始/终止 Repository，也没有 AI Task Worker、ModelRouter 或 ProviderAdapter；现有 AI_PROVIDER_WORKER 仅处理无客户数据的 Provider 探针，不得复用为业务调用器。

发现的实施缺口是：0072只为 Invocation PlanRef建立外键和更新不可变触发器，0064的插入守卫早于该列，尚未在数据库端要求新 Invocation 的 PlanRef 非空并与 Task、授权快照、Content Plan的Task/Project/Provider/Model/Prompt/Schema/payload身份一致。若直接编写Repository，这些约束只能依赖应用层，无法满足“偏差失败关闭”和数据库最终守卫要求。

决定按以下顺序继续：

1. `P05-P02` 追加 Schema0073 INSERT 完整性守卫；保留旧NULL历史，不回填，新Invocation必须完整绑定同一Plan。
2. `P05-P03` 建立无正文的 Invocation Begin 合同与Repository，在同一短事务锁定当前Job Claim/Task/Grant、插入下一PENDING Attempt并更新Task当前指针；不得持有事务跨网络。
3. `P05-P04` 加入ContextRef/并发、attempt上限、fencing、回滚与Win11/PG18.6真实验证，再进入P06 Adapter调用。

本项仅设计与证据记录，无程序、Migration、API、依赖、Invocation或网络外发变化；未运行新增测试，不能据此宣称业务AI调用可用。回滚为撤销后续未装配写链；已产生的Invocation历史必须保留并向前修复。Server 2025尚未复验，Debian 13按用户指令跳过。
