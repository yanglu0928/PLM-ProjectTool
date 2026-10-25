# PRT-01-A03-A04：Prototype PATCH / ARCHIVE Owner

日期：2026-10-08。结论：`PRT_01_A03_A04_PROTOTYPE_MUTATION_PASS`。下一项：`PRT-01-A03-A05`
NOT_REQUIRED 原子范围决定 Owner。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core；Gate 3保持BLOCKED
当前WBS：PRT-01-A03-A04
输入基线：CR-PRT-001、Schema0124、A03-A01、冻结PRT_PATCH/PRT_ARCHIVE控制
前置任务：PRT-01-A03-A03 PASS
涉及模块：prototype identity application/repository、project authorization、session/license/audit/idempotency
涉及实体：PRT-02 Prototype Root、不可变command result；既有Package membership只保留不改写
涉及API：内部Owner；PATCH无I，ARCHIVE有I/M；Router仍关闭
涉及权限：PATCH为ProjectManager/ImplementationMember；ARCHIVE仅ProjectManager
验收标准：强ETag、PATCH仅改名、ARCHIVE单向终态、持久重放、Audit、历史保留与提交闭包
风险：普通PATCH开放安全状态；归档删除membership/Version；PATCH伪造receipt；Root/结果半提交
```

## 实施结果

- 新增严格Prototype PATCH/ARCHIVE命令、Service和Repository。PATCH仅在ACTIVE改name、要求强版本且不接收/
  生成幂等key；RESTRICTED和NOT_REQUIRED不通过普通PATCH开放。
- ARCHIVE仅ProjectManager可执行、使用持久幂等回执并在每次重放前重证Session、CSRF、License与权限；从任一
  非ARCHIVED状态单向进入ARCHIVED，不删除Package membership、Version、Decision、Link或正式指针。
- Migration0125新增不可变Prototype command result，开放受限Root UPDATE；延迟约束在提交时闭合Root版本、
  状态、name、正式指针与结果快照。无结果的直接Root修改失败关闭，存在历史时拒绝破坏性降级。

## 验证

- Windows 11/PostgreSQL 18.6：空历史升降/重升、drift、角色/Session/CSRF/License、PATCH无receipt、旧ETag、
  无变化、ARCHIVE/重放/冲突/单向终态、Audit回滚、membership保留、直接Root提交拒绝、撤权重放拒绝及
  历史拒降：PASS。
- 定向27项PASS；完整后端3106项PASS、3项既有条件跳过；compileall PASS。
- 开发wheel构建PASS，1181 entries，SHA-256
  `dfb5fe0bbd64e61c95a81d75187ef48130ee04356243d055b3e2f93b3efe4108`。

本项未开放HTTP、NOT_REQUIRED、Version/Review/Workflow或正式业务事实；Windows Server 2025未执行本轮，
Debian 13按用户指令跳过，Gate 3/UAT/发行仍未通过。
