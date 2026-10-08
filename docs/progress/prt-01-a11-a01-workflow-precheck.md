# PRT-01-A11-A01：Prototype Workflow 资格前置核查

日期：2026-10-08。状态：PRECHECK_PASS；未开放 Prototype Checklist PASS 或 SOLUTION 阶段推进。

```text
前置任务：PRT-01-A10-A07 Windows 11真实Edge/PG闭环 PASS；Requirement Workflow资格已有正式 Owner
涉及模块：prototype、requirement、review、document、workflow、evidence
涉及实体：当前 Approved RequirementVersion、NOT_REQUIRED 决定、Approved PrototypeVersion、RequirementPrototypeLink、Artifact、Review、Checklist、StageTransition
涉及API：既有 Workflow资格预览/Checklist记录/阶段推进；Prototype冻结26项不变
涉及权限：ProjectManager受权预览/记录/推进；各业务Owner在同一事务内重证固定事实
验收标准：全项目范围完整、不把空集合/草稿/送审当批准、覆盖逐条验收标准、制品当前可访问完整、失败关闭并可追溯
风险：全范围NOT_REQUIRED被静默跳过、PM决定冒充客户确认、Link或Prototype单表被当完整覆盖、旧资格预览响应无法表达Prototype聚合
```

## 事实与缺口

- 六阶段定义及数据库 Transition pair 已包含 PROTOTYPE→SOLUTION，但运行 Registry 只注册 Handover、Survey、Requirement；Checklist record、资格预览和阶段推进仍只开放前三阶段。因此当前不能宣称 Prototype Workflow 资格已可用。
- Requirement 资格 Owner 已能锁定完整当前批准需求范围，可作为 Prototype 范围输入；不得另以 Prototype/Link 列表代替全项目 Requirement 集合。空范围仍失败关闭。
- Prototype 的显式 NOT_REQUIRED 决定固定受影响 Approved RequirementVersion、理由/影响、确认主体与可选 Review；PM 命令不等同客户确认。适用需求必须由正式 Approved PrototypeVersion、当前固定制品和完整验收标准 Coverage 证明；DRAFT/IN_REVIEW 与单独 Link 均不构成批准。
- Workflow 通用 `AggregateChecklistQualification` 可保留各 Approved Review 与 Evidence；现有资格预览仅有 Handover/Survey/Requirement 三种响应投影，不能静默把 Prototype refs 放入 `requirement_version_refs`。新增只读投影需要先记录兼容 CR。

## 执行拆分

1. A11-A02：登记 Prototype 资格/预览兼容增量与完整范围规则；固定受权事实 Port、失败关闭和全 NOT_REQUIRED 判定。
2. A11-A03：Prototype Owner 在同一数据库事务内锁定当前 Requirement 范围、范围决定、批准 PrototypeVersion、完整 Link/Coverage、Document/Review/Evidence，形成聚合资格；先做负例与漂移测试。
3. A11-A04：Workflow 显式注册两项 Prototype Checklist、只读预览、PASS 写入及 PROTOTYPE→SOLUTION 顺序推进；不得通过前端提交 PASS 绕过 Owner 重证。
4. A11-A05：Windows 11/PostgreSQL 18.6 真实 Owner/HTTP/Workflow 验收、完整回归与版本说明；Windows Server 2025 单独验证，Debian 13 依指令跳过。

本项只通过编码前核查和拆分，不制造客户 Review/Evidence，不关闭 Gate 3，也不把 A07 浏览器送审视作批准。
