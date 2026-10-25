# PRT-01-A03-A03：PrototypePackage PATCH / SET_MEMBERS Owner

日期：2026-10-08。结论：`PRT_01_A03_A03_PACKAGE_MUTATION_PASS`。下一项：`PRT-01-A03-A04`
Prototype PATCH/ARCHIVE Owner与不可变结果。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core；Gate 3保持BLOCKED
当前WBS：PRT-01-A03-A03
输入基线：CR-PRT-001、Schema0123、A03-A01、冻结PRT_PACKAGE_PATCH/SET_MEMBERS控制
前置任务：PRT-01-A03-A02 PASS
涉及模块：prototype package application/repository、project authorization、session/license/audit/idempotency
涉及实体：PRT-01 Package、同项目PRT-02 membership、不可变command result
涉及API：内部Owner；PATCH无I、SET_MEMBERS有I/M；Router仍关闭
涉及权限：ProjectManager/ImplementationMember写
验收标准：强ETag、全量集合替换、空集合、同项目/非归档成员、重放、Audit与提交闭包
风险：把SET误作增量；删除Prototype；PATCH伪造receipt；Root/成员/结果半提交
```

## 实施结果

- 新增严格PATCH与SET_MEMBERS命令、Service和Repository。PATCH只改name、要求强版本且不接收/生成幂等
  key；未冻结的RESTRICTED状态不通过普通PATCH开放。
- SET_MEMBERS表示完整集合替换，允许空集合，最多200个唯一Prototype，规范排序后进入指纹和结果；只删除
  membership，不删除Prototype。所有成员必须同项目、存在且非ARCHIVED。
- Migration0124新增不可变Package command result，开放受限Package UPDATE及membership INSERT/DELETE；
  延迟约束在提交时闭合Root版本、实际完整成员集合和结果快照。无结果的直接成员变更失败关闭。
- 新增`PRT_PACKAGE_PATCH/SET_MEMBERS`授权策略。SET持久重放每次重证权限；PATCH无receipt且Audit失败全回滚。

## 验证

- Windows 11/PostgreSQL 18.6：空历史升降/重升、drift、角色/Session/CSRF/License、PATCH无receipt、旧ETag、
  SET全量替换/空集合/重放/冲突/无变化、Audit回滚、直接membership提交拒绝、撤权重放拒绝及历史拒降：PASS。
- 定向26项PASS；完整后端3100项PASS、3项既有条件跳过；compileall PASS。
- 开发wheel构建PASS，1178 entries，SHA-256
  `31875e1583d38765f52f2de485290fb3178c8372c9a2c27622bcd64230d5f4c5`。

本项未开放HTTP、Prototype identity修改、NOT_REQUIRED、Version/Review/Workflow或正式业务事实；Windows
Server 2025未执行本轮，Debian 13按用户指令跳过，Gate 3/UAT/发行仍未通过。
