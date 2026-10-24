# HND-02 Review GET 主题接线增量 V1

日期：2026-10-25；WBS：`HND-05-A05-P01`。来源：Gate 2 冻结 API-02
`REVIEW_GET`、Review 读取增量合同、HND-01 真实 Subject Owner 与
HND-05-A04-P03 原子送审包内证据。

既有 `GET /api/v1/projects/{project_id}/reviews/{review_id}` 路径、
`data/trace_id` 精确投影、强 ETag、错误码和 `Cache-Control: no-store` 不变。
只在 Windows 显式只读 Registry 中加入 `HND-02`；默认应用仍 404，Review 列表
不自动加入该主题。`subject_ref.resource_type=HND-02` 须与
`policy_code=HANDOVER_ALL_V1` 对应；`active_round.subject_version_ref` 是本轮固定
交接版本，响应不复制问题正文、Evidence 内容、来源路径或内部证明。

读取仍先重验 License、当前 Cookie Session 与 `REVIEW_GET` 当前项目成员；
Handover Owner 在同一事务内再重验账户/项目成员资格、ACTIVE Analysis 身份，
有活动轮时以共享锁核实精确 Version 属于同一项目与 Analysis。未知主题、
错误版本、跨项目或权限丧失均失败关闭为 404；匿名 401。读取不能修改
Review、Handover、Audit 或客户确认事实。

本增量没有新的 API 路径、请求/响应字段、Schema、Migration、License 权益或
Breaking Change。回退可停止显式注册 HND-02 只读 Owner；合法 Review/Audit 历史
必须保留。前端决定、真人确认及正式发行验收不由本合同自动通过。
