# CR-PAR-001：Parser 正式基础合同前置的阶段时序调整

日期：2026-09-30；状态：持续授权下批准实施；原 Gate 2 冻结提交 `64cdf09` 保留，Gate 3 仍未通过。

## 来源与冲突

V2.1 将 Parser/OCR Worker 放在 Phase 3，但 Phase 2 的 EVD-01 Evidence 精确定位必须依据固定 DocumentVersion 的生产结构化结果复验。`evd-01-a03-p02-a02-precision-precheck.md` 已证实 PoC `ParsedDocument` 不是正式受权结果，现有 ParseRecord 只证明持久元数据/只读状态；继续等待完整 Gate 3 会使 Evidence Viewer 和正式业务证据闭环无法实现。上传提交的 Job/Outbox 前置已由 CR-DOC-006 处理，不代表 Worker 已执行。

## 方案比较与选择

- 不选以 PoC 结构或全文 SHA 冒充精确定位：会虚构来源事实，违背 DM-03 与用户点击原文定位需求。
- 不选削减九类 Evidence Locator 或提前把 Gate 3 标 PASS：破坏冻结验收。
- 选择在 Phase 2 只前置生产 Parser 所需的基础合同与随后可单独验证的解析/结果发布任务；保持 PostgreSQL Job/Outbox、独立 Worker、原技术栈与 `/api/v1` 不变。首项 `PAR-01-A01` 只实现固定版本输入与解析策略选择，后续真实 Worker/结果/八类定位逐项验证。Phase 3 的整体 AI/RAG 验收及 Gate 顺序不自动改变。

## 差异、风险、迁移与回滚

差异仅为依赖任务的实施时序，不修改冻结架构、数据模型、API、技术栈或 Scope。早期基础合同可能与后续 OCR/格式能力不匹配，故每个 profile 固定版本；不支持的 MIME、伪造版本/摘要或不完整来源失败关闭，不把策略选择当文件完整性或授权证明。`PAR-01-A01` 不新增依赖、ORM/Migration、路由或 Worker；可撤该独立模块回滚。正式解析输出不得含绝对路径/Secret，AI/客户资料不外发。未来结果 Schema/存储如需变更另立增量 CR/Migration 并验证空库与有数据升级及受控回退。

## 验证与关闭条件

首项单元验证六类 PoC 文档格式及受控图片 OCR 策略、未知/畸形 MIME、错误 UUID/Hash/大小、输入不变性；后端全量回归与 wheel 构建。后续独立证明受权固定版本文件读取、实际六类解析/OCR、Parser Version/结果 Hash、Job lease fencing/幂等发布、八类真实位置复验、Windows 11/Server 2025 与发行安装；Debian 13 按用户当前暂不验证但保留正式兼容目标。缺证据时对应任务/Gate 维持 INCOMPLETE。

2026-09-30 进展：PAR-01-A01 profile 合同、A02-P01 Document 输入元数据及 A02-P02 当前租约下的真实文件字节快照已分别验证并同步；详见各 WBS 记录。正式 Worker、解析结果发布、八类位置复验和 Gate/发行证据仍缺，CR 不关闭这些条件。

2026-09-30 后续：PAR-01-A03-P01 已完成纯文本/CSV 的真实抽取、类型化可重放源位置及版本化候选结果。3200万字符或10万节点以上显式失败，绝不截断为成功；该限制与其余格式、Worker、受权Evidence定位仍需后续任务处理，不改变 Gate 结论。

2026-09-30 后续：PAR-01-A03-P02 已完成合成 DOCX/PPTX/XLSX 的真实抽取与类型化位置；沿用 POC-01 已验证的 Office 依赖版本，增加 ZIP/扫描上限。仍非受权 Evidence 复验，且不改变 Gate 结论。

2026-09-30 后续：PAR-01-A03-P03 已完成合成原生 PDF 文本逐页位置；任一无文本页失败并要求 OCR，不标部分成功。正式许可、OCR/Worker/发布与受权定位、Gate 仍待。

2026-09-30 后续：PAR-01-A03-P04-P01 已用 PoC 已验证离线模型完成生产 PaddleOCR 主链适配器的合成图片推理，模型指纹、边界与生产依赖被固定；尚未作为正式解析结果发布，不改变 Gate 结论。

