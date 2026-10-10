# SOL-03-A04-P03-P03-P04-A03：OutlineVersion 双 Scope 固定引用 Owner 组合

日期：2026-10-09。结果：`SOL_03_A04_P03_P03_P04_A03_DUAL_SCOPE_OWNER_PG_PASS`；仅 Win11 内部 Owner/隔离 PostgreSQL 18.6 合成组合，公开 HTTP/Windows/UI 未接线。

## 编码前检查

- 当前 Phase/WBS：Phase 2 Platform Core / 本任务。输入基线：Gate2 DM-05/API-04、CR-SOL-016/017、0156 Guard、已验 OutlineVersion Owner 与双 Scope 现时证明。
- 前置：PROJECT/GLOBAL Reference 资格/固定来源、Requirement 当前批准、Section 身份、Auth/项目成员/License/收据/Audit 端口均已独立验证；本项将它们组合，不改变业务代码。
- 模块/实体/API/权限：Solution 内部验收夹具；OutlineVersion、Section、RequirementVersion、ReferenceVersion、Document/Evidence 来源；无新 API/权限/Schema/Migration。
- 验收：两套独立 Win11 PG 库以项目成员而非 GLOBAL 管理员创建 DRAFT，固定三类引用/Scope/首响/收据/Audit 一致；原键重放不增加行；跨项目、物理篡改、资格限制、GLOBAL 确认到期拒绝且失败无写。
- 风险：Requirement APPROVED 上游身份为隔离夹具的合成 Review 状态，不代替正式 Review/UAT；公开 HTTP 和生产信任源未验证。

## 实施与证据

仅新增可重复运行的验证资产，复用真实 Reference/Document/Evidence 文件与 PG 夹具。PROJECT 路径用真实 PM Session 创建 Outline/Section、真实合格 Reference 与合成已批准 Requirement，再由正式 `OutlineVersionCreateService` 同事务写 v1；重放返回同一首响，数据库逐项核对版本、Section/Requirement/Reference 顺序与 PROJECT 来源项目、首响、一次 Audit、一次收据。跨项目、已验证文件字节篡改、资格转 RESTRICTED 均拒绝，版本/引用/首响/Audit/收据总数不增。

GLOBAL 路径由独立项目 PM Session 创建目标项目及 Outline/Section，GLOBAL Reference 仍由原管理员完成脱敏确认与资格操作；项目 PM 只通过内部现时证明使用固定 GLOBAL 版本，无管理员凭据借用。正式 Owner 写入后数据库确认 GLOBAL 引用 `source_project_id=NULL`、其他关联与一次 Audit/收据一致；模拟确认到期时再创建失败且总行数不增。两套临时 PG18.6/真实文件组合、来源夹具回归与 Alembic drift 检查均退出 0。首轮验收脚本将收据列误写 `ref_id`，修正为实际 `result_ref_id` 后用全新库重跑通过；业务代码未因此修改。

兼容/回滚：无产品代码/Schema/API 变化，仅验收资产，可撤脚本但保留证据与历史；无正式数据写入。下一项 `SOL-03-A04-P03-P03-P05` 可选创建 HTTP 合同、真实 ASGI/PG、Windows 显式装配及 UI。Gate3、正式发行仍 BLOCKED。

TraceLink：Gate2 DM-05/API-04 → CR-SOL-016/017 → 0155/0156 → OutlineVersion Owner → 本双 Scope 验收 → HTTP/Windows/UI。
