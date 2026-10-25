# SOL-03-A06-P03-A05-P03-A02：Outline 版本验证服务

日期：2026-10-24。状态：`INTERNAL_PG_PASS`。本片建立正式内部命令服务，不挂载公开HTTP。

## 编码前检查

| 项目 | 结论 |
|---|---|
| 当前 Phase/WBS | Phase 2 / SOL-03-A06-P03-A05-P03-A02 |
| 输入基线 | Gate 2冻结 API-04 SOL_OUTLINE_VERSION_VALIDATE（order/source/coverage）、DM-05；已验 Section VALIDATE 同事务 Audit/收据模式；A05-P03-A01 现时三维可选证明 |
| 前置 | Outline历史读仓储与项目授权、Runtime License、通用Audit/幂等收据存在；公开 VALIDATE 缺服务/政策/Audit读回 |
| 涉及模块/实体 | solution Outline/Version、project policy、AuditEvent、通用Receipt |
| 涉及API/权限 | 冻结 Operation ID 不变；新增 `SOL_OUTLINE_VERSION_VALIDATE` 内部项目操作，限 ProjectManager/ImplementationMember；当前Session+CSRF+License，归档项目拒写 |
| 验收标准 | 同事务授权、固定版本读取和三维现时观察；首次结果Audit/Receipt原子提交；相同Key回放原观察且不重证；异Key重证当前事实；跨项目/无权限/License/审计失败均失败关闭；无公开路由 |
| 风险 | 历史Audit只记三维状态，不存正文；回放不能把旧PASS当当前资格。服务必须在首次观察前查批准指针一致性，但不隐式批准Outline/Section或关闭Gate |

无Schema变更或数据迁移；若服务不合格则不挂载路由，已有Outline版本/Audit/Receipt历史保留。单元与实际Win11/PG验证分层，后者必须证明Receipt/Audit原子性和漂移后的新Key行为。

## 验证与剩余边界

- 定向服务单元8项：项目负责人和实施成员可验；客户角色、归档/错资源、License及Audit故障拒绝；首次Audit/Receipt、同Key原观察、新Key重证及UNAVAILABLE结果合同通过。
- `validation/sol-03-a06-p03-a05-p03-a02-outline-validate-pg/verify.py` 使用已有一次性Windows11/PostgreSQL18.6真实Outline/Session/Project夹具退出0：首次Audit/Receipt各1，同Key回放均仍1，异Key重证各2，跨项目/拒绝License与Audit故障均不新增；本轮临时PG由夹具清理。现时事实在此脚本中为显式合成返回值，**未**验真实 Section/Requirement/Review/Trace 三维组合。
- 现有 Alembic 操作符类/计算列比较警告仍在，夹具无新迁移操作。后端全量结果见 `STATUS.md`。公开HTTP路由、Windows真实三维端口装配及客户正式确认待后续片。
- 权限矩阵随新操作由177项增为178项；首次全量回归发现旧计数断言失败（1失败/4007通过/3跳过），修正矩阵断言及角色清单后，定向18通过/836子例，后端全量4008通过/3跳过/6084子例。
