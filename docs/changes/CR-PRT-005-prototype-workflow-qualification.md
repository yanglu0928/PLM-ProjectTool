# CR-PRT-005：Prototype Workflow 聚合资格与只读预览兼容扩展

日期：2026-10-08。状态：依 `CR-EXEC-001` 持续授权分步实施；Gate 2 原冻结提交 `64cdf09` 不改写。触发 WBS：`PRT-01-A11-A02`。

## 来源、冲突与风险

六阶段定义已将 `PROTOTYPE_SCOPE_DECISIONS`、`PROTOTYPE_COVERAGE` 设为 PROTOTYPE 阶段的两个必填项，数据库亦允许 PROTOTYPE→SOLUTION；运行 Registry、资格预览、Checklist 写入和阶段推进目前只开放至 REQUIREMENT。直接扩大 item_key 白名单会让缺失真实 Prototype Owner 的 PASS 失去事实依据。

现有资格预览把聚合版本引用命名为 `requirement_version_refs`，不能承载 Requirement 与 Prototype 两种受审主体。Prototype NOT_REQUIRED 决定固定受影响需求、reason、impact、`confirmed_by` 和可选 Review；现有冻结命令没有直接 EvidenceRef 字段。不得把 PM 的受权命令冒充客户签署，也不得把 Requirement 的来源 Evidence 说成决定自身的证据。Workflow 所需的依据必须分别来自：当前批准 Requirement 的固定来源 Evidence/Review、NOT_REQUIRED 决定及对应 Audit/可选 Review、以及需原型分支的 Approved PrototypeVersion/Review、受权固定制品与 Link/Coverage。

## 方案比较与选择

- 拒绝“只认有 Link/Version 的需求”：会把遗漏或未决定的需求从范围中静默删除。
- 拒绝“每条 NOT_REQUIRED 必须新造 Review/Evidence”：会伪造不存在的客户确认，且与既有 `DEC-20261008-1024` 的可选 Review 规则冲突。
- 采用当前批准 Requirement 完整集合为左侧权威范围，同一事务内把每条需求分到两类：由当前有效、固定版本的 NOT_REQUIRED 决定覆盖，或由至少一个当前 Approved PrototypeVersion 明确固定为需原型。交叉归属、缺项、外项目/过期版本、空范围均失败关闭。所有 NOT_REQUIRED 的情形仍逐条验证决定及 Requirement 的来源 Evidence/正式 Review，不等于跳过阶段。
- `PROTOTYPE_COVERAGE` 还要求需原型需求存在与当前批准 PrototypeVersion 精确双端绑定的 ACTIVE Link；仅 `VALIDATES`/`ACCEPTANCE_REFERENCE` 的已覆盖验收标准计入覆盖。所有当前验收标准必须由有效 Link 的覆盖并集覆盖，未被覆盖且仅有“原因”的项目不能自动 PASS，须通过独立受权例外/处理路径。制品当前可访问、Hash/固定版本、Review 和 Trace 均由后续 Owner 重证，不能由纯范围算法或前端提交替代。

## 与冻结基线的差异

Prototype 26 项 `/api/v1` Operation、请求/响应和 NOT_REQUIRED 既有历史不改。后续在已存在的、CR-WFL-008 新增的 `WORKFLOW_CHECKLIST_QUALIFICATION_GET` 上，对 PROTOTYPE 阶段增加只读、严格类型化 `qualified_subjects[]`（`subject_type`、`subject_id`、`subject_version_id`、`review_round_ref`），同时保留规范 Evidence UUID 集和 Workflow 强 ETag；Handover/Survey/Requirement 原响应保持不变。新投影不含正文、磁盘路径、指纹、客户身份详情或内部失败原因。Checklist 写请求不增加字段，写时仍重新完整复验；新增 PROTOTYPE→SOLUTION 运行白名单必须等两个真实 Owner、HTTP/PG 验收通过后才显式开启。该增量不是冻结 API 的 Breaking Change，新增投影仍按可追溯变更处理。

## 实施、验证、迁移与回滚

