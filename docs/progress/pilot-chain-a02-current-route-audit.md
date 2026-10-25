# PILOT-CHAIN-A02：当前 Prototype→Solution→Plan→Output 关键路径复核

日期/版本：2026-10-25 / `0.1.0-dev.0`。结论：`PILOT_CHAIN_ROUTE_AUDIT_COMPLETE / PILOT_NOT_READY`；仅静态复核，不是 Pilot 验收。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `PILOT-CHAIN-A02`|
|输入基线|用户批准 `CR-EXEC-002`、冻结 DM-05/API-03/API-04、CR-PLAN-001、CR-SOL-003、`STATUS.md` 与 P51-A04 当前候选验收|
|前置任务|P51-A04 当前候选 Survey Review 只读/权限链已验；Gate 3、Pilot 与正式 Release 仍未通过|
|涉及模块|Prototype、Solution、Plan/WBS、Output、Pilot包；只读代码/迁移/WBS/进度记录，不改产品代码|
|涉及实体/API/权限|核对 Prototype、Outline/Section/StructuredSpec、Plan/PlanVersion/WBS、OutputRequest/Artifact 与已冻结 API；无运行时权限变化|
|验收标准|以当前代码、Migration、浏览器/PG证据和未完WBS更新依赖图；找出不依赖缺失事实的最短后续项及阻塞；明确不视为客户事实/批准|
|风险|将模块或表存在误判为可用业务Owner；将 SOL-06 专项Review代替完整批准方案；将 P51合成测试结果误报Pilot|

## 当前证据与依赖

|环节|实际状态|关键未闭合依赖|
|---|---|---|
|Prototype|已有创建/修订/Review、Windows页面及部分浏览器/PG证明；仍需结合当前完整上游事实验收|批准 Requirement 与完整 Solution 固定来源及正式 Trace/输出链|
|Solution|SOL-06结构化专项已有创建/读取/修订/验证/送审链分项；SOL-03 Outline已完成统一Review送审、Edge/PG客户角色决定和Windows显式组合|真实客户批准、Section/StructuredSpec全套输入与正式信任仍未由合成数据证明|
|Plan/WBS|Plan身份HTTP/页面/真实Edge-PG已验；PlanVersion/WBS/依赖/Milestone/固定来源主要为闭锁Schema，WBS只读Trace链另行验证|`PLAN-02-A04-P04-A04-P03-P01`已记录真实PlanVersion写入前置受阻：缺Outline/Section/StructuredSpec精确固定的Approved集合与Owner；不能由Trace图推定来源批准|
|Output|冻结API-03有OutputRequest/Artifact，但当前无正式Output模块、Artifact物理/元数据Owner及可供上游引用的受权限发布/下载链|无正式安全制品输出；Prototype/Solution附件分支失败关闭，不能以临时脚本或普通文件替代|
|安装/信任|P51-A02/A03/A04当前非发行Windows候选在隔离环境的原子落地、包内PG/HTTPS与Review只读权限链通过|缺正式产品公钥/License、目标账户Vault/ACL/CA、服务安装/恢复/升级和Pilot完整UAT；Server 2025未验，Debian 13按用户指令跳过|

## 路线决定

旧 `PILOT-CHAIN-A01` 在2026-10-19基于“Plan模块不存在”选择 `PLAN-01-A01`，已被后续Plan身份Owner/HTTP/UI/Edge/WBS Schema和Trace分项取代。其后续建议 `SOL-03-A06-P01` 也已完成：Outline统一Review真实Edge/PG链于2026-10-24验收，Windows显式组合亦通过；正式操作员仪式独立阻塞记录在 `SOL-03-A06-P04-P03-A06-P02`，故不重复旧前置。

下一项改沿 `CR-EXEC-002` 的Windows当前候选纵向验收继续：建立 `PLT-PKG-01-A09-P51-A05` 前置核查，评估在固定 P51 候选内复用 Prototype 真实Edge/PG生命周期验收的方式，优先验证 Prototype入口、DRAFT版本/Validate/送审/Review读取与权限边界；不得自动作客户Review决定。当前已有源码级Prototype浏览器验证，但尚未证明该功能切片随P51候选运行，因此候选包验收有直接Pilot价值。PlanVersion完整业务Owner、Section/StructuredSpec固定Approved来源、OutputArtifact Owner仍是后续正式依赖，不因本项通过而视为解除。

P51-A04仅证明当前Windows 11非发行候选中的合成Survey Review读取和决定权限隔离：Review决定数为0、批准指针NULL。它不证明Prototype至Output链、真实业务批准、正式信任或可交付Pilot。Gate 3、Pilot和正式Release均保持NOT_READY。

本核查无功能测试、Schema/API/权限/依赖/用户数据变化；只对照既有记录及当前实现证据。回滚只需恢复STATUS中的路线指针，历史WBS审计保留。
