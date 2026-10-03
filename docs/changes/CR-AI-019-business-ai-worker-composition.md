# CR-AI-019：业务 AI Worker 生产组合与启动边界

日期：2026-10-03；状态：依 V1.1 持续授权登记，分片实施中；关联 Gate 2 冻结 ADR-004/DM-04/API-03、CR-AI-015～018、Schema0072～0075；原冻结提交 `64cdf09` 不改。WBS `AI-04-A06-P09`。

## 差异与证据

P06～P08 已分别验证Execution Grant、精确Content/Envelope、Provider Route与Adapter、双pre-send/Secret审计、持久发送栅栏、响应解析、Suggestion成功/失败发布、过期对账、取消和显式Retry，但它们仍是独立Application/Infrastructure组件。现有Windows `AI_PROVIDER_WORKER`只组合固定Provider Probe；没有业务`AI_TASK_EXECUTE`的Owner专用claim、一步执行器、循环或生产组合。把已验组件误认为服务可运行会虚报交付状态。

现有通用Jobs `claim_next`可领取多种Owner，业务AI Worker若直接调用会越权领取Audit/Parse/Probe。Task的prepare发生在Invocation Begin之前；若内容/Prompt/授权在prepare期失败，现有P08 Failure Publisher因要求已创建Invocation而不能关闭Job+Task。Bootstrap也只有Probe/Egress/Task Policy，没有`AIProviderExecutionPolicyRegistry`所需的业务endpoint、model allowlist、响应大小和分段时限受信来源。服务计划目前仅按Probe Policy决定是否列出AI Worker。

## 方案与实施拆分

1. P02：增加Jobs-owned `claim_next_ai_task`，只领取`ai/AI_TASK_EXECUTE`；增加pre-Begin失败Owner，在无Invocation时原子关闭当前Job/Attempt/Lease与Task并写Audit，不进入自动`RETRY_WAIT`。
2. P03：实现业务AI one-shot Worker，固定`claim → prepare → begin → 双重授权/Secret/发送栅栏 → parse → success/failure publish`顺序；响应和正文在全部退出路径释放，不在日志输出。Begin已提交后无法安全发布时保留给过期对账，绝不重新发送同一Invocation。
3. P04：实现公平有界组合循环。每轮先限量对账过期业务Task，再在Probe与业务Task间交替尝试；维护准入覆盖claim、Secret、网络与发布，停止为协作排空，不强杀网络线程。
4. P05：新增严格非Secret业务Execution Policy Bootstrap来源并装配既有`AI_PROVIDER_WORKER`，该角色统一承载厂商网络I/O，但Probe与业务Adapter/策略/审计路径保持隔离。配置业务Task而未配置完整Execution Policy时启动失败关闭；服务计划在Probe或完整业务策略存在时列出该角色。
5. P06：Windows11使用一次性PG、合成License/Secret/HTTPS Provider与纯合成文档做真实服务组合验证；Windows Server 2025在网络/目标账户可用时单列。真实客户数据或真实Provider外发不由本CR授权。

## 兼容、迁移与回滚

预计不新增公开API、数据库迁移或第三方依赖；Bootstrap新增可选且严格的非Secret策略字段。未配置业务策略时历史行为保持Probe-only或不安装AI Worker。回滚为停止AI Worker并移除业务组合，保留Task/Invocation/Suggestion/Audit/Lineage；已越过发送栅栏的记录必须先对账，不能回退PENDING或删除。

## 风险与验收

- 同进程Probe与业务任务必须公平且Owner隔离，不能用Probe transport发送业务Envelope。
- 网络调用期间停止只能协作等待既有有界时限；SCM STOPPED前必须确认循环、数据库连接和秘密生命周期静止。
- prepare前失败、Begin后失败、发送栅栏后未知、结果发布失败、进程重启和Maintenance竞争必须分别验证。
- Gate 3只有在真实服务组合、正式信任、质量/性能、Server2025、UAT及交付包证据满足后才能关闭；Debian13按用户指令跳过验证但仍是兼容目标。
