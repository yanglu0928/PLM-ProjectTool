# PRT-01-A10-A05-P01 Prototype 列表、详情与范围决定页面

日期：2026-10-08
状态：`PRT_01_A10_A05_P01_LIST_DETAIL_PASS`

```text
前置任务：PRT-01-A10-A04 PASS
涉及模块：Prototype 列表页、详情页、Requirement 只读候选、Prototype 受控写客户端
涉及实体：Prototype、PrototypeVersion、RequirementVersion、PrototypeScopeDecision
涉及API：Prototype LIST/CREATE/GET/PATCH/MARK_NOT_REQUIRED/ARCHIVE、Version LIST、Requirement LIST
涉及权限：页面按当前 Session 项目角色显示操作；服务端仍逐请求重证 License、角色、Scope 与状态
验收标准：无隐藏 UUID 维护、逐字段提示、AI/模板非事实提示、幂等原样恢复、PATCH 独立 GET 对账
风险：把空原型当成不需要、把 AI 建议当批准、未知写结果重复提交、过期 ETag 覆盖并发修改
```

## 实现结果

- 列表页展示 Prototype 状态、正式版本是否形成、分页和结构化入口；创建表单明确只建立身份，不自动生成、
  校验或批准内容。没有 Prototype 时提示用户创建或进入正式范围决定，不把缺记录推断为“不需要”。
- 详情页汇总 Root、固定 Version 和当前批准 Requirement 候选。`NOT_REQUIRED` 只能从当前已批准需求中勾选，
  并要求人工填写原因、影响和确认声明；不提供 UUID 文本框，也不允许空集合代替范围决定。
- 两页仅向具备当前 Session、可提交状态和冻结角色的用户显示对应动作。模板、AI 建议、校验结果及创建回执
  均明确标为非批准事实；正式版本仍须固定输入、校验和人工 Review。
- CREATE、MARK_NOT_REQUIRED、ARCHIVE 在结果未知时保留原 Body、Key 和 ETag，由用户显式恢复同一操作；
  Prototype 名称 PATCH 不带幂等 Key，结果未知时只做独立 GET 对账，绝不自动重发或静默覆盖。
- 本子任务不注册生产路由。页面引用的固定命名路由由 A06 统一接入并执行跨路由撤权回归；Package、Template、
  Version 和 Link 的专用结构化页面由 A05 后续子任务完成。

## 验证、兼容与回滚

- 页面定向 2 项验证人工事实边界、批准 Requirement 选择、CREATE 原 Key 恢复和 PATCH 独立 GET 对账。
- Windows 11 前端全量 96 文件/1577 项、Vue/TypeScript typecheck 和 Vite 195 modules 生产构建通过；
  成功标记为 `PRT_01_A10_A05_P01_LIST_DETAIL_PASS`。既有主 chunk 大于 500 kB 警告仍为非阻断优化项。
- 无 Schema/Migration、服务端 API、依赖、角色、Secret、客户数据或外发变化。删除两个页面及对应测试即可
  回滚；后端、历史和冻结合同不变。当前不声称页面路由、真实 Edge、Windows Server 2025、Gate 3、UAT
  或发行通过，Debian 13 按用户指令跳过。
