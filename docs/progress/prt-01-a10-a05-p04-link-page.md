# PRT-01-A10-A05-P04 RequirementPrototypeLink 结构化页面

日期：2026-10-08
状态：`PRT_01_A10_A05_P04_LINK_PAGE_PASS`

```text
前置任务：PRT-01-A10-A05-P03 PASS
涉及模块：RequirementPrototypeLink列表、创建、撤销、替换及验收覆盖分区
涉及实体：Requirement、RequirementVersion、AcceptanceCriterion、Prototype、PrototypeVersion、RequirementPrototypeLink
涉及API：Requirement/Prototype LIST；RequirementVersion/PrototypeVersion GET；Link LIST/CREATE/REVOKE/SUPERSEDE
涉及权限：读取为项目成员；三项写操作仅PM与ImplementationMember，服务端仍逐次重证
验收标准：业务候选、双端当前批准交叉证明、稳定验收引用、完整覆盖分区、生命周期与幂等原操作恢复
风险：隐藏UUID、过期批准版、Prototype未固定Requirement、空/部分覆盖被误判完整、替换改变逻辑身份、未知结果重复写
```

## 实现结果

- 创建只允许从当前ACTIVE且具有批准指针的Requirement/Prototype业务候选中选择。加载覆盖表单时并行读取
  两个当前批准Version，要求PrototypeVersion已固定引用精确RequirementVersion；最终提交仍由服务端重新验证
  当前事实，页面交叉检查不替代Owner证明。
- AcceptanceCriterion仅消费A02提供的稳定只读引用；任一引用为空或重复时失败关闭，不显示UUID回填入口。
  每条标准必须明确选择`COVERED`或`UNCOVERED`，未覆盖项必须填写原因，且至少一项已覆盖；页面据此生成
  不相交的完整Coverage分区，不把空Link、空白或部分标记解释为完整覆盖。
- 列表保留ACTIVE、REVOKED、SUPERSEDED全部历史，以需求代码、原型名称、用途、状态和覆盖计数显示。
  撤销需要单独确认且不删除历史；替换锁定原Requirement Root、Prototype Root和purpose，只允许更新到双端
  当前批准Version并重新形成完整Coverage。
- CREATE、REVOKE和SUPERSEDE结果未知时均保留原完整输入与Idempotency-Key，用户只能显式恢复原操作；
  不增加冻结合同未定义的If-Match。项目切换或迟到响应不能写入新项目页面状态。
- 所有提示明确Link和Coverage是人工声明而非Review批准。页面不在本任务注册Router；由A06统一接入导航、
  即时撤权与路由守卫。

## 验证、兼容与回滚

- 定向3项覆盖稳定引用完整分区、双端批准固定关系、缺引用失败关闭、创建与替换原操作恢复及逻辑身份锁定；
  Windows 11前端全量100文件/1588项、typecheck和Vite 195 modules生产构建通过。既有主chunk大于500 kB
  警告仍为非阻断优化项。
- 无Schema/Migration、服务端API、依赖、角色、Secret、客户数据或外发变化。删除页面和测试即可回滚；
  后端Link历史不变。
- 当前不声称路由、真实Edge、Windows Server 2025、Gate 3、UAT或发行通过；Debian 13按用户指令跳过。
