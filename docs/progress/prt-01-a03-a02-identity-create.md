# PRT-01-A03-A02：Prototype identity create Owner

日期：2026-10-08。结论：`PRT_01_A03_A02_IDENTITY_CREATE_PASS`。下一项：`PRT-01-A03-A03`
Package PATCH/SET_MEMBERS Owner与不可变集合结果。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core；Gate 3保持BLOCKED
当前WBS：PRT-01-A03-A02
输入基线：CR-PRT-001、Schema0122、A03-A01命令拆分、PRT_PACKAGE_CREATE/PRT_CREATE
前置任务：PRT-01-A03-A01 PASS
涉及模块：prototype application/repository、project authorization、session/csrf、license、audit、idempotency
涉及实体：PRT-01 PrototypePackage、PRT-02 Prototype、两类不可变首成功结果
涉及API：内部Owner；Router仍未装配
涉及权限：ProjectManager/ImplementationMember写，其他角色失败关闭
验收标准：输入规范化、持久重放/冲突、同事务Root+result+Audit+receipt、提交闭包、历史拒降
风险：直接Root绕过Owner；Audit失败留下半套身份；重放读取可变Root；旧Schema0122手工历史无法追认
```

## 实施结果

- 新增Package/Prototype创建命令、严格初始View、应用Service和SQLAlchemy Repository；名称做NFKC、trim、
  1～255及控制字符校验，Session/CSRF、License和Project角色每次调用重证。
- 新增`PRT_PACKAGE_CREATE`、`PRT_CREATE`授权策略；两个Operation只允许PM和ImplementationMember。
- Migration0123新增两张不可变首成功结果表和延迟Root提交闭包。Root、首结果、Audit、幂等receipt在同一
  UOW提交；重放只读首结果，不读取随后变化的Root。
- 0123拒绝自动接纳Owner关闭期间可能存在的手工Prototype身份，因为无法证明其授权/Audit/receipt；必须
  另走审计迁移。空历史可降0122，产生首结果后拒绝物理降级。

## 验证

- Windows 11/PostgreSQL 18.6：空历史升降/重升、drift、PM/实施成员、客户角色拒绝、Session/CSRF、
  License、Package/Prototype创建、持久重放/冲突、Audit失败回滚、无结果Root提交拒绝、撤权后重放拒绝、
  历史拒降：PASS。
- 新增5项单元测试；相关定向24项PASS；完整后端3094项PASS、3项既有条件跳过；compileall PASS。
- 开发wheel构建PASS，1175 entries，SHA-256
  `36935bcf54cb43f8440f4b65028a345cd92516afe374ca215cc16ab8bd25ffb9`。

本项未开放HTTP、Package修改、NOT_REQUIRED、Version/Review/Workflow或正式Prototype事实；Windows
Server 2025未执行本轮，Debian 13按用户指令跳过，Gate 3/UAT/发行仍未通过。
