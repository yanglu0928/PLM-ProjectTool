# PRT-01-A10-A05-P03 Prototype Version 结构化页面

日期：2026-10-08
状态：`PRT_01_A10_A05_P03_VERSION_PAGE_PASS`

```text
前置任务：PRT-01-A10-A05-P02-P02 PASS
涉及模块：Prototype Version列表/详情/创建、Validate、Submit Review、固定Document定位
涉及实体：Prototype、PrototypeVersion、TemplateVersion、RequirementVersion、DocumentVersion、Review
涉及API：Prototype GET；Version LIST/GET/CREATE/VALIDATE/SUBMIT_REVIEW；Template/Requirement/Document/Member LIST
涉及权限：创建/校验仅PM与ImplementationMember；送审仅PM；Reviewer仍由服务端逐人重证
验收标准：业务候选选择、不可执行交互、自动Coverage、固定来源定位、校验非批准、幂等原操作恢复
风险：隐藏UUID、动态latest、任意脚本、伪造Coverage、旧校验报告、ImplementationMember越权送审
```

## 实现结果

- 同一页面支持Version列表和固定Version详情路由。创建只从当前获准TemplateVersion、当前批准
  RequirementVersion和受权PROJECT Document固定版本中选择，不提供技术ID文本框或动态`latest`引用。
- InteractionSpec使用受限交互模式、导航方式和人工说明；CoverageSummary由已选批准需求/制品数量自动生成，
  标记`maintained_by=HUMAN`，不提供任意JSON、脚本、代码、命令或URL编辑器。当前OutputArtifact无Owner，
  页面只提供服务端已支持的DocumentVersion。
- Version创建固定Root ETag、完整输入和幂等Key；VALIDATE和SUBMIT_REVIEW同样保留原Key。三种操作结果未知
  时均只能显式恢复原操作，不自动生成新Key；重新校验会立即清除旧报告。
- 校验报告明确是当前事实检查且不改变状态；只有报告有效后才展示Reviewer候选。送审固定
  `PROTOTYPE_ALL_V1`，只允许ProjectManager，回执只表示IN_REVIEW，不表示批准。
- 固定DocumentVersion有受权Document根时提供版本历史定位；旧投影缺根时明确不可定位，不扫描或猜测。
  Requirement和Reviewer使用业务代码、姓名、角色及部门显示，内部ID不要求用户维护。
- 页面不在本任务注册Router；列表/详情命名路由和项目导航由A06统一接入。

## 验证、兼容与回滚

- 定向2项覆盖创建/校验/送审三类原操作恢复、结构化输入、自动Coverage、固定原文定位、直接Version读取和
  ImplementationMember不得送审；Windows 11前端全量99文件/1585项、typecheck及Vite 195 modules生产
  构建通过。既有主chunk大于500 kB警告仍为非阻断优化项。
- 无Schema/Migration、服务端API、依赖、角色、Secret、客户数据或外发变化。删除页面和测试即可回滚；
  后端Version/Review历史不变。
- 当前不声称路由、真实Edge、Windows Server 2025、Gate 3、UAT或发行通过；Debian 13按用户指令跳过。
