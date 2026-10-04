# CR-RAG-004：RetrievalRun、加密查询内容与最小 Context 边界

日期：2026-10-04；状态：`A02_P02_CREATE_OWNER_PASS`；WBS：`RAG-04-A01～A06`。关联 Gate 2 冻结 ADR-004/009、DM-04、SC-01～04、API-03，以及 Schema0087/CR-RAG-001～003；原冻结提交 `64cdf09` 不改。

## 差异与实施方案

冻结基线已经定义 RetrievalRun、Candidate/ScorePart、ContextBundle/Item 和异步项目 API，但生产仓库尚无这些 Owner。现有 Job 安全合同只允许引用类 `payload_refs`，不能承载 query；冻结 API 又要求 POST 后异步执行。因此需要在不改变 API 的前提下细化查询正文的持久化 Owner。

按持续授权采用以下增量方案：

1. 新增 RAG 自有 `RetrievalQueryContent` 密文实体，使用独立注入的 AEAD 数据加密端口、版本化 AAD、密钥引用和 query fingerprint；不复用 Secret 业务表，不把明文写入 Run、Job、Outbox、Audit、日志、DTO 或异常。
2. 新增冻结 SC-01 已列出的 Run/Candidate/Context/ScorePart 物理实体。Run 固定 Scope/Project/Actor、实际 Index/Model/Policy generation、Job、query/filter 指纹、rerank/egress/degraded/quality 状态；候选和 Context 都是不可变快照。
3. PROJECT 与 GLOBAL 分开授权、召回和计分，再由版本化策略合并。PROJECT 的候选、Rerank、Context 与 AI 消费每层都重新证明相同 ProjectId；GLOBAL 只允许策略登记的来源类型。
4. metadata filter 采用固定字段/操作符 AST 和参数化 SQL，拒绝 SQL、JSONPath、任意 key/column/expression。候选不足只能在同 Project/Index 扩大扫描或 exact/FTS fallback。
5. Context 表不复制无界正文，只固定 Chunk、DocumentVersion/Evidence locator、授权截取范围、顺序、token budget 与指纹；读取时按当前访问权和不可变来源投影最小 snippet。
6. Query Embedding/Reranker 若外发，必须复用统一 AIService 的 Egress Preview/Authorization、当前 Secret/路由与发送栅栏；没有授权时失败关闭。纯数据库 FTS/exact 显式记录 `NOT_APPLICABLE`。

## 风险、兼容、迁移与回滚

- 密钥风险：正式运行账户必须提供专用内容加密密钥；缺失、错误版本或解密失败时停止创建/执行，不回退明文。Windows 11 先用隔离临时密钥证明机制；正式信任源另以部署证据关闭。
- 隔离风险：所有 PROJECT 子表同时保存并复合绑定 ProjectId/Run/Index/Chunk，应用和 deferred constraint 双重校验；错误项目统一安全错误，不披露存在性。
- 质量风险：隔离合成 ACTIVE 只用于机制测试；正式无 ACTIVE 时请求失败，不把 READY、旧 generation 或历史 PoC 结果当作可用索引。
- 兼容：追加内部 Schema 和 Owner，保持冻结 `/api/v1` 路径/DTO；不引入 Redis、队列、独立向量库、本地模型或 Runtime DDL。
- 迁移：Schema0088 先落不可变基础并关闭状态转换，再逐项开放创建、执行和完成 Owner。空表可降；存在密文、候选或 Context 历史时拒降。
- 回滚：可停止新 Retrieval Job 和 HTTP 挂载；已产生的运行/审计历史保留并向前修复，密文按 R3 保留策略受控清理，不能删除历史来伪装回滚。

## 验证计划

Windows 11/PostgreSQL 18.6 验证空库/有数据升降重升、ORM drift、密文无明文泄漏、Run/Job/Index/Project 复合绑定、不可变候选/分数/Context、跨项目/旧 generation/任意 filter/无 ACTIVE/撤权/过期 License 负例及 Audit 失败全回滚。Owner 完成后以明确标记的合成 ACTIVE 验证 FTS/vector/exact、GLOBAL/PROJECT 合并、Rerank degraded 与最小 Context；不冒充业务质量。Windows Server 2025、Debian 13、20 并发/P95、正式密钥、真实业务质量、Gate 3/UAT 和发行包继续按独立证据关闭。

## A01 核查结论

静态检查确认当前只有 Chunk/Embedding/Index 实现和 AI 侧 `RAG_CONTEXT` 失败关闭合同，没有 RetrievalRun/ContextBundle 生产 Owner。冻结边界可在不破坏 API 的前提下通过专用加密 QueryContent 和追加式不可变表实现；下一项进入 Schema0088，未产生真实外发或客户数据处理。

## A02-P01 实施与结果

Schema0088/ORM已新增Run、密文QueryContent、Candidate/ScorePart及ContextBundle/Item。Run/Job不保存query正文；同事务deferred约束拒绝缺QueryContent。PROJECT候选复合重验Run、ACTIVE Index、精确source Chunk与AVAILABLE Embedding；Score固定整数微分值；Context只存引用/范围/token/指纹且完成Owner前关闭。六张表历史不可改删截断，有任一历史拒降。

Windows11/PostgreSQL18.6完成空/已有基础数据升级、drift、空历史降级重升、有历史拒降及合成ACTIVE组合；缺QueryContent、状态直改和提前Context被拒绝。后端2458/跳过3、wheel RAG86通过，SHA-256 `4fb5d1c4f465be331807cc1dcbcbddd8746216fe641d881bb22224e2c643b4fc`。无真实Provider I/O或客户数据外发；合成ACTIVE不作业务质量证据。进入A02-P02创建Owner。

## A02-P02 实施与结果

实现仅允许`fts.project.v1 + none.v1`的受权创建Owner和专用AES-256-GCM Query Cipher。输入规范化后，在同一业务事务内重验Session/CSRF、License、当前Project成员、ACTIVE Index/Model/Chunk及幂等收据；只有非重放且当前授权的请求才读取密钥并加密。Job、Run、QueryContent、Audit和收据同事务，重放仍重验当前权限，query缓冲归零。

Windows11/PostgreSQL18.6完成成功创建、Audit失败全回滚、幂等重放、撤权后重放以及CSRF/License/Index负例；query明文未进入Job/Audit。后端2467/跳过3、wheel RAG95通过，SHA-256 `14a6a8ce6b7293e63acbb7f40a15bbb513ba938a8649ea978b138b9420a0fe12`。零真实Provider I/O、零客户数据外发；合成ACTIVE仍不作Gate证据。进入A03-P01执行链前置核查。
