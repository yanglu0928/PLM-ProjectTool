# CR-SOL-025：Section 客户终态内部证据重证的角色边界

日期：2026-10-23。状态：`APPROVED_FOR_IMPLEMENTATION`（依 CR-EXEC-001 的持续授权）；原冻结 Gate 2 版本及 CR-SOL-024 保留，未追写。

## 冲突与差异

CR-SOL-024 要求指定客户确认人作独立 Review 决定，APPROVED 前同事务重证 Section 固定六维。现有 Section `VALIDATE`/送审来源图在 Evidence 内部证明上仅允许 PROJECT_MANAGER/IMPLEMENTATION_MEMBER；真实 Windows 11/PG18.6 合成客户确认人送审后重证得到 `evidence=UNAVAILABLE`，终态 404。若复用实施方 Session 代证，违反决定者本人权限和同事务时效；若直接跳过 Evidence，违反六维门。

## 选择、风险与实施界限

终态 Review Owner 专用的内部只读来源图可接受当前同项目客户角色。仅在 Review 已认证、分配确认人、同项目和精确 IN_REVIEW 锁通过时执行；证据服务仍逐次检查当前 Session/项目成员/证据状态及固定 Document 来源，结果仅作 PASS/UNAVAILABLE，不对该客户开放证据正文、证据管理入口或新的 `/api/v1` 权限。原 VALIDATE/送审来源图维持实施方角色。旧证据、旧 Audit、旧收据不得代替当前证明。

风险：客户角色对内部证据资格的读取范围增加；以独立来源图和不返回证据正文限制暴露。若实际业务要求客户不得触及某来源，则应改为经用户/客户明确配置的可见范围或双人复核，不能静默放行。

迁移/回滚：无 DB Schema、API 合同、License 权益变化；可停用 Section 终态 Review 注册并恢复旧内部来源图，但不删除已形成的 Review/决定历史。验证：Win11/一次性 PG 以合成客户 Session 覆盖批准/退回、失效来源拒绝、项目隔离及 Audit/幂等；定向与后端全量回归。Gate/Pilot 仍按客观证据判定。
