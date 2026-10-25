# HND-05-A05-P02：交接 Review 安全客户端合同

日期：2026-10-25；状态：`HND_05_A05_P02_REVIEW_CLIENT_PASS / PILOT_NOT_READY`。

|编码前检查|结论|
|---|---|
|Phase/WBS|Phase 2 / `HND-05-A05-P02`；只扩展现有 PROJECT Review 客户端对 HND-02 的严格读取/决定映射，不改页面。|
|输入基线|Gate 2 API-02、`handover-review-read-v1-increment.md`、P01 Win11 PG/HTTP 实证、现有 ProjectReviewClient SOL-03/05/06 合同。|
|前置|HND-02 `REVIEW_GET` 已显式接线；通用 Review 决定 HTTP 已在 Handover 写 Owner 上成立；交接送审链接已有固定 ReviewId。|
|模块/实体/API|仅前端 Review 客户端与测试；原 `GET /projects/{p}/reviews/{r}` 和 `POST /rounds/{round}:decide`，不增字段。|
|权限|客户端必须严格匹配 HND-02 与 HANDOVER_ALL_V1，未知/错配投影拒绝；决定仍只允许当前 Session 的待决 Assignment，使用私有 CSRF、原 Key 和服务端回执。|
|验收|正确 HND 投影读取与决定、错配/非评审人/无提交能力拒绝；原 SOL 回归、前端全量/typecheck/build。|
|风险/回滚|本片不改后端/API/Schema/License；回退客户端会重新拒绝 HND 读取，已形成 Review/Audit 保留。通用页面当前会误标 HND 为结构化专项，P03 前必须修正，不把 P02 当作完整用户入口。|

编码前置满足。页面文案/固定交接版本链接、真实 Edge/PG/包内决定均另行验收。

实施只增加 HND-02/`HANDOVER_ALL_V1` 的严格一对一解析，原 SOL-03/05/06
配对与未知主题拒绝保持不变。客户端沿用既有私有 Session/CSRF、当前待决定
Assignment、原幂等号、固定轮次和服务端回执约束；单元测试覆盖正确交接读取/决定、
类型/策略交叉错配、非本轮评审人和空退回意见拒绝。定向 6 项、前端全量 188 文件
2,009 项、typecheck 和生产构建退出 0。首次定向命令使用错误工作目录路径而未运行，
修正后执行成功；无产品缺陷或 API/Schema 变化。

本片尚不能宣称交接评审页面可用：`ProjectReviewView` 当前把非 SOL-03/05
一概标成结构化专项，并给错误的固定版本入口。下一片 P03 专门修正交接标签、
固定分析/版本跳转和确认文案，再做真实浏览器/包内组合；不把客户端通过当客户批准。
