# A06-P05-P06-P09-P02 PlanVersion 不可变草稿创建前置核查

- 日期：2026-10-26
- WBS：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P09-P02`
- 结果：`PRECHECK_PASS`

## 编码前检查

```text
当前Phase：Phase 2 Platform Core
当前WBS：PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P09-P02
输入基线：冻结API-04 PLAN_VERSION_CREATE、PLAN_VERSION_GET；已冻结PlanVersion聚合/ORM与不可变来源证明；P09-P01历史列表及固定快照页/Read Client；现有PlanVersionWriteClient.create；Solution Outline/OutlineVersion既有读取Client
前置任务：P06-P04原子SubmitReview HTTP、P06-P06写Client、P08版本列表HTTP、P09-P01历史与固定快照只读界面均完成；Create Owner/HTTP factory现有但尚未装入显式Windows写组合
涉及模块：Windows显式写组合（PlanVersion Create router）；frontend PlanVersion Create client消费、Approved Solution固定版本候选、不可变Create页面及读回；后端合同/隔离Win11 PG18验证；STATUS/CHANGELOG
涉及实体：PlanVersion DRAFT、Approved Solution OutlineVersion固定引用、WBS根任务、Acceptance/Entry conditions、日历/里程碑/依赖/排除项（仅本页面表单提供且保持完整schema）
涉及API：只用冻结POST `/api/v1/projects/{project_id}/plans/{plan_id}/versions` 与既有冻结GET固定版本接口；候选只读用已存在Outline/OutlineVersion GET；无新增API/Schema/Migration
涉及权限：创建只允许项目负责人或实施成员；服务端保持Session/CSRF、幂等、License、项目授权及Approved Solution源证明；router仅挂载于include_secret_write显式Windows组合，不扩大login/read权限
验收标准：只能选择同项目已批准且经详情回读核实的Solution固定版本；提供用户可维护的WBS根任务名称/编号/分类、至少一项AcceptanceCriteria及可选准入条件/排期/风险/排除说明；固定完整草稿预览；新建操作号/内容原样保存在sessionStorage并在不确定结果时只允许原内容原操作号重试；创建结果按返回固定version ID读回并校验身份及内容一致；路由变化/会话变化忽略旧响应；定向、前端全量/typecheck/build、后端全量与Win11隔离PG18真实来源/SQL/HTTP组合
风险：不可用名称/状态推断Solution已Approved，必须读取固定版本且服务器重验；不得将新建DRAFT称作Approved/已交付；不要创建空WBS或缺少AcceptanceCriteria的业务无效快照；Validate/Review交互仍独立；写路由不得被普通read模式挂载
```

## 输入输出/排程

- 前端由现有 Outline 列表读取活动目录、逐个读取冻结版本历史并筛选 `APPROVED`；提交前再固定读回所选版本详情，生成严格固定引用。若候选量超限、读取不完整或身份不匹配，则关闭提交，不做部分成功选择。
- Create Owner 结构验证要求至少一项 `approved_solution_refs`；WBS项需精确提供冻结字段。页面先实现一个完整根任务（含必填AcceptanceCriteria）及可选里程碑/依赖/排除项，确保JSON完整且无空白有效载荷。
- 对未知的项目部署配置、版本状态或源资格由服务端Create Owner最终判定；页面仅是建议和输入，不把前端候选视为业务授权。
- 本任务可在原授权内直接实现；未改冻结基线，无外发数据、无生产数据库操作。编码前置记录应先同步，再修改代码。
