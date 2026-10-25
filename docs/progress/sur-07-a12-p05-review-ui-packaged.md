# SUR-07-A12-P05：Survey Review 固定包验收

- 日期/版本：2026-10-25 / `0.1.0-dev.0`。
- 状态：`INCOMPLETE_BLOCKED_BY_OWNER_READ_GAP`；首轮确认未受指派的送审者收到预期 404；复跑中实际受指派 Reviewer 仍收到 404，证实是后端 Owner 读取/组合装配缺口，不是前端 UI 或决定权限问题。详见 `CR-SUR-014`，由 P06 修复后重建候选。
- TraceLink：冻结通用 Review GET/DECIDE 与 `SRV-02 + SURVEY_ALL_V1` Owner → A12-P02 送审包内链 → A12-P03 前置核查 → A12-P04 Review UI → 本项。

## 编码前检查与范围

- 新前端候选必须来自 P04 提交及其之后的干净提交；不复用 P02 固定包作为 P04 UI 证据。
- 在 Windows 11 上从候选独立解包；以包内 Python/FastAPI、PostgreSQL 18、Caddy/HTTPS 和真实 Edge 实测同一纵向链：Survey DRAFT Validate→ProjectManager 显式送审→IN_REVIEW；隔离数据库解析准确的受指派合成客户 Reviewer，再由该用户打开 Review 详情和待办列表。
- 验证详情标记为“调研问题评审”、列表为“调研问题版本”、链接包含同一 Survey ID 和当前轮精确固定 SurveyVersion ID；受指派 Reviewer 看得到“批准本轮/退回修改”按钮，但脚本不点击、不提交决定。另以送审者请求 Review 详情并确认服务端 404，拒绝未受指派成员读取。
- 独立 PG 查询断言 Review/Round、Reviewer PENDING、Audit/收据及零决定/批准指针 NULL；沿用既有审计与 License 拒绝、候选不变、临时资源/Vault 清理。
- 仅修改合成验收脚本，无产品 API/Schema/权限变化。完成后记录候选 SHA、运行证据和所有失败重试，并同步 GitHub。

## 首轮验收偏差与处理

- 首轮包内 Edge 在 ProjectManager 账号打开 Review 详情时收到 404。该身份不是本轮评审者，拒绝读取合理；当时证据不足以证明 Review GET 的 Survey Owner 只允许受指派人读取。
- 原预期“送审者读取详情并看不到决定按钮”与已实现的对象级授权不兼容。依持续授权调整验收方案：保持发送者写链，独立验证其读请求 404；随后由数据库核对实际分配的合成客户 Reviewer ID，切换该账号验收详情/待办/固定版本链接及按钮可见性，并确保零决定。此为测试夹具/验收方案调整，不改权限策略、API、数据模型或客户数据。
- 第二轮完整回归进入 P05 后，实际合成 Reviewer 的 Review GET 仍 404。源码核查确认 Survey Owner 缺 `authorize_read`，且 PROJECT Review GET/List 注册表未包含 Survey Owner；因此未达到 P05 通过条件。已建立 `CR-SUR-014` 和 P06，不将此 404 误判成权限正确拒绝。
