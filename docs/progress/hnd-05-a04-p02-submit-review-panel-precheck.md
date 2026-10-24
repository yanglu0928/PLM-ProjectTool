# HND-05-A04-P02：交接 DRAFT 送审确认人页面

日期：2026-10-25；状态：`FRONTEND_CONTRACT_PASS / PACKAGED_BROWSER_PENDING / PILOT_NOT_READY`。

|编码前检查|结论|
|---|---|
|Phase/WBS|Phase 2 / `HND-05-A04-P02`；仅把 P01 冻结送审客户端接入交接详情的已选 DRAFT 版本。|
|输入基线|Gate 2 冻结 HND/Review 合同、`handover-submit-review-v1-increment.md`、P01 客户端定向10/前端全量2001及构建已同步；不改 API/Schema/Review Owner。|
|前置|现有详情页提供不可变版本，ProjectMemberReadClient 支持当前项目成员分页；项目负责人可送审，客户确认人资格仍由服务端同事务重验。|
|页面行为|只列当前 ACTIVE 的 CUSTOMER_MANAGER/CUSTOMER_MEMBER 候选，最多32人；用户显式核对版本和确认人后才送审。未知结果保留原 Key 与完整确认人集合，先核对评审再同号重试。201 仅展示 IN_REVIEW 与评审入口，不称批准。|
|风险|校验 PASS 也不是送审保证；来源、Action 覆盖或确认人资格变化由后端拒绝。成员列表不完整时拒绝给出假“全量可选”结论，不外发客户正文。|
|验收|定向角色/候选过滤/确认/原号恢复/跨版本清屏与既有详情回归；前端全量/typecheck/build。真实 Edge/HTTPS/PG/固定包和真人评审留下一独立组合验收。|

编码前条件满足；当前任务只解决用户可操作的送审入口。

实施：交接详情的已选 DRAFT 版本增加送审面板，ProjectManager 显式点击后才分页读取
项目成员；只显示当前 ACTIVE 的客户角色，最多选32人，显式核对固定版本/范围后送审。
未知结果将 actor/project/analysis/version、原确认人集合和 Key 保留在浏览器会话，
必须先核对评审再同号重试；201 只显示 `IN_REVIEW` 首轮和评审链接，不称批准。
成员刷新会重核所选集合并撤销确认，成员列表不完整时不开放新送审，服务端仍最终
重验资格、来源、Action 覆盖与 License。

首次定向：新增面板自身通过，但既有交接详情用例发现自动加载成员在用户查看原文时
提前显示无关的成员读取错误，遮蔽原文定位错误；未将该轮记为通过。改为显式点击
“读取当前项目确认人”后才发起成员请求，并让送审后已有 Review 在详情刷新时继续可达；
定向面板4/详情4重新通过，前端全量188文件2006项、typecheck/build退出0。
无 API/Schema/权限/License 或数据迁移，回退前端面板
不删除合法 Review/Audit。真实 Edge/HTTPS/PG/固定包及真人 Reviewer 决定仍待。
Next：从已同步的干净提交制作新非发行包，一次验证 DRAFT→校验报告→送审与拒绝矩阵；
若送审被 Action 覆盖前置阻断，使用既有正式 Action 路径建立有来源的合成待办，不伪造
当前来源或跳过资格。
