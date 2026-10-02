# CR-AI-014：AI Task 提交策略、Prompt版本与最小参数快照

日期：2026-10-03；状态：依 V1.1 持续授权登记，P02～P03已实施，P04～P05待继续；关联冻结 API-03 `AI_TASK_CREATE/GET`、DM-04、Schema0063～0070、CR-AI-010～013；原 Gate 2 冻结提交 `64cdf09` 不改。WBS `AI-04-A05`。

## 缺口与证据

冻结创建合同允许受控 `task_type`、input version refs、prompt policy ref、output schema ref、RAG/context policy ref、EgressAuthorizationRef 和最小业务参数，并要求读取返回 policy/version refs。现有 `CreateAITask` 与 `ai_tasks` 只有三个语法受限的字符串引用，没有最小业务参数，也没有锁定 `PromptTemplate/PromptVersion`；创建服务未证明 task type、Prompt活动版本、output schema、RAG policy 与提交策略相互匹配。若直接开放HTTP，字符串可通过语法但不代表已批准策略，Worker还可能在配置变化后解析到另一Prompt版本，违反Retry变化需新授权及不可变追踪要求。AITask公开GET/Invocation/Suggestion读取也尚不存在。

## 方案比较与决定

- A：维持三个字符串并由Worker启动时再解析。否决；提交与执行会发生策略漂移，无法形成冻结GET要求的版本证据。
- B：接收任意JSON业务参数并直接放入Job payload。否决；会形成未分型的数据旁路，可能把客户正文写入普通Job/日志链。
- C：新增不可变提交快照。部署 Task Policy 将 `prompt_policy_ref + task_type` 映射到允许的PromptTemplate、purpose和严格参数Schema；创建事务锁定当前ACTIVE PromptVersion，并证明其task type、output schema、RAG/context policy与请求一致。AITask持久化精确Prompt Template/Version、受控最小参数及规范化SHA-256；Job/Outbox继续只存Task/授权/摘要引用。选择C。

## 计划差异

Schema0070已为AITask增加可空迁移列 `prompt_template_ref`、`prompt_version_no`、`task_parameters` 与 `task_parameters_fingerprint`，并用复合外键/触发器保护Prompt归属、活动快照形态、参数摘要和历史不可变。为分阶段兼容，0070数据库允许四列全NULL或完整；0063～0069遗留NULL仅保留审计且不猜测回填。P03接入Task Policy/Prompt Owner后，应用层新Task必须完整，NULL历史禁止Worker执行。现有 `prompt_policy_ref/output_schema_ref/context_policy_ref` 保留，原冻结历史不追写。

参数只允许Task Policy声明的少量键和值类型，并设键数、深度、数组项和编码字节上限；Document/Requirement正文只能通过已授权不可变InputRef进入，不得塞入参数。策略配置非敏感、版本化、严格拒绝未知字段；参数Schema变化使用新policy reference。PromptVersion必须与提交快照精确一致，后续激活新版本不改既有Task。

## 迁移、回滚与验证

P02实现ORM/Migration0070，验证空库、有0069历史、up/down/re-up、Prompt复合引用、摘要、形态、不可变与非空拒降；P03实现Task Policy/Prompt Owner及内部创建接入，覆盖策略/版本/参数允许拒绝和事务回滚；P04实现可选创建HTTP；P05完成真实Win11/PG18写平台组合与安全读取前置。正式库升级前备份；0070无新Task历史可物理降级，有新历史则拒绝降级并向前修复或受控恢复。无真实Provider调用或客户数据外发。

风险：Prompt激活并发、参数旁路、旧Task误执行、授权payload与最终发送载荷不一致。控制：同事务行锁/复合引用、严格Task Policy、不可变参数摘要、遗留执行失败关闭；最终Worker仍须在发送前重读Authorization状态并对实际payload fingerprint和上限做精确校验，本CR不把提交验收冒充发送验收。

## P02实施结果

Migration0070、AITask ORM和迁移head合同已落地。Windows 11 / PostgreSQL 18.6 空库与历史库升级/降级/重升级、漂移、Prompt/策略/参数/摘要/不可变/拒降均PASS；后端2136运行/3跳过及wheel通过。开发中发现并修正PL/pgSQL变量歧义与非对象JSON判断顺序，最终均从头重跑。无公开API、真实Provider调用或客户数据外发；P03前不把全NULL兼容路径视为可执行新Task。

## P03实施结果

版本化Task Policy已严格绑定task type、PromptTemplate、purpose、Output/RAG引用和有界标量参数；Prompt Owner在创建事务锁定当前ACTIVE版本并由PostgreSQL规范化JSONB与计算摘要。内部新Task通过现有原子链写入完整0070快照，purpose与当前Egress Authorization精确一致；Prompt退役后新建失败，历史重放保留。Win11/PG18.6真实链、后端2140运行/3跳过及wheel通过。首轮发现JSON文本双重编码并修正为Text→JSONB显式转换后全量重跑。公开路由、部署策略来源和Worker执行仍未开启。
