# PRT-01-A06-A04：PrototypeVersion List/Get 与 ValidationReport

日期：2026-10-08。结论：`PRT_01_A06_A04_VERSION_READ_VALIDATE_PASS`。`PRT-01-A06`完成；下一项：
`PRT-01-A07-A01` Review/Formalize 前置核查。

## 实施结果

- 新增项目内Version倒序keyset分页与固定历史Get，按Version声明计数重建有序Artifact、Requirement及唯一
  Interaction；集合不完整时失败关闭，项目/Prototype复合过滤防越权读取。
- 新增`PRT_VERSION_LIST/GET/VALIDATE`授权。项目成员可读；ProjectManager/ImplementationMember可Validate。
- Validation在同一事务重证固定Template、当前Approved Requirement和当前可用Document，只返回去重问题码、
  checked_at及原version_state并写Audit；不修改Version、owned集合或Root正式指针。OutputArtifact继续报告不可用。

## 验证与偏差

- Win11/PostgreSQL 18.6验证倒序分页、游标、历史owned集合重建及跨项目拒绝。当前证明正负组合同时由A02
  实库证据与本项Service测试覆盖。
- 实库首轮夹具把JSON字面量直接放入SQLAlchemy `text()`，其中冒号被解析为绑定参数；改为显式JSONB参数后
  完整重跑PASS。这是验证脚本问题，产品读路径未失败，未放宽断言。
- 定向14项/634 subtests；全量后端3136项通过、3项跳过、4684 subtests；compileall PASS。
- wheel共1205项，SHA-256 `b8ea3055932b5548a84a891b948bc973f9dc5693ce97f679ca1ded7ea346ed1c`。

## 兼容与边界

无Schema/Migration、公开API、依赖、外发或License变化；停止注入Read/Validation Service即可回滚，历史不变。
Server2025未验证，Debian13按指令跳过。A07 Review/Formalize、A08 Link、HTTP、前端、Workflow、Gate3/UAT/
发行仍待，Gate3保持BLOCKED。
