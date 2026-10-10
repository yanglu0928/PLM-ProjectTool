# CR-SOL-012：SolutionSection 身份 CREATE Owner 安全解锁

日期：2026-10-09；状态：`CREATE_OWNER_HTTP_WINDOWS_SYNTHETIC_VERIFIED`。依据 CR-EXEC-001 持续授权自主实施；Gate 2 冻结提交 `64cdf09` 保留不追写。TraceLink：API-04/DM-05/SC-01 → CR-SOL-001/002、SOL-03-A01 → SOL-04-A01 → 本 CR → SOL-04-A02～A06。0147 闭锁存储与 0148 内部 Owner/Guard、可选 HTTP 和 Windows 显式写模式已在 Win11 隔离 PG/合成信任源验证；正式目标账户/生产启动、只读、前端、Server2025、性能与发行仍未验。

## 冲突与选择

冻结 API-04 的 `SOL_SECTION_CREATE` 要求项目负责人或实施成员建立当前 Outline 下的逻辑章节，返回 201/ETag；DM-05 的 `SolutionSection` 身份含稳定 `section_key`，且同一 Outline 内唯一。0136 已建表但整表 DML Guard 拒写；0146 只开放 Outline 根/结果初态 INSERT，Section 仍关闭。若直接移除 Guard，Section UPDATE/DELETE、未知 Version/Review 路径也会裸露；若仅开放 Section INSERT 且幂等收据只存根 ID，将来 key/状态变更后重放会返回可变结果，丢失首次 201。不能以 Outline 创建或空 OutlineVersion 代替章节身份。

选择独立 Section 首次结果快照表及 INSERT-only Guard：首版命令只接受归属 Outline 与 `section_key`，服务器固定初态 `ACTIVE`、批准指针 NULL、锁版本 0，并规范化/校验 key。先迁移增加快照结构但保持关闭；随后 Owner/Guard 同一交付单元开放有效初态 INSERT，要求事务结束时匹配不可变快照。Section UPDATE/DELETE/TRUNCATE、Version DML 保持拒绝。内部 Owner 用真实 Session/CSRF、License、`SOL_SECTION_CREATE` 项目角色、同项目且活动 Outline、持久 Receipt、Audit 同事务提交；重放仍复验当前授权，从快照还原原 201。

不采用可由同库角色设置的自定义事务信号作为授权证明。Guard 仅约束操作形态与首次结果闭合，不声称防范已持有应用 DB 凭据的恶意连接；正式服务账户最小权限另在 Release Gate 验证。

## 差异与风险

仅补冻结 SOL-04 身份写能力，不修改 `/api/v1` 路径、角色、Scope、AI 或业务批准规则。`section_key` 为 1..128、非控制字符、NFKC+trim 后固定；同 Outline 重复 key 须按合同冲突处理，跨 Outline 可同 key。Section 身份不是正文、SectionVersion、Review 或客户确认；创建不能自动满足 OutlineVersion/方案覆盖。若已归档 Outline、已归档项目、暂停成员或 License 不可用，必须失败关闭。目录当前尚无 PATCH/ARCHIVE Owner，但不得据此省略最终状态锁检查。

## 迁移、回滚与验证计划

1. `SOL-04-A02`：在 0146 后新增线性 Alembic migration 与 ORM 首次结果表，含同项目/根复合 FK、唯一 ID、不可变规则和历史拒降；此步仍保持 Section INSERT 关闭。验证空库及有 Project/Outline 的库升级、drift、空历史降级重升、已有快照拒降。
2. `SOL-04-A03`：新增授权 Owner、Project operation 策略及最小 Guard 解锁；事务结束的延迟闭合必须保证每个已提交 Section 根有对应首次结果。验证 PM/实施成员、跨项目/归档/暂停/License、同 Key 并发与不同载荷冲突、审计/收据失败回滚、直接 SQL 无快照提交失败、UPDATE/DELETE/TRUNCATE/Version 继续拒绝。
3. 后续独立任务：可选 HTTP 合同、Windows 显式组合、前端和 Edge/隔离 PG；正式目标账户、Server2025、20 并发、Gate3/UAT/发行各自验收。

若 A03 失败，维持/恢复关闭的 Guard 和不挂载路由；历史不删除。空历史才允许降回旧迁移，已有 Section/快照时拒降，改用向前修复迁移。所有验证使用一次性隔离数据库，不操作生产数据。
