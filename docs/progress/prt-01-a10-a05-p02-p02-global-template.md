# PRT-01-A10-A05-P02-P02 GLOBAL Prototype Template 管理页面

日期：2026-10-08
状态：`PRT_01_A10_A05_P02_P02_GLOBAL_TEMPLATE_PASS`

```text
前置任务：PRT-01-A10-A05-P02-P01 PASS
涉及模块：DeploymentAdmin GLOBAL Template页面、共享结构化Template表单、GLOBAL Document元数据
涉及实体：PrototypeTemplate、TemplateVersion、GLOBAL DocumentVersion
涉及API：GLOBAL Template LIST/CREATE/REVISE；GLOBAL Document LIST/CONTENT
涉及权限：仅DeploymentAdmin；页面角色提示不替代服务端Session、License、Admin与文档权限重证
验收标准：不依赖ProjectId、结构化字段、固定GLOBAL文档、不可变修订、未知结果原操作恢复
风险：借项目权限管理GLOBAL、模板冒充客户事实、任意JSON/脚本、动态latest、重复创建或修订
```

## 实现结果

- 新增独立部署管理页面，不要求或提交 ProjectId；非 DeploymentAdmin 不读取模板/文档，也不渲染管理表单。
  所有真实读取和写入仍由服务端逐请求重证，客户端角色判断仅用于最小暴露。
- GLOBAL Template 创建/修订与项目页面共用受限布局、组件、终端和固定文档合同生成器；不提供任意 JSON、
  脚本、URL 或隐藏 UUID 编辑。非当前结构化合同的历史模板保持只读，不用自由编辑器绕过。
- 文档候选只来自受权 GLOBAL Document 元数据的有效固定版本。已发布模板的固定文档原文使用 same-origin
  固定 content URL，服务端重新核验 Session、GLOBAL权限、License及文件完整性；不暴露磁盘路径。
- CREATE/REVISE 结果未知时保留原结构、DocumentVersion、Key及修订ETag，由管理员显式恢复首次操作；不
  自动生成重复 TemplateVersion。修订只追加不可变版本，并提示旧版本及项目固定事实不受影响。
- 页面不在本子任务注册 Router；A06统一接入`/admin/prototype-templates`并执行登录/撤权回归。

## 验证、兼容与回滚

- 定向5项覆盖GLOBAL元数据、固定内容定位、结构化创建、原Key恢复、强ETag修订及普通用户不读取；
  Windows 11前端全量98文件/1583项、typecheck和Vite 195 modules生产构建通过。既有主chunk大于500 kB
  警告仍为非阻断优化项。
- 无Schema/Migration、服务端API、依赖、角色、Secret、客户数据或外发变化。删除页面及共享表单模块、恢复
  项目页内联生成器即可回滚；后端、模板历史和固定项目事实不变。
- 当前不声称路由、真实Edge、Windows Server 2025、Gate 3、UAT或发行通过；Debian 13按用户指令跳过。
