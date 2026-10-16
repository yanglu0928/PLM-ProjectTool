# PRT-01-A06-A01：PrototypeVersion Create/Read/Validate Owner 前置核查

日期：2026-10-08。结论：`PRT_01_A06_A01_VERSION_OWNER_PRECHECK_PASS`。下一项：
`PRT-01-A06-A02` 固定输入证明 Ports。

## 冻结合同与现状

- API-04 已冻结 `PRT_VERSION_LIST/CREATE/GET/VALIDATE`；CREATE 仅由 ProjectManager、
  ImplementationMember 创建 DRAFT，LIST/GET 是项目成员只读，VALIDATE 只生成报告且不改变 Version 状态。
- Schema0130 已固定 Version、ArtifactRef、RequirementRef、InteractionSpec 结构，但四表 Owner 仍关闭；当前
  没有 Version Service、Repository、授权 Policy、持久命令结果或 ValidationReport 实现。
- Requirement Owner 已有不可变 Version 和 APPROVED 状态；Template Owner 可读取同项目 PROJECT 或 GLOBAL
  的历史 PUBLISHED Version；Document Owner 可在同事务证明 AVAILABLE DocumentVersion、ACTIVE Document
  和 AVAILABLE FileObject。OutputArtifact 尚无正式 Owner，因此不得接受其裸 UUID。
- 统一 AIService/AITask 只可形成建议态 Draft 输入或来源证明，不能作为 Artifact、Requirement 批准、
  Validation PASS 或正式 PrototypeVersion 的替代事实。

## Owner 边界

1. Requirement 证明必须在调用者事务内锁定同项目、当前 `APPROVED` 的固定 RequirementVersion，并返回
   Requirement/Version 复合身份、内容指纹、Review/Round；缺失、跨项目、SUPERSEDED 或无批准 Review 均失败关闭。
2. Template 证明必须锁定 ACTIVE Root 下指定的 PUBLISHED 固定 Version；PROJECT 必须同项目，GLOBAL 可供
   项目使用。允许固定历史 PUBLISHED Version，不把 Root 后续修订改写到既有 PrototypeVersion。
3. `DOCUMENT_VERSION` 证明必须由 Document Owner 返回同项目或 GLOBAL、AVAILABLE 且文件可用的固定内容摘要；
   `OUTPUT_ARTIFACT` 在 Owner 建立前明确返回不可用，不猜测表结构、不以 AITask ID 替代。
4. A06-A03 在单一事务中完成授权、License、全部证明、内容指纹、DRAFT Version及owned集合、不可变结果、
   Audit 和 receipt；同 Prototype Root 行锁串行 version_no/supersedes，DRAFT 不更新正式指针。
5. A06-A04 LIST/GET 每次重证项目成员资格；VALIDATE 重建固定集合并重验当前 Artifact 可访问性、Requirement
   Approved事实、Template固定身份、Interaction安全合同和coverage完整性，仅返回报告/Audit，不修改状态。

## 原子拆分

- `A06-A02`：三个目标 Owner 的固定输入证明 Port/SQL Adapter；OutputArtifact 失败关闭。
- `A06-A03`：`PRT_VERSION_CREATE`、Schema0131 Owner开放/命令结果闭包、并发/幂等/Audit。
- `A06-A04`：内部 LIST/GET、只读分页和 `PRT_VERSION_VALIDATE` 报告；无状态推进。

## 验收与风险

每项执行类型负例、跨项目、非当前批准、历史Template、不可用文件、OutputArtifact、事务边界和撤权测试；
A03执行Win11/PostgreSQL 18.6并发、重放、Audit故障回滚、完整集合闭包及有历史拒降；A04执行固定历史读取和
漂移Validation。然后运行全量后端、compileall、wheel及Secret扫描。

A01只有冻结对账和拆分，无Schema/API/代码/依赖/外发。Windows Server 2025未验证，Debian 13按用户指令
跳过；Gate 3、UAT、前端、发行与可使用程序包仍待，Gate 3保持BLOCKED。
