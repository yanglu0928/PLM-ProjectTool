# SOL-02-A01：目录身份 CREATE 前置核查

日期：2026-10-09；结果：`OUTLINE_CREATE_PRECHECK_PASS`，仅确定实现切片和冻结差异，不表示目录已可创建。

```text
当前 Phase：Phase 2；依 CR-SEQ-001 前置 Solution 独立 Owner
当前 WBS：SOL-02-A01
输入基线：V2.1 §6.10/Phase 8、冻结 DM-05/SC-01/02/API-04、CR-SOL-001/002、P10 对账
前置任务：SOL-01-A02 0136 与 A03-P01 0137 Schema 已验证；Project/Session/License/Audit/Receipt 基础存在
涉及模块：solution 身份；project 授权策略；platform Receipt；audit
涉及实体：SolutionOutline（只创建逻辑身份；不创建版本、Section、Trace 或批准指针）
涉及 API：冻结 SOL_OUTLINE_CREATE；本项不装配运行 API
涉及权限：同项目有效 ProjectManager/ImplementationMember；失效/跨项目默认拒绝
验收标准：明确 0136 写保护安全解锁、唯一初态与不可变重放快照、事务 Audit/Receipt、降级历史保护及负例
风险：关闭全表保护后提前开放 UPDATE/DELETE、重放读可变根、空目录误充正式方案、跨项目/撤权
```

当前 `sol_outlines` 具备 Project/Creator FK、名称/状态/锁版本约束和指向 0137 版本的复合批准指针；但 `guard_solution_identity_foundation()` 对 INSERT/UPDATE/DELETE 全拒，`SOL_OUTLINE_CREATE` 未有 Owner、项目授权策略或公开路由。已存在的 Prototype 身份 Owner 提供同事务 Session/CSRF、License、项目授权、持久幂等、Audit 和不可变初次结果的施工先例，不能直接复制其 255 字符上限覆盖 Solution 现有 500 字符 Schema。当前没有事实表能证明一个目录被正式审批；初态必须是 ACTIVE、无 ApprovedVersion、锁版本 0。

需先建 `CR-SOL-011`：仅为 SOL-02 CREATE 按表/操作拆开 0136 全表 DML Guard，禁止未装配的 UPDATE/DELETE 和 Section 写；新增最小 CREATE 结果快照持久层以防重复 Key 读取已修改/归档根，并保持 TRUNCATE 拒绝。事务自定义信号不足以证明授权，实施前已按 DEC-20261009-1123 排除；数据库拥有 INSERT 权限的连接仍可直接写合规初态，授权必须由 Owner 与目标账户权限共同承担。此为冻结 Schema 施工细化，不追写 Gate 2 原提交。A02 完成 Migration/ORM 与空、有数据升级/降级/历史拒降；A03 再做内部受权 Owner/PG/Audit/Receipt；A04 公开可选 HTTP；A05 Windows 显式组合；前端/浏览器独立。任一切片未通过不得宣称 SOL-02 完成。

本项静态检查了 0136/0137、Solution ORM、Project 策略注册表、Prototype 身份 Owner、0144 Reference INSERT-only 迁移与冻结 API-04；未运行新测试。无程序、Schema、API、权限或数据迁移；撤销本次排期即可回退，已记录证据保留。未完成的 SOL-01 Revise/Eligibility/现时资格、正式客户确认、POC-03 质量、生产信任源、20 并发和 Gate 3 不受本项通过影响。TraceLink：P10 → 本 A01 → CR-SOL-011 → A02。
