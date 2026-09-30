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
