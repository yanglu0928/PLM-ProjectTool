# PRT-01-A07-A03-P01：Prototype 批准 Trace 前置核查

日期：2026-10-08。结论：`PRT_01_A07_A03_P01_APPROVAL_TRACE_PRECHECK_PASS`。下一项：
`PRT-01-A07-A03-P02` Approval Trace Manifest Schema0133。

## 编码前检查

```text
当前Phase：Phase 2保持IN_PROGRESS；Gate 3保持BLOCKED
当前WBS：PRT-01-A07-A03-P01
输入基线：冻结PrototypeVersionApproved事件、TRC-01、PRT-03/04、Schema0132、CR-PRT-001
前置任务：A07-A02-P01/P02状态窄门和真实Subject Owner均PASS
涉及模块：prototype、trace、review、requirement、document、audit
验收标准：批准Review/Round不可变绑定；Template/Requirement/Artifact反向来源完整；同事务、可重放、无半边
风险：把Review UUID伪造成Trace Version；批准成功但来源边部分缺失；调用公开Trace Service造成嵌套事务
```

## 核查结论

1. 通用`TraceVersionRef`只接受冻结业务版本类型；Review/Round不是合法Trace节点，`trc_links`也没有Review/
   Round字段。因此不能用一条普通TraceLink完整表达`PrototypeVersionApproved`批准依据。
2. PRT-03批准后的反向来源应投影为三类现有合法边：固定TemplateVersion(`PRT-04`)和DocumentVersion
   (`DOC-02`)以`DERIVED_FROM`指向Approved PrototypeVersion，RequirementVersion(`REQ-03`)以`IMPLEMENTS`
   指向该版本。每条边必须与Version owned集合一一对应，不接受调用方补充或删减。
3. 新增Prototype-owned不可变Approval Trace Manifest，固定PrototypeVersion、Review/Round、批准结果、内容
   指纹、Template、全部Requirement/Artifact及对应TraceLink；延迟闭包要求Manifest和边全集同时存在。
4. 批准终态在Review调用方同一事务内消费当前事实、写Version/Root结果、Manifest、通用Trace边和Audit；不得
   调用自带UOW/Session/CSRF/幂等收据的公开TraceCreateService形成嵌套事务。低层Trace仓储仍只写自己的表。
5. RETURNED/WITHDRAWN不产生批准Manifest或来源边；旧批准版被SUPERSEDE时保留其历史Manifest/边，后续
   当前事实消费者必须同时核验Root当前指针，不能仅凭历史ACTIVE边判断当前批准。

## 实施拆分与偏差

- `A03-P02`：Migration0133建立Approval Trace Manifest及有序来源/TraceLink闭包；空历史可降，有历史拒降。
- `A03-P03`：实现Prototype Approval Trace Owner/Repository并接入APPROVED终态；真实PG验证全集、回滚、重放。
- 原计划单项A03拆为两个实现子项，是为避免Schema与跨Owner事务投影混在一个不可回滚任务；不改变冻结API、
  Relation枚举、业务Scope或批准语义。

本项纯文档，无Schema/API/代码/依赖/外发。Windows Server 2025未验证，Debian 13按指令跳过；Gate 3保持
BLOCKED，不能把本核查描述为批准Trace已实现。
