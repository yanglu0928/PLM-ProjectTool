# PRT-01-A07-A03-P02：Prototype Approval Trace Manifest Schema0133

日期：2026-10-08。结论：`PRT_01_A07_A03_P02_APPROVAL_TRACE_MANIFEST_PASS`。下一项：
`PRT-01-A07-A03-P03` Approval Trace Owner/Repository及APPROVED终态同事务接入。

## 实施结果

- Migration0133和ORM新增不可变`prt_version_approval_trace_manifests`、
  `prt_version_approval_trace_sources`；每个Approved PrototypeVersion和APPROVED Review状态结果最多一个Manifest，
  来源按连续ordinal固定对应通用`trc_links`。
- 延迟闭包同时重证Prototype Root当前批准指针、Approved Version、Review/Round、批准结果、Approver、内容指纹、
  TemplateVersion及声明计数；Template、Document、Requirement来源必须与Version owned集合一一对应，无缺边或额外边。
- 固定边形状为`PRT-04 --DERIVED_FROM--> PRT-03`、`DOC-02 --DERIVED_FROM--> PRT-03`、
  `REQ-03 --IMPLEMENTS--> PRT-03`；Manifest来源必须引用完全相同且仍为ACTIVE的TraceLink。
- 新写入APPROVED Review状态结果必须在同一事务拥有完整Manifest；RETURNED/WITHDRAWN等非批准结果不得绑定Manifest。
  两表拒绝UPDATE/DELETE/TRUNCATE；存在Manifest历史时0133拒绝降级。

## 验证证据

- Windows 11、PostgreSQL 18.6隔离数据库：空库升至0133、空历史降至0132并重升；批准结果缺Manifest、Manifest
  缺来源、TraceLink身份错配、UPDATE/DELETE/TRUNCATE均失败关闭；完整Template/Document/Requirement三边和
  Manifest同事务提交；有历史数据时降级拒绝。验证器返回
  `PRT_01_A07_A03_P02_APPROVAL_TRACE_MANIFEST_PASS`。
- 定向Schema/Migration/ORM 23项通过；后端全量3148项通过、3项既有条件跳过；`compileall`和`git diff --check`
  通过。开发wheel包含Migration0133，SHA-256为
  `10ba4ab5a7654e06145aeea97e00ec730c32301237fbab59a34eb71c6b7f784f`（1210项）。

## 兼容性、偏差与回滚

- 这是前向加表和延迟约束，不改冻结`/api/v1`、Relation枚举、依赖或外发边界。0132之前已经存在的批准结果不在
  升级时伪造/回填Manifest；0133只对升级后的新批准写入强制闭包。当前未执行生产迁移，若未来发现正式旧批准历史，
  必须另立可审计回填Change Request，不能合成来源边。
- P02只建立DB闭包，现有Subject Owner尚未写Manifest；因此升级到0133后批准入口按设计失败关闭，直至P03把低层
  Trace仓储、Manifest仓储和APPROVED终态纳入调用方同一事务。不能把本项描述为公开批准流程已可用。
- 空Manifest历史可降0132；存在历史拒降。业务回退只能停止新批准并保留历史，不删除Manifest或通用Trace边。
  Windows Server 2025未验证；Debian 13按用户指令跳过；Gate 3保持BLOCKED。
