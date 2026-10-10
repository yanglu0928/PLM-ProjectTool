# SUR-01-A06-A03：Survey 列表、Version 与问题卡片页面

日期：2026-10-06。结论：`SUR_01_A06_A03_FRONTEND_DEFINITION_PASS`。下一项：`SUR-01-A06-A04` Survey 来源只读解析边界前置与 Change Request。

## 实施结果

新增项目Survey列表、详情路由及项目详情入口。列表只显示名称、状态、当前批准Version是否形成和更新时间；分页cursor仅保存在当前组件内存。详情并行读取Survey与Version页，用户选择Version时再次按固定Version ID读取详情，不把列表对象、Review引用或当前批准引用当实时审批证明。

每个问题以卡片展示主题、问题、调研目的、需要维护的回答类型/必填性/规则、预期输出、证据要求、显示条件和选项；没有输入表单、接受建议或自动确认动作。页头持续强调“实际调研记录优先，模板仅供参考”，MANUAL说明明确不是客户确认，TEMPLATE持续显示“不是客户事实”。

来源卡片只显示业务可理解的类型和可用性，不显示Handover/Capability版本内row UUID。TEMPLATE可导航到当前Project受权Document历史，由用户核对固定版本；MANUAL明确当前无Document/Evidence绑定，Handover/Capability明确受控定位入口尚未接入，页面不猜内部标识、不复制正文。目标部门只显示计数并导航至项目部门历史，不把UUID作为人工操作入口。

所有页面在无身份、强制改密、路由切换、后续拒绝或迟到响应时清空旧数据；加载更多拒绝后不保留部分列表。当前只读页面不开放Survey创建、修改、归档、Version编辑、校验或送审。

## 客观验证

- 页面与项目导航定向3个文件、27项通过：无身份/改密、列表与分页、后续拒绝清空、跨Project迟到响应、根与Version分层读取、问题维护提示、实际/模板/交接来源标签、内部row ID不泄露、受权模板导航和错误清旧。
- 前端全量81个文件、1,429项通过；TypeScript typecheck通过；Vite production build转换171个模块并成功产出。
- 静态路由使主JS从A02的`599.01 kB`增至`625.76 kB`，继续超过500 kB提示。构建成功不等于加载性能通过；后续发行性能任务须以动态路由拆包和真实浏览器加载测量处理，本WBS不跨范围改造全局路由。

## 兼容、回滚与未关闭项

纯前端页面、路由和项目导航增量；无Schema、Migration、后端API、权限、依赖、配置、Secret、网络外发或客户数据变化。撤页面路由与导航即可回滚，服务器历史不变。

A04来源解析Owner/HTTP、A05按需定位和真实浏览器/PG、定义写交互、Round/Response/Conclusion、路由拆包性能、正式key/信任、Gate 3、UAT与发行仍未完成。
