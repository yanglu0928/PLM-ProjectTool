# SOL-05-A02-P08：SectionVersion CREATE 项目操作授权

日期：2026-10-09。结果：`SECTION_VERSION_CREATE_POLICY_INTERNAL_PASS`；只增加 Project-owned 操作策略，未接 SectionVersion 写 Owner/API。

## 编码前检查

Phase 2 Platform Core；WBS `SOL-05-A02-P08`。输入冻结 API-04 `SOL_SECTION_VERSION_CREATE` PM/实施成员与 CR-SOL-003/P07 的实施顺序，前置满足。涉及 Project 授权矩阵，不改 Solution 实体、Schema/Migration、公开 API、License、安全来源、用户会话或数据。验收为 PM/实施成员在活动项目可受权且锁定当前事实，客户经理/成员与非成员拒绝并隐藏，归档项目拒写。风险是把策略存在误称入口或 SectionVersion CREATE 已开放。

## 实施与验证

增加 `SOL_SECTION_VERSION_CREATE` 写操作策略，角色严格为 `PROJECT_MANAGER`、`IMPLEMENTATION_MEMBER`；沿用现有 `ProjectAuthorizationService` 对项目当前成员/归档状态的加锁校验，不赋予客户角色或扩大其他 Solution 操作。定向测试 `9 passed, 754 subtests passed`，含本操作的四角色、非成员、归档、同事务锁以及全矩阵回归；后端全量 pytest `3526 passed, 3 skipped, 5510 subtests passed`、退出0。未运行真实 PG/HTTP/浏览器本操作，因为 Owner/路由/Guard 仍未安装；不能以单元桩验证宣称真实受权写链通过。

兼容/升级/回滚：内部策略增加一个尚未调用的 OperationId；无 Schema/Migration/API/配置/依赖/数据变化，撤策略和对应测试可回滚。0138 写闭锁保持。下一项 `SOL-05-A02-P09` 新增 SectionVersion 不可变首次响应闭锁表及空/已有项目库迁移验收；P10 才计划开 INSERT-only Guard。正式 Server2025/信任、性能/质量、Gate3/发行未通过，Debian13 实机依用户指令跳过。

TraceLink：Gate2 API-04/DM-05 → CR-SOL-003 → P07/DEC-1173 → 本策略 → P09 首响应 → P10 Guard → P11 Owner → P12 HTTP → Gate3。
