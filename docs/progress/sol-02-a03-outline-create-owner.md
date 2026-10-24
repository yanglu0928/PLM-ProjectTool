# SOL-02-A03：目录身份受权内部创建

日期：2026-10-09；结果：`OUTLINE_CREATE_OWNER_PG_PASS`，限定 Windows 11 一次性 PostgreSQL 18.6/合成身份与许可，不是公开 API、正式审批或 Gate 3 PASS。

```text
当前 Phase：Phase 2；依 CR-SEQ-001 前置 Solution 真实 Owner
当前 WBS：SOL-02-A03
输入基线：冻结 API-04/DM-05/SC-01/02、CR-SOL-011、0145、DEC-1123/1124
前置任务：A02 关闭的首次结果快照 Schema/ORM 已验证
涉及模块：solution 内部应用/仓储、Project 操作策略、Alembic；复用 Auth/License/Audit/Receipt
涉及实体：SolutionOutline、SolutionOutlineCreateResult、AuditEvent、IdempotencyReceipt
涉及 API：无新公开装配；SOL_OUTLINE_CREATE 仍待 A04
涉及权限：当前 Session+CSRF、有效 License、同项目 PM/ImplementationMember；其他角色/跨项目拒绝
验收标准：原子创建/首次 201 快照、同 Key 并发重放、不同载荷冲突、Audit 回滚、非法 SQL/历史拒降
风险：无快照根、根后续修改影响首次响应、未受权客户写入、误把空目录当正式版本
```

Changed：新增 `OutlineCreateService`、独立 SQLAlchemy 仓储、`SOL_OUTLINE_CREATE` 项目操作策略及 0146 Guard/延迟闭合；根初态 ACTIVE/批准指针 NULL/ETag v0，Audit/Receipt 与根/首次结果同事务。规范名称按 NFKC、去首尾空白、1..500 字符，未沿用其他模块 255 上限；首次响应由不可变快照重放，即使隔离测试模拟后续根改名也返回原值。Reference/Section/Version/Review/Trace 不因此自动产生正式事实。

Migration：0145→0146 有既有 Auth/Project/Reference 数据升级、无目录时降级重升与 Alembic drift 通过；目录有历史时拒降。API：无运行路由，默认/Windows 现有公开组合不变。Tests：定向单元 8/8 子例；隔离 PG 真实 Session/CSRF、PM/实施成员、客户角色/跨项目/许可拒绝、同 Key 并发、不同载荷冲突、Audit 失败回滚、无快照根/非法状态/未开放操作拒绝与历史拒降退出 0。A02 历史关闭态脚本复跑退出 0；后端全量 `3360 passed, 3 skipped, 5003 subtests passed`。首轮全量唯一失败是新增项目操作未进入静态矩阵计数，补齐后重跑通过。

限制：合成 License 与测试身份不是正式目标账户；只测两个并发同 Key，不是 20 并发性能。公开 HTTP/Windows 组合、UI、正式 Review/Trace/Workflow、Server2025、POC-03 质量、Gate3/UAT/发行仍待；Debian13 当前实机依用户指令暂跳过。无客户数据/秘密外发。回滚仅适用于空历史；非空时关闭 Owner/公开路由并做前向修复，不删已创建目录。

TraceLink：A01/CR-SOL-011 → A02/0145 → DEC-1124/0146 → 本 A03 → A04。