1. A02 先实现纯范围策略和正反例，输入只代表候选事实，不能生成 Workflow PASS。
2. A03 构建跨模块公开证明 Port 与 Prototype Owner，锁定当前 Requirement 范围并重证决定、Review、Evidence、Artifact、Link、Trace；缺证明统一失败关闭。
3. A04 接入 Registry/预览/Checklist/Stage Transition，保证旧阶段响应与行为兼容、权限不扩大、原操作幂等与强 ETag 不变。
4. A05 做 Windows 11/PG18.6 真正的包含/遗漏/冲突/漂移/全 NOT_REQUIRED/部分覆盖/跨项目/撤权与顺序推进验证，完整后端/前端回归、开发 wheel 和 Secret 扫描；Server 2025 单独实机验证，Debian 13 按用户指令跳过。

当前选择不增加 Schema、依赖或数据迁移；若 A03 证明既有不可变数据无法承载完整规则，须先补充本 CR 的数据差异和 up/down/历史迁移方案，不能在代码里伪造或补写旧决定。应用回滚可停止新增 Registry/Router 注册，现有 Requirement/Prototype/Workflow/Audit 历史保留；一旦已有 PROTOTYPE Checklist/Transition 历史，不得删除记录或把 Workflow 实例自动降回旧定义。Gate 3、UAT 和可用包结论仍只按客观证据关闭。

## 2026-10-08 A03 兼容修订：受审主体的 Evidence 归属

P01/P02 后发现通用 `ChecklistQualificationSubject` 要求每个受审主体至少一个 EvidenceRef，但 `PRT-03` Approved PrototypeVersion 的正式依据是固定 DocumentVersion 制品、Review 和 Trace，而不是其自身 EvidenceRef。把 Requirement 来源 Evidence 复制到 PRT-03 主体会错误陈述证据归属；虚构 Evidence 更不可接受。选择允许聚合中的单个主体 Evidence 集为空，但聚合整体仍必须至少包含一个经证明的 Evidence；本阶段 Requirement 主体须继续提供其真实来源 Evidence，PRT-03 主体以真实 Review 与受权制品/Trace 由 Owner 另行证明。现有 Handover/Survey/Requirement Owner 输出不变，单主体 `CurrentChecklistQualification` 的非空 Evidence 约束不改。空 Evidence 的 PRT-03 不会凭此获得 PASS，A03 Owner、A04写时复验与A05实例测试仍是必需前置。

差异/风险：通用聚合 Subject 构造约束小幅放宽，若错误 Owner 输出全部无 Evidence 可能削弱登记依据；在 Aggregate 根约束新增总 Evidence 非空，并保持受权 Registry、聚合写时原样匹配和 Review Basis 持久化。无 Schema、API、权限或数据迁移。验证计划：零 Evidence 聚合拒绝、混合主体的 Evidence/Review 身份和排序、既有 Workflow 全量回归，后续真实 PG/HTTP。回滚：A04 尚未开放 Prototype 注册前可撤销该内部 DTO 兼容扩展；开放并形成 Checklist 历史后不得删除记录，应先停止新注册并制定保留历史的迁移方案。

## 2026-10-08 A03 兼容修订：Document 制品物理完整性

P02 复核发现既有 `PrototypeVersionCurrentValidator` 的 Document Proof 只锁数据库中的 AVAILABLE/Hash/固定Version元数据，不能单独证明本地文件仍在或实际字节匹配。若直接把该元数据当作“制品当前可访问且Hash正确”的 Workflow PASS，会高估资格。A03 新增 Document 所有者公开物理校验 Port：在同一项目事务重读固定Version/FileObject当前状态与元数据，并用既有本地存储安全校验逐字节验证 SHA-256、长度、文件身份/重解析点；仅返回不含路径的证明。Prototype Owner 必须逐个消费；缺失、篡改、超限失败关闭。无 Schema/API/生产依赖；可能增加预览/Checklist 的磁盘读取成本，A05 需测延迟与并发，不得以缓存元数据替代实际校验。回滚仍须保持 Prototype Registry 关闭，不可静默绕过物理证明。