2026-09-30 后续：PAR-01-A03-P04-P02 已以真实本地模型在无落盘合成 PNG/混合 PDF 上跑通候选抽取；OCR 区域/置信度/模型指纹已固定，但仍不具备结果持久发布、受权 Evidence 或客户资料质量结论，Gate 不变。

2026-09-30 后续：PAR-01-A04-P01 已完成结构化结果文件的私有一次性写入与复验，沿用冻结 Schema V1 的结果引用形状；DB/Job/ParseRecord fenced 发布尚未完成，孤儿不等于成功，Gate 不变。

2026-09-30 后续：PAR-01-A04-P02-P01 已真实验证首次当前租约的 ParseRecord PENDING→RUNNING，不包含成功结果发布或重试历史；A04-P02 整体未关闭，Gate 不变。

2026-09-30 后续：PAR-01-A04-P02-P02 已在隔离 PostgreSQL18 验证首个 RUNNING Attempt 的 ResultRef、ParseRecord、真实 Audit 与 Job 在当前 lease 下原子成功发布及失败回滚。私有文件与数据库仍非同一事务，过期重试历史、正式 Worker 组合和受权 Evidence 待独立处理；A04-P02 整体及 Gate3 不关闭。

2026-09-30 后续：PAR-01-A04-P02-P03-P01 已证明当前租约前每代 JobAttempt 的终结事实、连续顺序和 Lease 一致性；Document 旧 ParseRecord 对账与新尝试启动尚未执行，不把此证明等同于重试支持，Gate3 不变。

2026-09-30 后续：PAR-01-A04-P02-P03-P02 已在同一 Job 的第2/3代验证旧 ParseRecord 对账、新代 RUNNING 启动、真实 Audit 与异常回滚；冻结 Schema V1 不变。新 Job 的用户主动重试、后代成功结果发布及正式 Worker 未完成，P03/Gate3 不关闭。

2026-09-30 后续：PAR-01-A04-P02-P03-P03 已在隔离 PG18 验证同一 Job 第2/3代的真实私有结果文件原子成功发布及旧代拒绝。后台过期接管链具备内部启动/发布能力；跨 Job 用户主动 retry 与正式 Worker loop/取消/失败/崩溃恢复、Evidence、质量及 Gate3 尚未完成。

2026-09-30 后续：PAR-01-A05-P01-P01 已为 Parser Worker 增加 Jobs 自有的 DOCUMENT_PARSE 定向领取，真实混合队列未消耗其他 Owner Job；仅领取入口，不代表 Worker 已执行解析或具备心跳/取消/失败处理，Gate3不变。

2026-09-30 后续：PAR-01-A05-P01-P02 已在 Windows11 隔离 PG18 和真实本地文件上验证一次 Parser Worker 成功执行与长任务心跳，成功发布受租约保护；仅内部 Queue/Document 源桩，未装配独立守护进程及失败分类/取消/恢复，不把单步成功当完整 Worker、Gate3 或发行通过。

2026-09-30 后续：PAR-01-A05-P01-P03 已在隔离 PG18 验证当前租约下已启动 ParseRecord/Job/Audit 的原子失败、重试/终止与回滚，真实文件 Worker 的非法编码也完成失败链。未启动错误不伪造 ParseRecord；状态呈现、协作取消、崩溃恢复、独立进程和 Gate3 尚待。

2026-09-30 后续：PAR-01-A05-P01-P04-P01 增加 Jobs 内部 Parser 取消识别/当前租约确认，真实 PG18 证明请求后不续租并拒绝旧代/过期/其他 Owner；尚未接 Worker/Document/Audit 或用户请求 Owner，不称完整取消。

2026-09-30 后续：PAR-01-A05-P01-P04-P02 已将取消识别接入 Worker 安全点，并在当前租约下同事务取消 Document ParseRecord、Audit 和 Job。真实文件/PG 长抽取取消不产生结果引用；用户请求授权 Owner、过期恢复及独立进程仍待，不称端到端取消或 Gate3 通过。
