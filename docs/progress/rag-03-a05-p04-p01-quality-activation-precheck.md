# RAG-03-A05-P04-P01：业务质量证据与 ACTIVE 切换前置核查

日期：2026-10-04

状态：`PASS`

验证标记：`RAG_EMBEDDING_INDEX_ACTIVATION_PRECHECK_PASS`

## 编码前检查

|字段|结论|
|---|---|
|当前 Phase|Phase 2：Platform Core|
|当前 WBS|`RAG-03-A05-P04-P01`|
|输入基线|冻结 DM-04、API-03、SC-03/04、ADR-009、CR-RAG-003、Schema0086|
|前置任务|A05-P03 已证明技术 Validation、Job、Build、Lease 与 Index READY 原子收敛|
|涉及模块|RAG、AI、Audit、License；本项只核边界并拆分实施|
|涉及实体|EmbeddingIndex、IndexValidation；拟新增 QualityResult 与 ActivationResult|
|涉及 API|不修改；先实现内部证据与 Owner，公开 Validation/Activation 合同后续单列|
|涉及权限|GLOBAL 仅 DeploymentAdmin；PROJECT 仅当前 ProjectManager；登记和激活均重新验证 Session/CSRF、License|
|验收标准|失败证据可追溯但不能激活；只有全新独立留出集达到分类 90%/精确引用 98% 且隔离、越界引用、失败关闭检查通过，才可在当前事实仍有效时 READY→ACTIVE|
|风险|把合成夹具、旧失败集、技术 Recall、外部模型成功或人工确认误写成独立业务质量 PASS|

## 核查结论

现有 POC-03 50 条留出集已参与诊断，真实结果固定为 Top-5 98%、分类 48%、精确引用 74%；它不能再次作为独立通过集。仓库也没有一份未参与 Prompt、规则或标签调优且达到 90%/98% 的新业务证据。因此本项不能客观地把任何真实 Index 激活或关闭 Gate 3/UAT，但这不阻塞实现安全的证据登记和激活机制。

质量证据只保存可审计元数据、计数和 SHA-256，不保存 Query、Golden 答案或客户正文。独立性至少固定数据集引用/指纹、首次封存时间、隔离声明指纹、评估策略、样本总数、分类/精确引用正确数、ProjectId 隔离、越界引用计数和失败关闭检查。门槛由数据库固定为分类 9000、精确引用 9800 basis points；应用不得降低。

READY→ACTIVE 必须在同一事务锁定目标 Index、同用途旧 ACTIVE、技术 Validation、质量结果、当前 Model、全部来源 Chunk 与构建外发授权。目标仍为 READY、技术/质量均 PASSED、来源 ACTIVE 且指纹未漂移、Model AVAILABLE、构建授权未撤销/未过期时，先将旧 ACTIVE 置 RETIRED，再把目标置 ACTIVE，写 Audit 与不可变 ActivationResult。唯一部分索引继续作为并发最终防线。任何失败整笔回滚并保持目标 READY。

隔离 PostgreSQL 验证可构造明确标记为 `SYNTHETIC_CONTRACT_FIXTURE` 的全新临时质量集，用于证明状态机、门槛和原子性；该夹具不得写入正式环境、不得称为业务质量或 Gate 3 证据。

## 后续最小实施拆分

- `RAG-03-A05-P04-P02`：Schema0087/ORM，新增不可变 QualityResult 与 ActivationResult，并扩展 Index READY→ACTIVE、ACTIVE→RETIRED 的数据库守卫；先不提供写服务。
- `RAG-03-A05-P04-P03`：受权质量证据登记 Owner；固定独立性字段、90%/98% 门槛和失败证据，禁止正文/答案载荷。
- `RAG-03-A05-P04-P04`：受权原子激活 Owner、Audit/License/当前事实重验、唯一 ACTIVE 切换与 Windows 11/PostgreSQL 18.6 组合验证。

## 兼容、迁移与回滚

本分项仅文档，不修改代码、Schema、API、依赖、网络或外发。后续采用追加表和受控状态分支；空历史可降级，有 Quality/Activation 历史时拒绝物理降级并向前修复。原冻结提交 `64cdf09` 与 Schema0086 历史不改写。

## 验证

- 静态交叉核对 DM-04 的唯一 ACTIVE 与激活前条件。
- 静态交叉核对 API-03 的 Validation/Activation、权限与质量失败边界。
- 静态交叉核对 ADR-009 的独立留出集、90%/98%、ProjectId/越界引用/失败关闭要求。
- 静态核对 Schema0086：当前只允许 READY，尚无 ACTIVE/RETIRED 合法分支或质量证据实体。

未运行新增程序测试。本项不代表业务质量、ACTIVE、Gate 3、UAT、正式性能、Windows Server 2025、Debian 13 或发行包通过。
