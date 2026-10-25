# SUR-07-A12-P05：Survey Review 固定包验收

- 日期/版本：2026-10-25 / `0.1.0-dev.0`。
- 状态：`IN_PROGRESS`；编码前检查已完成，正在准备新候选和 Windows 11 包内浏览器/数据库验收。
- TraceLink：冻结通用 Review GET/DECIDE 与 `SRV-02 + SURVEY_ALL_V1` Owner → A12-P02 送审包内链 → A12-P03 前置核查 → A12-P04 Review UI → 本项。

## 编码前检查与范围

- 新前端候选必须来自 P04 提交及其之后的干净提交；不复用 P02 固定包作为 P04 UI 证据。
- 在 Windows 11 上从候选独立解包；以包内 Python/FastAPI、PostgreSQL 18、Caddy/HTTPS 和真实 Edge 实测同一纵向链：Survey DRAFT Validate→ProjectManager 显式送审→IN_REVIEW；继而由同一 ProjectManager（非受指派 Reviewer）打开 Review 详情及全部历史列表。
- 验证详情标记为“调研问题评审”、列表为“调研问题版本”、链接包含同一 Survey ID 和当前轮精确固定 SurveyVersion ID；非 Reviewer 看得到状态但看不到“批准本轮/退回修改”按钮。不得让合成 ProjectManager 代替客户做决定。
- 独立 PG 查询断言 Review/Round、Reviewer PENDING、Audit/收据及零决定/批准指针 NULL；沿用既有审计与 License 拒绝、候选不变、临时资源/Vault 清理。
- 仅修改合成验收脚本，无产品 API/Schema/权限变化。完成后记录候选 SHA、运行证据和所有失败重试，并同步 GitHub。
