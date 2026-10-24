# HND-05-A04-P01：交接 DRAFT 版本送审前端安全客户端

日期：2026-10-25；状态：`FRONTEND_CONTRACT_PASS / REVIEW_UI_PACKAGED_PENDING / PILOT_NOT_READY`。

|编码前检查|结论|
|---|---|
|Phase/WBS|Phase 2 / `HND-05-A04-P01`；仅接冻结的交接版本原子送审前端命令，不修改校验面板/Review 页面。|
|输入基线|Gate 2 冻结 API、`docs/api-contract/handover-submit-review-v1-increment.md`、CR-HND-006；A03 校验前端已同步。无 API/Schema/权限变更。|
|前置|后端正式 Windows 组合已有 `:submit-review`，ProjectManager 当前权限与 Review Owner 同事务重验；项目成员/客户确认人枚举可由既有 ProjectMemberReadClient 用于后续页面。|
|请求/回执|DRAFT 且无 Review 引用；1～32 个互异 canonical ReviewerId；精确 `HANDOVER_ALL_V1`、`due_at=null`、`submission_note=null`；当前 Session/CSRF/Origin、原幂等 Key；201 仅 `IN_REVIEW` 首轮回执，不是批准。|
|风险|评审人资格、来源与项目状态可能变化，前端只能预筛，服务端最终权威；未知结果必须保留原 Key/评审人集合，不能换号重复提交或自动称已批准。|
|验收|定向覆盖请求/排序、强身份/状态/角色预筛、回执结构/ETag/Trace、错误状态与未知结果；全量前端/typecheck/build。真实 Edge/PG/包内和评审人页面留后续独立任务。|

编码前条件满足；若冻结合同与生产边界冲突，先记录 CR，不静默改 `/api/v1`。

实施：私有 Session 增加冻结交接送审 POST 路径及 8 KiB 上限；客户端要求同项目
ProjectManager、DRAFT/无 Review 引用、互异 canonical ReviewerId，固定排序后构造
`HANDOVER_ALL_V1` 与显式双 null。仅接受精确 `HND-02`、`IN_REVIEW` 首轮、原评审人集、
actor/项目/分析/版本匹配、ETag/Trace/时间可信的 201 回执；不把送审当批准。确定拒绝
映射冻结错误码，503/网络和不可信回执按结果不确定处理，供后续页面保留原号。

验收：定向10项覆盖精确请求、排序、角色/状态/重复确认人拒绝、伪批准/错人回执、
六类 HTTP 状态和网络未知；前端全量187文件2001项、typecheck/build退出0。首次构建
因新冻结路径未加入 Session 私有写路径类型白名单而失败，补齐该单一路径后完整复跑通过。
无 API/Schema/权限/License 及数据迁移；回退客户端不删除已合法创建的 Review/Audit。
送审页面、真实 Edge/PG/固定包及 Reviewer 人工决定均未在本片验收。
Next：`HND-05-A04-P02` 以既有项目成员列表实现当前合格确认人选择/原号恢复页面。
