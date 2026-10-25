# PRT-01-A05-A01：PrototypeVersion Schema/Owner 前置核查

日期：2026-10-08。结论：`PRT_01_A05_A01_VERSION_PRECHECK_PASS`。下一项：
`PRT-01-A05-A02` PrototypeVersion Schema0130。

## 冻结对账

- PRT-03是PROJECT不可变业务版本，归属一个PRT-02 Prototype；字段固定为version_no、ArtifactRefs、
  RequirementVersionRefs、TemplateVersionRef、InteractionSpec、ReviewSubjectRef和version_state。
- 冻结物理表为`prt_prototype_versions`及owned表`prt_version_artifact_refs`、
  `prt_version_requirement_refs`、`prt_interaction_specs`；不得用TraceLink、正文JSON或Package membership替代。
- `PRT_VERSION_CREATE`只创建DRAFT；VALIDATE不改变状态；只有后续`PRT-03 + PROTOTYPE_ALL_V1`正式Review
  才能进入APPROVED并更新Prototype正式指针。AI输出只能作为建议/Draft输入，不能自动批准或执行代码。
- 输入只允许Approved RequirementVersion、固定PUBLISHED TemplateVersion和经Owner证明的固定Artifact；
  GLOBAL TemplateVersion可用于项目，PROJECT TemplateVersion只能同项目。

## 缺口与决定

- 当前没有PRT-03表/ORM/Migration/Owner。Requirement Approved事实和Template固定版本已具备读取基础；
  OutputArtifact Owner仍不存在，因此后续Create对该Artifact种类继续失败关闭，但可接受同项目/允许GLOBAL的
  AVAILABLE DocumentVersion，不以裸UUID或AITask结果绕过。
- Schema0130建立Version主表、两类有序引用和每Version恰一条InteractionSpec。InteractionSpec保存有界、
  类型化、不可执行JSON合同；即使静态原型也保存`interactions: []`，不得保存script/command/URL执行入口。
- 每个Version固定1～100个ArtifactRef、1～200个Approved RequirementVersionRef、一个TemplateVersion和
  一个InteractionSpec；coverage summary为有界结构化JSON对象并进入内容指纹。计数字段与提交闭包防止
  声明集合不完整。
- Version链使用同Prototype复合FK；初版`version_no=1/supersedes=NULL`，后续精确指向原最新Version。
  DRAFT创建不更新`current_approved_version_ref`；正式指针保持A07前的数据库窄门。
- ReviewRef/RoundRef成对可空，A07送审/终态才写入；状态候选与Requirement版本一致采用
  `DRAFT/IN_REVIEW/APPROVED/RETURNED/SUPERSEDED/RESTRICTED`，但A02 Schema后所有业务写仍关闭。

## 实施拆分

1. `A05-A02`：Schema0130/ORM、复合FK、计数/顺序/不可变/Owner关闭、空库和有数据升降验证。
2. `A06-A01`：Create/Read/Validate Owner前置核查，固定Requirement/Template/Artifact/Interaction证明口径。
3. `A06-A02`：Approved Requirement与固定TemplateVersion证明Port；OutputArtifact继续失败关闭。
4. `A06-A03`：DRAFT Create、不可变集合、链/幂等/Audit/并发；统一AIService只提供受控Draft输入。
5. `A06-A04`：内部List/Get与ValidationReport，不改变状态。

## 兼容、迁移与回滚

A01仅文档和决策，无Schema/API/代码/依赖/外发。A02只增加冻结表且Owner关闭；空历史可降0129，产生
PrototypeVersion历史后拒绝破坏性降级。冻结四个Version Operation、角色和HTTP路径不变，`64cdf09`保留。

Windows Server 2025与Debian 13本项均无运行结论；Debian按用户指令跳过。OutputArtifact、A02/A06、
Review/Link/HTTP/前端、Gate 3、UAT和发行待，Gate 3保持BLOCKED。
