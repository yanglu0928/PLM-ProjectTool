# SUR-06-A07 Windows 11 Edge 全链验收

本夹具复用 SUR-04-A06 的真实 APPROVED SurveyConclusion/Review 与 SUR-06-A05 的真实 Survey
qualification Owner，在隔离 PostgreSQL 18.6 库中初始化 NOT_STARTED Workflow。真实 Edge 经构建后 Vue
和生产 FastAPI 顺序完成 START、Handover 两项 PASS、`HANDOVER → SURVEY`、Survey 两项 PASS、
`SURVEY → REQUIREMENT`，并独立刷新确认每个版本。

旧 Survey 夹具不包含完整 HND-02 正式评审链，因此本组合验收仅为 Handover 两项注入固定合成资格代理；
Handover Owner 本身的真实性由 HND-03-A04、WFL-01-A07-P07-A10 和 WFL-02-A02-A07 既有证据承担。
本项不把代理描述成 Handover 业务复验；它验证两套已验收链在同一浏览器会话中的顺序组合、前端阶段选择、
生产 Workflow 写服务、审计、幂等回执和最终持久状态。无外网调用，数据库、凭据、临时目录及 Edge profile
均在结束时清理；截图写入 Git 忽略的 `artifacts/sur-06-a07-workflow-edge/`。
