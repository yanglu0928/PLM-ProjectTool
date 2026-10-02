# CR-AI-014：AI Task 提交策略、Prompt版本与最小参数快照

日期：2026-10-03；状态：依 V1.1 持续授权登记，待按 P02～P05 分片实施；关联冻结 API-03 `AI_TASK_CREATE/GET`、DM-04、Schema0063～0069、CR-AI-010～013；原 Gate 2 冻结提交 `64cdf09` 不改。WBS `AI-04-A05`。

## 缺口与证据

冻结创建合同允许受控 `task_type`、input version refs、prompt policy ref、output schema ref、RAG/context policy ref、EgressAuthorizationRef 和最小业务参数，并要求读取返回 policy/version refs。现有 `CreateAITask` 与 `ai_tasks` 只有三个语法受限的字符串引用，没有最小业务参数，也没有锁定 `PromptTemplate/PromptVersion`；创建服务未证明 task type、Prompt活动版本、output schema、RAG policy 与提交策略相互匹配。若直接开放HTTP，字符串可通过语法但不代表已批准策略，Worker还可能在配置变化后解析到另一Prompt版本，违反Retry变化需新授权及不可变追踪要求。AITask公开GET/Invocation/Suggestion读取也尚不存在。

## 方案比较与决定

- A：维持三个字符串并由Worker启动时再解析。否决；提交与执行会发生策略漂移，无法形成冻结GET要求的版本证据。
- B：接收任意JSON业务参数并直接放入Job payload。否决；会形成未分型的数据旁路，可能把客户正文写入普通Job/日志链。
- C：新增不可变提交快照。部署 Task Policy 将 `prompt_policy_ref + task_type` 映射到允许的PromptTemplate、purpose和严格参数Schema；创建事务锁定当前ACTIVE PromptVersion，并证明其task type、output schema、RAG/context policy与请求一致。AITask持久化精确Prompt Template/Version、受控最小参数及规范化SHA-256；Job/Outbox继续只存Task/授权/摘要引用。选择C。

## 计划差异

Schema0070拟为AITask增加可空迁移列 `prompt_template_ref`、`prompt_version_ref`、`task_parameters` 与 `task_parameters_fingerprint`，并用复合外键/触发器保护Prompt归属、活动快照形态、参数摘要和历史不可变。迁移后新Task必须完整；0063～0069遗留NULL仅保留审计，禁止Worker执行且不猜测回填。现有 `prompt_policy_ref/output_schema_ref/context_policy_ref` 保留，原冻结历史不追写。

参数只允许Task Policy声明的少量键和值类型，并设键数、深度、数组项和编码字节上限；Document/Requirement正文只能通过已授权不可变InputRef进入，不得塞入参数。策略配置非敏感、版本化、严格拒绝未知字段；参数Schema变化使用新policy reference。PromptVersion必须与提交快照精确一致，后续激活新版本不改既有Task。

## 迁移、回滚与验证

P02实现ORM/Migration0070，验证空库、有0069历史、up/down/re-up、Prompt复合引用、摘要、形态、不可变与非空拒降；P03实现Task Policy/Prompt Owner及内部创建接入，覆盖策略/版本/参数允许拒绝和事务回滚；P04实现可选创建HTTP；P05完成真实Win11/PG18写平台组合与安全读取前置。正式库升级前备份；0070无新Task历史可物理降级，有新历史则拒绝降级并向前修复或受控恢复。无真实Provider调用或客户数据外发。

风险：Prompt激活并发、参数旁路、旧Task误执行、授权payload与最终发送载荷不一致。控制：同事务行锁/复合引用、严格Task Policy、不可变参数摘要、遗留执行失败关闭；最终Worker仍须在发送前重读Authorization状态并对实际payload fingerprint和上限做精确校验，本CR不把提交验收冒充发送验收。
