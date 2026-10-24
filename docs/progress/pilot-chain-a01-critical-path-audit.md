# PILOT-CHAIN-A01：Windows 11 内部试用包关键路径缺口核查

日期/版本：2026-10-19 / `0.1.0-dev.0`。结论：`PILOT_CHAIN_AUDIT_COMPLETE / PILOT_NOT_READY`；本项只读核查并排定下一独立 WBS，不是 Pilot 验收。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `PILOT-CHAIN-A01`|
|输入基线|用户批准 `CR-EXEC-002`、冻结模块边界、DM-05、SC-01/02、API-03/04、`STATUS.md` 与已验收的 SOL-06-A16-P08|
|前置任务|Gate 2 已批准；本项只读核查可在 Gate 3 开放时执行|
|涉及模块|Solution、Plan、Output、Windows 安装/信任；不改运行代码|
|涉及实体/API/权限|审查 Plan/PlanVersion/WBS、OutputRequest/Artifact 的冻结定义及实现存在性；无运行权限变更|
|验收|区分已实测、仅设计及客观阻断；选定最短纵向链下一项且不免除其他 Gate|
|风险|把 SOL-06 专项批准误当完整 Solution 批准，把合成浏览器/License/安装候选误当 Pilot|

## 静态核查结果

|环节|当前证据|Pilot 结论|
|---|---|---|
|Project→Handover→Survey→Requirement→Prototype|已有分项 Owner、API、浏览器/PG 证据，`STATUS.md` 仍列纵向完整业务链未闭合|不能从分项通过推定全链 UAT|
|Solution|SOL-06 结构化专项送审、决定、Review Inbox 的 Windows 11 Edge/PG 已验证；Outline/Section/整体范围仍需按冻结规则组合、批准与 Trace 验收|不能把单专项 APPROVE 当整套已批准 Solution 输入|
|Plan/WBS|冻结 DM-05 定义逻辑 Plan、不可变 PlanVersion、六级 WBS、FS DAG；API-04 定义 PLAN_CREATE/版本/验证/送审。仓库当前无 `modules/plan`、前端 Plan 模块或 `pln_plans`/`pln_plan_versions` Migration|真实实施 WBS 无正式 Owner/持久化/API/页面；这是下一明确业务链实现缺口|
|Output|冻结 API-03 有 OutputRequest/Artifact；当前无 `modules/output`、前端 Output 模块或 Output 表 Migration|无法形成正式可下载交付文件；不得以临时导出脚本替代 OutputService/Plugin/Document 边界|
|Windows 离线安装与信任|`PLT-PKG-01-A09-P41` 只证明非发行候选在隔离布局的安装编排/拒绝路径；P38 仍 `FORMAL_INSTALL_BLOCKED`|正式服务账户、Vault/ACL、产品公钥/License、证书/CA、SCM、备份升级和许可清单未齐；合成信任不能作为 Pilot|

## 顺序与验收边界

按 `CR-EXEC-002`，下一项选择 `PLAN-01-A01`：对冻结 Plan Identity、PlanVersion、WBS 与现有 Solution 正式输入/Review/Trace 依赖做编码前核查，产出可执行的最小分片和任何必要 CR。之后优先实现 Plan Schema/Owner/HTTP/前端/真实 PG-Edge，再推进 Output 的固定上下文/制品链；Windows 安装与正式信任可在不依赖业务 Plan 代码的 WBS 中继续独立推进。每项只解决一个明确问题，不因加速而放松批准版输入、人工确认、权限、Trace 或历史保留。

Gate 3、Pilot 和正式 Release 维持 NOT_READY：没有完整业务 UAT、正式信任和离线安装/升级证据；POC-03 质量、20 并发、Windows Server 2025/Debian 13 与发行许可仍属正式 Gate 缺口。本审查未运行功能测试，也未改 Migration/API/数据或用户文件。
