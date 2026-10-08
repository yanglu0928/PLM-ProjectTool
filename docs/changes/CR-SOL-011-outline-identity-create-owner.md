# CR-SOL-011：SolutionOutline 身份 CREATE Owner 安全解锁

日期：2026-10-09；状态：`RECORDED_BEFORE_IMPLEMENTATION`。依据 CR-EXEC-001 持续授权自主实施；Gate 2 冻结提交 `64cdf09` 不追写。TraceLink：SOL-02-A01 → 本 CR → SOL-02-A02/A03。

## 来源、冲突与选择

冻结 API-04 要求 `SOL_OUTLINE_CREATE`，0136/0137 已建身份表和批准版本 FK，但 0136 的整表 DML Guard 在 Owner 未安装时有意拒写；当前 Project 授权表亦无 SOL_OUTLINE_CREATE。若直接移除 Guard，会同时开放未验的 UPDATE/DELETE/Section 写；若不改 Guard，则真实 Owner 无法创建。普通持久 Receipt 仅存结果 ID，创建后根可能改名/归档，重复 Key 若读取根会丢失首次响应，违反冻结的持久幂等语义。

不选直接关闭整表 Guard、模拟成功或使用可变根做重放；不选把目录创建捆绑 Section/Version/Review。最初考虑事务局部自定义信号，但普通自定义 GUC 可由同数据库角色设置，不能作为不可伪造授权凭据，故实施前放弃（DEC-20261009-1123）。选择与现有 0144/Prototype Owner 一致的最小增量：Guard 仅允许满足固定初态的 Outline INSERT，继续拒绝 Outline UPDATE/DELETE 与 Section 全部 DML；TRUNCATE 仍拒绝。会话、License、项目角色、Receipt 和 Audit 由内部 Owner 同事务校验。另建不可变首次创建结果表，保存根 ID、项目、规范名称与首次创建时间，Receipt 存 Operation/根 ID；重放仍须当前会话/项目授权，结果从快照返回。名称规则对齐 1..500 Schema，不隐式降为 Prototype 的 255。

## 差异、影响及安全边界

只增加 SOL-02 写入施工能力，不改变冻结外部 `/api/v1` 操作、角色、Scope、AI 或业务批准规则。Project 策略增 SOL_OUTLINE_CREATE，仅 PM/ImplementationMember 且有效 Project 可用；默认应用和 Windows 现有公开路由仍关闭，待独立 HTTP/组合 WBS 验收。CREATE 初态 ACTIVE、批准指针 NULL、锁版本 0；目录身份不是 Approved OutlineVersion，也不能满足 Solution Checklist。数据库拥有 INSERT 权限的连接可直接构造合规初态，故 Guard 只是防误写/未安装操作边界，不能宣称防恶意 SQL；目标服务账户权限与凭据保护另由 Release 验收。

## 迁移、回滚与验证计划

A02 新线性 Alembic 迁移与 ORM 同构：改 Guard 和新增快照表；空库/有 Project/User 数据库升级、drift、无历史时降级重升、存在 Outline/快照时拒降。不能删除客户历史以强行回滚；若 A02 之后 A03 失败，保留历史并关闭应用 Owner/路由，后续迁移修复。A03 验证 PM/IM 创建、其他角色/跨项目/失效/License 拒绝、同 Key 并发精确重放、不同载荷冲突、Audit 与 Receipt 原子回滚、直接 SQL 写闭锁、名称边界及元数据更新后快照不变。A04/A05 分别验证 HTTP 合同和 Windows 隔离 PG 组合；正式生产信任源、Server2025/20 并发、Gate3/UAT/发行单独验收。

剩余风险：应用数据库凭据被盗用时，INSERT-only Guard 不能替代数据库角色隔离/凭据保护；正式目标服务账户和权限收敛必须在发行门禁验收，不能把本地合成 PG 结果称为生产安全 PASS。任何测试只用一次性隔离库，不对生产数据做不可恢复操作。
