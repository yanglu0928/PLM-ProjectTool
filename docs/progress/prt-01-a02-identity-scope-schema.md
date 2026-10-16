# PRT-01-A02：Prototype identity、membership 与 NOT_REQUIRED Schema

日期：2026-10-08。结论：`PRT_01_A02_IDENTITY_SCOPE_SCHEMA_PASS`。下一项：`PRT-01-A03`
Package/Prototype identity Owner、状态、显式范围决定、持久结果与 Audit。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core；Gate 3保持BLOCKED
当前WBS：PRT-01-A02
输入基线：CR-PRT-001、PRT-01/02冻结Root、PrototypeState、NOT_REQUIRED DTO与Workflow范围决定规则
前置任务：PRT-01-A01 PASS；Requirement固定Version/Review事实已存在
涉及模块：prototype ORM、Alembic metadata、合成PG验证；不开放Application/API/UI
涉及实体：PrototypePackage、Prototype、PackageMembership、ScopeDecision、受影响RequirementVersion refs
涉及API：无运行路由；current approved pointer保留nullable且保持关闭
涉及权限：仅数据库User/Project FK；角色/Session/License留A03 Owner
验收标准：同项目membership、固定RequirementVersion、决定唯一/有序、Review成对、初态关闭、历史拒降
风险：半套NOT_REQUIRED决定；跨项目需求范围；悬空正式指针；破坏性降级
```

## 实施结果

- 新增 Migration `20261008_0122` 与五张 `prt_*` 表：Package、Prototype、membership、不可变范围决定和
  受影响固定 RequirementVersion 引用；全部显式携带 ProjectId，membership 与需求版本使用复合 FK 拒绝
  跨项目组合。
- PrototypeState 固定 `ACTIVE / NOT_REQUIRED / ARCHIVED / RESTRICTED`；A02只允许 Package/Prototype
  `ACTIVE/v0` 初态，正式指针必须为空。ScopeDecision及其RequirementRefs在A03前全部拒写，防止直接形成
  无原子闭包的 NOT_REQUIRED 事实。
- NOT_REQUIRED决定固定reason、impact、确认人、可选成对Review/Round、before/after lock version；每个
  Prototype至多一个决定，受影响RequirementVersion去重且ordinal唯一。Approved状态、Review同项目与连续
  ordinal属于A03当前事实Owner验证，A02不凭Schema推断业务合格。
- 空历史允许降到0121并重升；任何五表历史均拒绝物理降级。更新Alembic metadata、迁移head和ORM注册
  清单，无公开API、依赖、Secret、客户数据或外发变化。

## 验证

- Windows 11 / PostgreSQL 18.6：已有库/空库升级、空历史降级/重升、Alembic drift、同项目membership、
  跨项目Prototype和RequirementVersion拒绝、Owner关闭、截断拒绝、历史拒降：PASS。
- 新增Schema单元测试5项；完整后端`3089`项PASS、`3`项按既有条件跳过；`compileall` PASS。
- 开发wheel构建PASS，`1171` entries，SHA-256
  `ec80a5968b87e0786091e259c61ff32714246b8ee90b6f5be6e245407d157c1d`。

本项没有创建正式Prototype、客户确认或Approved事实，不证明Owner、API、Review、Workflow、Gate 3、UAT
或发行通过。Windows Server 2025未执行本轮；Debian 13按用户指令跳过。
