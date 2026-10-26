# A06-P05-P06-P09-P01 PlanVersion 历史/固定快照页面编码前核查

- 日期：2026-10-26
- WBS：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P09-P01`
- 结果：`PRECHECK_PASS`

## 编码前检查

```text
当前Phase：Phase 2 Platform Core
当前WBS：PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P09-P01
输入基线：冻结API-04 PLAN_VERSION_LIST、PLAN_VERSION_GET、PLAN_VERSION_WBS_LIST；现有不可变PlanVersion ORM/Owner；P08完成的版本列表HTTP/cursor；现有Vue 3/TypeScript/Vite及Plan读页面模式
前置任务：P06-P04 SubmitReview HTTP与P06-P06写Client完成；P08冻结版本列表端点已在Win11/PG18组合验收并推送；固定版本Get Owner与router factory已存在但未装入显式只读启动组合
涉及模块：backend Windows只读composition/API app wiring；frontend Plan API Client、历史列表/固定快照Vue页、Plan详情/路由；前端/后端合同测试、STATUS/CHANGELOG
涉及实体：Plan身份、PlanVersion版本摘要、不可变快照/WBS/依赖/里程碑（只读）
涉及API：仅冻结GET `/api/v1/projects/{project_id}/plans/{plan_id}/versions`、GET `/api/v1/projects/{project_id}/plans/{plan_id}/versions/{plan_version_id}`；本项不新增API、不装WBS分页之外的未实现功能
涉及权限：Session有效且项目成员只读；UI不给无项目访问权/强制改密账户展示数据；read route只在显式Windows read mode挂载，普通create_app/login-only仍关闭
验收标准：列表schema/cursor/顺序异常关闭、分页无重复；固定版本详情严格校验身份与快照字段；跨项目/版本路径错误由服务404；页面支持列表到固定快照导航、空/忙/错误/刷新、路由切换不显示旧项目数据；显式Windows组合挂载，默认/登录-only返回404；定向、前端全量/typecheck/build、后端回归及Win11隔离PG18真实HTTP组合
风险：历史PlanVersion页面不得将DRAFT/历史来源显示为批准/交付事实；快照内容不得编辑；本项暂不建Create表单，下一WBS独立实现完整不可变草稿录入，避免将无效空快照写入数据库
```

## 排程调整

- P09原组合任务拆为P09-P01（列表与固定快照只读页面）和P09-P02（Approved Solution源选择、完整WBS/Acceptance输入、不可变Create与重读）。理由是只读历史导航可立即消费已验收API，而创建必须先完备源版本选择与完整聚合录入；不能用空快照或模拟来源缩短交付。
- 未修改冻结基线；无Schema/Migration/API Contract变化。P09-P01只给现有PLAN_VERSION_GET Windows只读工厂增加显式装配，并由页面消费既有冻结端点。
