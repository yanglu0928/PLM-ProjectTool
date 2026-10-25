# SUR-07-A12-P03：Survey Review UI 编码前核查

- 日期/版本：2026-10-25 / `0.1.0-dev.0`。
- 状态：`SUR_07_A12_P03_REVIEW_UI_PRECHECK_PASS`；只读核查，未修改产品。
- TraceLink：冻结通用 Project Review API 与 `SRV-02 + SURVEY_ALL_V1` Owner → SUR-07-A12-P02 合成送审包内证据 → 本项。

## 结论

- 后端已有真实 `SurveyReviewSubjectOwner`，在 Windows 生产组合注册；冻结通用 `/api/v1/projects/{project_id}/reviews/{review_id}` 读取与通用 `:decide` 写入可由 Review Subject Registry 路由至 SRV-02 Owner，不需要新增 Survey 专用 API。Owner 在送审和终态重新验证固定快照，并事务性收敛 SurveyVersion/Review 状态与正式批准指针。
- 前端 `ProjectReviewClient` 的精确 Subject/Policy allowlist 当前只接受 SOL-06/SOL-05/SOL-03/HND-02，没有 `SRV-02 + SURVEY_ALL_V1`。因此虽可从送审成功回执打开通用 Review 路由，客户端会拒绝合法 SRV-02 详情。
- Review 详情页面对未知主题显示为“结构化专项”，固定版本链接也退回到结构化专项路由；它没有 SurveyVersion 固定版本详情入口。通用待办/历史客户端也未发现 SRV-02 映射。
- 通用决定 UI 已具备登录权限、当前待分配 Reviewer 检查、APPROVE 显式确认、RETURN 必填意见、幂等号持久化与未知结果同号重试；但当前 `ProjectReviewClient` 的 Subject allowlist 阻断 SRV-02 在该 UI 使用。不可自动提交决定，不可把合成验收标成客户决定。

## 编码前结论

- 允许后续单一范围实现：在冻结通用 Review 客户端/列表中识别 `SRV-02 + SURVEY_ALL_V1`；详情页给出正确 Survey 主题标签，并以 `subject_ref.resource_id` 和活动轮 `subject_version_ref` 精确链接固定 SurveyVersion；决策操作沿用既有通用 Review 安全流程，不新增 API/Schema/Migration/角色。
- 验收应包含未知/错配 Subject 拒绝、固定版本深链、被分配 Reviewer 与非 Reviewer 页面行为、显式 APPROVE/必填 RETURN、同操作号未知结果恢复及 Review/Audit/SRV-02 Owner 状态一致性。真实包验收仅使用隔离数据库与合成用户；不宣称客户事实或客户签署。
- Next：`SUR-07-A12-P04`，实现 SRV-02 的通用 Review 列表/详情主题识别和精确固定 SurveyVersion 链接；保持既有决定安全交互。完成后做独立测试，再进入新 Windows 11 候选包验证。Pilot/Gate/Release 仍未通过。
