# CAP-01-A05-A01：Capability 冻结 HTTP 与生产组合前置核查

日期：2026-10-05。结论：`CAP_01_A05_A01_HTTP_PRECHECK_PASS`。下一项：`CAP-01-A05-A02` 当前受权读取Owner与游标。

## 编码前检查

```text
当前Phase：Phase 2保持IN_PROGRESS；Gate 3保持BLOCKED
当前WBS：CAP-01-A05-A01
输入基线：冻结API-01公共协议、API-04十二个Capability Operation、DM-05、Schema0094、CR-CAP-001/CR-RVW-003
前置任务：Baseline/Draft/Validate内部Owner与Capability GLOBAL Review正式化链已通过
涉及模块：capability application/infrastructure/api；platform Windows组合
涉及实体：CapabilityBaseline、BaselineVersion、CapabilityItem、ReviewRef/RoundRef
涉及API：十二个冻结`/api/v1/global/capability-baselines...` Operation
涉及权限：DeploymentAdmin管理；当前受权项目成员仅看正式GLOBAL能力；Draft/受限版本不向普通项目成员暴露
验收标准：逐Operation映射现有能力、差距、实施顺序、迁移/Secret/回滚和验证边界
风险：一次挂载半成品API、GLOBAL读取泄漏Draft、重复实现Review、游标密钥复用、命令无持久幂等
```

## 核查结论

冻结十二个Operation当前均未挂HTTP。已存在可复用的内部Owner只有`CAP_BASELINE_CREATE`、`CAP_VERSION_CREATE`、`CAP_VERSION_VALIDATE`以及Review GLOBAL持久内核/Capability Subject；后三者仍没有统一的Session/CSRF/License/持久幂等外层。Baseline/Version/Item没有当前受权列表/详情投影和独立签名游标；Baseline PATCH/ARCHIVE、Version RESTRICT没有状态Owner或数据库守卫。默认应用及Windows显式组合均未注册Capability Router。

读取政策按冻结GLOBAL边界收敛：DeploymentAdmin可读受控全历史；当前启用且属于至少一个ACTIVE Project的成员仅能读取ACTIVE Baseline的当前APPROVED Version及其Items，不能发现Draft、RETURNED、SUPERSEDED或RESTRICTED历史。管理员查看历史不等于项目可正式引用；后续Trace/Handover Owner仍须验证精确APPROVED Version。分页使用Capability独立HMAC游标，不复用Project/Document/AI密钥。

## 实施分解

1. `A05-A02`：实现当前身份读取授权、Baseline/Version/Item安全投影及两个独立游标；无HTTP。
2. `A05-A03`：为Baseline PATCH/ARCHIVE与Version RESTRICT登记并实施最小Schema0095状态/元数据守卫及内部Owner；历史拒降。
3. `A05-A04`：把Baseline/Version Create、Validate和A03三个命令接成统一Session/CSRF/License/ETag/持久幂等HTTP；默认关闭。
4. `A05-A05`：单独实现`CAP_VERSION_SUBMIT_REVIEW`外层命令，把认证、License、收据与现有GLOBAL Review/Capability Subject装入同一UOW；不得再写第二套Review状态机。
5. `A05-A06`：实现五个冻结读取Router、强ETag和安全分页；项目成员路径只返回正式投影。
6. `A05-A07`：Windows显式生产组合接线，并在隔离PostgreSQL 18.6以真实HTTP覆盖十二Operation、角色/Scope/重放/并发/Audit/回滚；默认应用继续404。

前端工作与Server2025/发行包保持后续独立WBS。本分解不新增冻结Operation、URL或字段，不把内部Owner通过等同于HTTP可用。

## 验证、兼容与边界

本项为静态核查：交叉检查API-04十二Operation、Capability全部源码、Schema0094、现有Router/生产组合模式和游标密钥隔离规则；未运行新增程序测试。标记`CAP_01_A05_A01_HTTP_PRECHECK_PASS`。

无代码、Schema、Migration、依赖、配置、网络、Secret或客户数据变化。后续Router均保持显式注入且默认关闭，可通过不装配关闭新流量；数据库状态Owner的迁移/回滚在A03独立验证。正式信任锚、目标账户游标密钥、性能、Server2025当前链和Gate3仍未完成。
