# REQ-01-A12-A05：Windows 11 / PostgreSQL Requirement Workflow闭环

日期：2026-10-08。结论：`REQ_01_A12_A05_WORKFLOW_PG_PASS`。下一项：
`REQ-01-A12-A06` Requirement Workflow前端。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core；Gate 3保持BLOCKED
当前WBS：REQ-01-A12-A05
输入基线：CR-REQ-004、DEC-1016～1019、A04 Windows生产组合
前置任务：REQ-01-A12-A04-A02 PASS
涉及模块：只新增隔离验证脚本与证据文档；正式代码不变
涉及实体：真实Requirement/Version/Review/Workflow历史，全部位于临时数据库
涉及API/权限：生产Preview/Record/Transition路由、真实Session/CSRF/Project角色/License组合
验收标准：真实聚合资格、复数响应、写时重证、两项PASS、REQUIREMENT→PROTOTYPE、Audit/回放
风险：测试夹具伪造批准；漂移未在写时阻止；Review证明未落不可变Basis；临时数据残留
```

## 验证结果

- 通过正式Requirement服务创建Root与Version，绑定当前Project Evidence、已批准GLOBAL Capability及五要素
  Acceptance；通过正式Review提交/决定服务形成真实`REQ-03 + REQUIREMENT_ALL_V1`批准事实。
- Windows生产组合的两个Preview均返回同一真实Version、ReviewRound和Evidence；不返回旧单Subject字段。
- Preview后撤销Evidence时Checklist写入返回409；恢复当前事实后两项分别写入PASS，工作流版本从v7推进至
  v9，两个不可变Record均保存真实ReviewRound Basis。
- 两项资格重验后从REQUIREMENT推进PROTOTYPE，工作流到v10；同幂等Key重放结果一致，Checklist及
  Transition审计数量精确。
- Windows 11 / PostgreSQL 18.6 `upgrade head`与两次`alembic check`均无漂移；临时数据库在成功和失败
  路径均强制删除。验证脚本`py_compile`通过。

## 兼容、偏差与回滚

- 本项无正式代码、Schema/Migration、API、依赖、权限、Secret、客户数据或外发变化，只增加可重复的
  合成数据验证脚本；删除该验证目录和本记录即可回滚，不影响产品历史。
- 验证使用Windows 11本机；Windows Server 2025尚未执行本轮闭环，Debian 13按用户指令跳过。A06前端、
  A07 Edge、Gate 3其他质量/信任/性能阻塞、UAT和发行仍未完成。
