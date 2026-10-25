# A06-P05-P06-P05 PlanVersion 用户路径前置核查

- 日期：2026-10-26
- WBS：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P05`
- 结果：`PRECHECK_PASS_WITH_API_GAP`

## 现状与冻结接口

- 前端已有项目Plan列表、Plan创建、单Plan身份详情及创建客户端；路由为 `/projects/:projectId/plans`、`/new`、`/:planId`。列表/详情明确提示当前不含PlanVersion/WBS/评审。
- 尚无PlanVersion专属API client、页面、版本详情路由或已验证的安全SessionClient方法；当前认证写操作须经SessionClient受限写桥接，禁止页面直接fetch绕过。
- 后端已有冻结API-04的PlanVersion DRAFT创建、单版本GET、WBS分页GET、bodyless VALIDATE及原子SUBMIT_REVIEW。写操作要求可信Origin、Session/CSRF、幂等键；原子送审固定`PLAN_VERSION_ALL_V1`与`due_at/submission_note=null`。
- 冻结接口没有PlanVersion collection/list端点；Plan身份读取当前也不暴露版本历史列表。因此不能从Plan页恢复任意历史版本列表。不得用客户端推测/数据库直读补齐，也不在本项新增或修改冻结`/api/v1`合同。
- 创建payload是完整不可变快照，含固定Approved Solution refs、WBS、dependencies、milestones、exclusions和calendar；服务同事务重证来源，且当前Output refs未支持。创建后Validate为独立不可变报告，送审须用原子PlanVersion SubmitReview，不得拆成通用Review Create/Start。

## 设计决定 / 后续切片

1. 先实现前端安全传输层：在SessionClient精确增加PlanVersion create/validate/submit-review窄方法及写路由白名单；实现严格响应解析、固定policy/null字段、原幂等键重试、不确定结果不换key。不得直连API或绕过Session/CSRF/Origin。
2. 后实现用户工作页：从Plan详情创建固定版本并进入版本详情；对固定版本读取/WBS分页展示，提供来源选择和完整WBS填写、Validate报告、仅在校验通过后原子送审及Reviewer选择。明确快照不可修改，失败/超时保留原操作号，不制造“已批准/已交付”暗示。
3. 分片验收客户端合同、页面行为，再用Windows 11 Edge→显式Write API→隔离PG做合成链验证。合成身份/License/批准来源不得描述为正式信任。

## 验收边界

- 本项仅静态核查，无代码、API、Schema、业务数据或数据库变化；未运行新增测试。
- 已确认用户入口、冻结读写路径与缺口，并确定不改API的客户端/页面拆分。
- 版本历史列表、真实来源Proof、Edge用户操作、Gate/Pilot/Release仍未通过。

## 下一项

`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P06`：前端PlanVersion安全写Client / SessionClient方法前置核查与实现；只覆盖create、bodyless validate、atomic submit-review及安全路由类型，不新增页面。
