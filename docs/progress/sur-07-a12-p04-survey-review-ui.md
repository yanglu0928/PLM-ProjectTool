# SUR-07-A12-P04：SRV-02 Review 列表/详情支持

- 日期/版本：2026-10-25 / `0.1.0-dev.0`。
- 状态：`SUR_07_A12_P04_REVIEW_UI_PASS`；前端测试、类型检查和生产构建通过，尚未完成新包内浏览器验收。
- TraceLink：冻结通用 Review `GET/DECIDE`、`SRV-02 + SURVEY_ALL_V1` Owner → P02 Survey 送审包内证据 → P03 Review UI 前置核查 → 本项。

## 变更

- `ProjectReviewClient` 精确接受 `SRV-02 + SURVEY_ALL_V1`；仍拒绝跨类型/策略组合。
- Review 待办/历史将 SRV-02 显示为“调研问题版本”；详情显示正确调研主题，回链和活动轮入口均以 Survey ID + 当前轮固定 `subject_version_ref` 组成 `fixedVersionId` 深链，不回退到最新版本或结构化专项。
- Survey 详情根据 `fixedVersionId` 直接读取该固定版本，保留既有授权检查；不以版本列表顺序推断 Review 固定对象。
- Reviewer 决定继续使用现有通用安全面板：仅本人 PENDING assignment 可操作、批准需显式确认、退回需填写理由、结果未知保留同一决定/意见/操作号。没有新 API、角色、Schema、Migration、依赖或权限放宽。

## 验证与限制

- Review API Client、Review 详情、Review 列表、Survey 固定详情定向 29 项通过；前端全量 192 个测试文件、2,045 项通过；TypeScript/Vue 类型检查通过；Vite 402 modules 生产构建通过。
- 构建保留既有 500 KB chunk warning（入口 chunk 约 1,041 KB）；不是本项失败，但后续可独立治理。
- 新 `dist` 尚无候选包 Edge/HTTPS/PG18 运行证据；P05 从干净提交构建非发行候选，使用隔离数据库与合成 Reviewer 验证送审后的列表、SRV-02 Review 详情、固定 SurveyVersion 深链及评审权限。不得把合成决定称为真实客户决定。
- Server 2025/Debian 13、正式信任、真实客户决定、UAT、Gate/Pilot/正式 Release 均未通过。
