# PRT-01-A10-A05-P02-P01 Prototype Package 与项目 Template 页面

日期：2026-10-08
状态：`PRT_01_A10_A05_P02_P01_PROJECT_ORGANIZATION_PASS`

```text
前置任务：PRT-01-A10-A05-P01 PASS
涉及模块：Prototype Package 页面、PROJECT Template 页面、Template混合Scope读取
涉及实体：PrototypePackage、Prototype、PrototypeTemplate、TemplateVersion、DocumentVersion
涉及API：Package LIST/CREATE/GET/PATCH/SET_MEMBERS；PROJECT Template LIST/CREATE/REVISE；Document LIST
涉及权限：Package/PROJECT Template写仅ProjectManager、ImplementationMember；GLOBAL在项目页只读
验收标准：业务候选选择、完整集合提示、结构化模板表单、固定文档版本、未知结果安全恢复
风险：成员增量误解、任意JSON/脚本、GLOBAL误改、动态latest引用、混合Scope列表误拒绝
```

## 编码前兼容偏差与处理

冻结合同和后端 Owner 明确规定项目模板列表合并同项目 PROJECT 与获准 GLOBAL 当前版；既有前端客户端却
把项目列表每一项强制解析为 PROJECT，真实 GLOBAL 项会让整页失败。按持续授权修正读取投影：PROJECT 项仍
必须精确匹配当前项目，GLOBAL 项仍必须 `project_id=null`，其他 Scope、外项目 PROJECT、排序或重复继续失败
关闭。未改变路径、DTO、权限、cursor、Schema 或后端。

## 实现结果

- Package 页面从受权 Prototype 列表生成成员候选，支持创建、改名和全量成员替换；页面明确未勾选项只是
  从包移除，不删除 Prototype、Version、Review 或 Audit。没有 UUID 文本维护入口。
- Package CREATE/SET_MEMBERS 结果未知时保留原 Body、Key、ETag显式恢复；名称 PATCH 无幂等 Key，未知
  结果只做独立 GET 对账。所有列表限制最多20页，超限、重复或迟到响应失败关闭。
- 项目 Template 页面使用布局枚举、组件多选、终端多选和当前受权 Document 固定版本选择，不提供任意 JSON
  编辑器或脚本字段。新版本只追加，旧版本保持不可变；不兼容的历史合同只读，不降级到原始 JSON 编辑。
- 项目列表中的 GLOBAL Template 清楚标记为只读和非客户事实；PROJECT 创建/修订只能调用项目写入口。
  固定 DocumentVersion 通过受权 Document 候选产生，并保留固定版本定位；不提交动态 `latest`。
- GLOBAL Template 管理面仍需独立 DeploymentAdmin 页面，不借项目身份旁路；拆入 P02-P02 后续任务。

## 验证、兼容与回滚

- 定向33项覆盖混合Scope安全解析、外项目拒绝、Package完整集合原操作恢复、GLOBAL只读、结构化合同和固定
  DocumentVersion；Windows 11前端全量97文件/1580项、typecheck及Vite 195 modules生产构建通过。既有
  主chunk大于500 kB警告仍为非阻断优化项。
- 无 Schema/Migration、服务端 API、依赖、角色、Secret、客户数据或外发变化。可删除新增页面并恢复原
  项目模板解析器回滚，但恢复后含 GLOBAL 的合法项目列表会重新不可用；后端和历史均不变。
- 当前不声称路由、GLOBAL管理、真实Edge、Windows Server 2025、Gate 3、UAT或发行通过；Debian 13按
  用户指令跳过。
