# SUR-07-A12-P05：Survey Review 固定包验收

- 日期/版本：2026-10-25 / `0.1.0-dev.0`。
- 状态：`SUR_07_A12_P05_PACKAGED_REVIEW_UI_PASS`；首次候选确实被 Owner 读取/组合装配缺口阻断，CR-SUR-014/P06 修复后重建并通过包内 Edge/HTTPS/隔离 PG18 验收。候选仍是非发行内部验证包，不产生客户决定。
- TraceLink：冻结通用 Review GET/DECIDE 与 `SRV-02 + SURVEY_ALL_V1` Owner → A12-P02 送审包内链 → A12-P03 前置核查 → A12-P04 Review UI → 本项。

## 编码前检查与范围

- 新前端候选必须来自 P04 提交及其之后的干净提交；不复用 P02 固定包作为 P04 UI 证据。
- 在 Windows 11 上从候选独立解包；以包内 Python/FastAPI、PostgreSQL 18、Caddy/HTTPS 和真实 Edge 实测同一纵向链：Survey DRAFT Validate→ProjectManager 显式送审→IN_REVIEW；隔离数据库解析准确的受指派合成客户 Reviewer，再由该用户打开 Review 详情和待办列表。
- 验证详情标记为“调研问题评审”、列表为“调研问题版本”、链接包含同一 Survey ID 和当前轮精确固定 SurveyVersion ID；ProjectManager 可读取当前项目 Review 摘要但看不到“批准本轮/退回修改”按钮；受指派 Reviewer 看得到两个决定按钮但脚本不点击、不提交决定。项目外/非成员访问仍须拒绝。
- 独立 PG 查询断言 Review/Round、Reviewer PENDING、Audit/收据及零决定/批准指针 NULL；沿用既有审计与 License 拒绝、候选不变、临时资源/Vault 清理。
- 仅修改合成验收脚本，无产品 API/Schema/权限变化。完成后记录候选 SHA、运行证据和所有失败重试，并同步 GitHub。

## 验收结果与偏差记录

- 首轮包内 Edge 在 ProjectManager 账号打开 Review 详情时收到 404，但 Owner 实现缺口意味着当次不能据此推断预期权限。
- 依据 Handover/Review 的既有读权限模型，当前有效项目成员可读本项目 Review 摘要/固定版本，决定权限独立限定于受指派 Reviewer。验收现同时核对：送审 ProjectManager 可读状态且看不到决定按钮；数据库确认的受指派合成客户 Reviewer 可读待办/详情、固定 SurveyVersion 深链和按钮。任一身份均不提交决定。
- 第二轮完整回归进入 P05 后，实际合成 Reviewer 的 Review GET 仍 404。源码核查确认 Survey Owner 缺 `authorize_read`，且 PROJECT Review GET/List 注册表未包含 Survey Owner；因此未达到 P05 通过条件。已建立 `CR-SUR-014` 和 P06，不将此 404 误判成权限正确拒绝。
- P06 代码包第一次复验确认 Owner 修复后 Reviewer GET 200，但旧的 UI 动作文案断言不匹配 Survey 专属详情的“返回本轮固定调研版本”导航；第二次把接口 404 假设用于 ProjectManager 也失败，200 符合所有项目成员可读的权限合同。两者均为夹具/断言错误，现改为实测 ProjectManager 详情无决定按钮，再转 Reviewer 验列表/详情/决定按钮可见性。
- 最终使用候选 SHA-256 `050f37207985e5f407ac713373b2713bc24cafe67a3a36a8b5adc4e786aecfce`（654,939,043 bytes，22,197 payload items），源提交 `47e979044f90c9618d80d0c1283ee93e024057f2`；wheel SHA `a3b9c64e77ff025c4fd3fa0fd85df3a7d95cbc5ef4a30f8af40942ae100de45c`，parent SHA `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98`，pgvector wheel SHA `fedc9800894e6da2be51358d7b7c574bf34f247ca741a5a09513622135f5964f`。候选路径：`artifacts/package-prep/windows11/current-app-sur-a12-p06-20261025/current-app-candidate-d1ac121baf8a/NOT-FOR-RELEASE-windows11-current-app.zip`。
- 清洁解包逐件校验通过；包内 Windows 11 Edge/HTTPS/PG18 合成链通过：ProjectManager 可读当前 Review 且无决定控件，指派 Reviewer 可见待办、详情、精确固定 SurveyVersion 深链及决定控件；数据库核验单个当前 Review/Round、精确 ACTIVE 指派快照、Reviewer PENDING、Audit/收据存在、决定数为0且批准指针 NULL。包内 upstream Survey Validate/送审、审计、许可拒绝与 HTTPS 也通过。无真实客户数据，无决定被提交，临时进程/数据库/布局已清理，候选哈希保持不变。
- 验收输出：`SUR_07_A12_P05_PACKAGED_EDGE_PASS`、`SUR_07_A08_PACKAGED_PG_PASS`、`SUR_07_A12_P05_PACKAGED_PG_PASS`、`SYNTHETIC_CURRENT_APP_PACKAGED_HTTPS_PASS`。最终报告中的“non-reviewer 404”是旧日志文案；实际验收断言为项目成员读取成功并验证非指派人无决定权限，已更正脚本输出。候选 `release_eligible=false`、`legal_clearance=false`，不具备发行资格；Server 2025/Debian 13 未实测。
