# WFL-01-A07-P01：Checklist Record 写入前置核查

2026-10-02 / Phase 2 / `PRECONDITION_BLOCKED`；本项是编码前检查，未实现或开放 `WORKFLOW_CHECKLIST_RECORD`。输入基线为 Gate 2 API-02 的 PASS/FAIL/WAIVED 请求、固定十二项六阶段定义、CR-WFL-004 记录形状与 0030/历史 Schema、已接通的 Workflow START。

发现：现有 `ChecklistRecordSnapshot` 仅验证结构，`CurrentChecklistRecordRepository` 仅读取既有记录并提示“observations still need Owner reproof”。Evidence 已有真实受控记录与资格服务，但 Workflow 尚无经授权的固定 Evidence Owner 复验接口；Review 只有内部创建/轮次/状态 Port，未有可依赖的全部正式 Subject Owner 实现；更没有 `APPROVED_EXCEPTION` 当前 Owner 来源。故仅凭 UUID、客户端 PASS/WAIVED 或 AI 推断无法满足 `EVIDENCE_FIXED_PROJECT_V1`/`REVIEW_*_V1`。开放全量记录接口或仅写一条 PASS/WAIVED 都会虚造 Gate 依据。

可选方案：①绕过 Owner/人工确认直接记录——拒绝，违反冻结安全/业务规则；②仅写 FAIL 子集并对 PASS/WAIVED 失败关闭——可作为单独内部范围，但不是完整冻结 API，不宜冒称 A07 完成；③保持公开写入口关闭，先补可验证 Evidence/Review/Exception Owner 合同与真实业务主体，再做全量受权记录/原子 Audit/幂等/HTTP——选③。无新代码、Schema 或迁移；不改原冻结内容。Rollback：仅删除本前置核查记录不会产生业务数据，但历史决策应保留。

影响/风险/验证计划：A07 完整写命令、Stage Gate/Transition 无法关闭；Workflow 启动及只读仍可继续。后续须由 Owner 在同一受权事务复验 ProjectId、固定版本、状态、来源、当前权限、证据完整性；Review/例外须有真实人工决定，失败关闭并覆盖跨项目、撤权、过期、并发、Audit 回滚和重放测试。当前证据为对相应应用/基础设施文件与冻结 API/六阶段定义的只读核对，未运行写入测试，不标 PASS。转向独立的 Workflow 前端只读/启动能力。
