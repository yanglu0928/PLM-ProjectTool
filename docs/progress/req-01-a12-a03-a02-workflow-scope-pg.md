# REQ-01-A12-A03-A02：Requirement Workflow PostgreSQL完整范围锁

日期：2026-10-08。结论：`REQ_01_A12_A03_A02_WORKFLOW_SCOPE_PG_PASS`。下一项：
`REQ-01-A12-A04` Checklist/Preview/Transition及Windows生产组合接线。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core；Gate 3保持BLOCKED
当前WBS：REQ-01-A12-A03-A02
输入基线：CR-REQ-004、DEC-1016、A03-A01应用Owner、现有Requirement ORM/不可变Version重建
前置任务：REQ-01-A12-A03-A01 PASS
涉及模块：requirement.infrastructure.workflow_qualification_repository与Windows/PG验证脚本
涉及实体：读取并共享锁Project、Requirement、RequirementVersion、RequirementStateDecision；不改Schema
涉及API/权限：无公开API、路由或生产注册变化
验收标准：完整Root集合、最新Approved、范围决定、规范顺序、并发锁、漂移和空范围失败关闭
风险：phantom新Root；最新Draft被忽略；直接ARCHIVE无决定仍放行；锁顺序与正常写链冲突
```

## 实现结果

- 新增SQLAlchemy Repository；先以Project共享锁建立范围栅栏，再按UUID顺序共享锁全部Requirement Root、
  按Root/版本号锁全部Version、按Root/决定版本锁全部StateDecision，锁顺序与正常写链的Project→业务行
  顺序一致。
- ACTIVE Root只在`current_approved_version_ref`等于最高版本、该版本状态为APPROVED且绑定Review/Round时
  才重建完整不可变Snapshot；任何较新的DRAFT/IN_REVIEW/RETURNED都会使资格失败。
- DEFERRED/REJECTED决定必须精确落在当前Root lock version；ARCHIVED必须是决定后紧接的一次归档，
  直接ACTIVE→ARCHIVED或决定/Root版本漂移均失败关闭。
- 至少保留一个ACTIVE正式需求；空项目、只有范围决定而无正式需求、无Approved版本或范围数量不闭合
  均不生成资格锁。

## 验证、兼容与回滚

- Windows 11 / PostgreSQL 18.6隔离数据库实测：两个ACTIVE Approved Version、DEFERRED和由REJECT后
  ARCHIVED组成四Root全集；Project/Root/Version/Decision均阻止竞争`FOR UPDATE NOWAIT`并返回`55P03`。
- 空范围、较新Draft、直接归档和决定版本漂移负例均返回None；Alembic `upgrade head/check`两次无漂移，
  临时数据库已删除。
- A03-A01定向6项、后端全量3079项/3跳过、source/tests `compileall`通过；开发wheel 1167项，
  SHA-256 `e229c33218bd2c68aefb9f380e926564408a56172c38f34e18b4e1a411fc7c77`。
- 无Schema/Migration、公开API、依赖、权限、Secret、客户数据或外发变化；停止A04生产注册并删除Repository
  可回滚，既有业务/Workflow历史不变。此项不单独声称完整Owner真实业务链、HTTP、Edge或Gate 3通过。
