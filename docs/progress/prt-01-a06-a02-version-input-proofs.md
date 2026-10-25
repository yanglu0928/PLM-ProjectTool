# PRT-01-A06-A02：PrototypeVersion 固定输入证明 Ports

日期：2026-10-08。结论：`PRT_01_A06_A02_VERSION_INPUT_PROOFS_PASS`。下一项：
`PRT-01-A06-A03` DRAFT Create Owner 与 Schema0131。

## 实施结果

- Requirement Owner 新增 `PrototypeApprovedRequirementVersionProofPort` 与 SQL Adapter，只证明同项目、
  ACTIVE Root 当前指针指向、状态为 APPROVED 且 Review/Round 非空的固定 RequirementVersion；返回复合身份、
  version_no、内容指纹和批准 Review 身份。
- PrototypeTemplate Owner 新增 `PrototypeVersionTemplateProofPort` 与 SQL Adapter，只证明 ACTIVE Root 下指定的
  PUBLISHED Version。GLOBAL 可被任一项目采用，PROJECT 必须同项目；允许固定历史 PUBLISHED Version。
- Document Owner 扩展既有 Prototype Artifact Adapter，增加语义独立的
  `prove_for_prototype_version`：只证明 GLOBAL 或同项目、ACTIVE Document、AVAILABLE DocumentVersion/FileObject，
  返回固定内容摘要、大小和 MIME。没有复用 Template 的 `template_scope` 参数，避免跨用例语义泄漏。
- 三类证明均要求调用者已经开启的 SQLAlchemy Owner 事务并使用共享行锁；无效 UUID、跨项目、非当前批准、
  非 ACTIVE/PUBLISHED/AVAILABLE 状态返回不可用。没有 `OUTPUT_ARTIFACT` Adapter，A03 对该种类继续失败关闭。

## 验证证据

- Windows 11/PostgreSQL 18.6 隔离实库证明：当前 Approved Requirement、GLOBAL/同项目 PUBLISHED Template、
  GLOBAL/同项目 AVAILABLE Document 均成功；跨项目、ARCHIVED Requirement 和 RESTRICTED File 均失败关闭。
  数据为事务局部绕过 Owner guard 后建立的合成一致基线，验证读取在正常数据库角色执行，结束后数据库销毁。
- 新增单元测试 5 项；Prototype 全组 47 项、99 个 subtest 通过。
- 全量后端 3128 项通过、3 项条件跳过、4666 个 subtest 通过；只有既有 TestClient/anyio 弃用告警。
- `compileall` 通过。首次从 backend 工作目录调用时使用了仓库根相对路径，Shell 在执行前拒绝；改用正确的
  `../../.poc-runtime` 路径后通过，不涉及产品代码或测试结果放宽。
- 开发 wheel 共 1200 项并包含四个新增 Requirement/Prototype 证明模块，SHA-256：
  `5b724bb596cc83de984faf6590adaa78d6a81166e0c57d4952ec02f7060bb09e`。

## 兼容与边界

本项只新增只读 Port/Adapter并兼容扩展既有Document Adapter，无Schema/Migration、公开API、依赖、外发或
License变化。回滚可停止注入这些证明对象；没有历史数据需要删除。Version四表Owner仍关闭，未形成任何正式
PrototypeVersion事实。

Windows Server 2025未验证，不能从Windows 11外推；Debian 13按用户指令跳过。A03 Create、A04 Read/
Validate、A07～A11、Gate 3、UAT和可使用程序包仍待，Gate 3保持BLOCKED。
