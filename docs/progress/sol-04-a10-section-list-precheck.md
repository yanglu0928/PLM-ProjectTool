# SOL-04-A10：SolutionSection LIST 前置核查

日期：2026-10-09。结果：`SOL_04_A10_SECTION_LIST_PRECHECK_PASS`，仅静态前置核查与施工拆分；LIST Owner、cursor、HTTP、Windows 组合均未实现，未运行新测试。

## 输入与证据

- Phase/WBS：Phase 2 Platform Core / SOL-04-A10。输入为 Gate 2 冻结 API-04 `SOL_SECTION_LIST`、DM-05/0136 Section 表、0148 初态 Owner、A07～A09 GET 只读链与现有 Outline LIST keyset/cursor/Windows Vault 模式。
- 冻结路径为 `GET /api/v1/projects/{project_id}/solution-sections`、当前 Project member、Section page；不能把 Outline LIST 的家族、游标密钥或 ProjectId 之外 Scope 直接继承。
- `sol_sections` 已有 ProjectId、OutlineId、SectionId、key、状态、批准指针、锁版本与 `ix_sol_sections__outline_state`；跨 Outline 的项目全量页可用 SectionId UUID keyset，但现有索引是 Outline/状态/SectionId，项目过滤分页的性能尚无索引/20 并发证据。不得声明性能已达标。
- `SOL_SECTION_GET` 当前项目成员策略已装；`SOL_SECTION_LIST` 尚未列入授权矩阵。无 Section LIST Owner/仓储、独立 HMAC cursor/Vault key、HTTP 或平台组合。GET 详情已有批准指针失败关闭逻辑，LIST 每项亦须复验。

## 决定的施工顺序与验收

1. `SOL-04-A11` 先实现内部 LIST Owner/仓储：独立 Project member 策略，当前 Session/License/成员复验，SectionId UUID 升序 keyset、`limit+1`，每项固定最小摘要及批准指针复验；跨项目/暂停/归档/异常和真实 PG 三页验证。不接受未经签名的 HTTP `after_id`。
2. `SOL-04-A12` 实现 Section 专用签名 cursor，绑定家族、ProjectId、Session 摘要、page size 与最后 SectionId；与 Outline/Reference cursor 不可互换。临时合成 key 只用于验证。
3. `SOL-04-A13` Windows 当前账户 Vault 独立 `project-section-list-cursor-v1` key ref/备份恢复；缺 key fail closed，不自动生成正式 key。目标服务账户另验。
4. `SOL-04-A14` 可选 GET LIST HTTP，严格查询参数和固定投影、Trace/no-store，默认 404；隔离 ASGI/PG 验证。`SOL-04-A15` 再接 Windows 显式读/写模式，登录专用仍 404，读模式 Section POST 仍 404。
5. 如真实三页/20 并发证据表明项目全量页扫描不合格，先登记索引增量与迁移/回滚/空有数据验证，再优化；不得静默改冻结 Schema 或报性能 PASS。若需要新增业务过滤字段，也先对照冻结 API 合同并登记差异。

本核查不改程序、Schema、Migration、公开 API、依赖或权限；仅确定后续 WBS 顺序，无新 Change Request。静态对账不代替运行测试。SectionVersion/Review/Trace、UI/浏览器、正式目标账户/License、Server2025、性能、Gate3/UAT/发行未验；Debian13 实机依用户指令暂跳过。
