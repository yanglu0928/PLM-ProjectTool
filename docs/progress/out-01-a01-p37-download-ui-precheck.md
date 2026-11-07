# OUT-01-A01-P37：输出历史受控下载入口编码前检查

- 日期：2026-11-06
- 结论：PASS_WITH_LIMITATION（可实现；正式Platform信任装配仍阻塞）
- 基线：P36 PASS_SCOPE_LIMITED、CR-OUT-032、OutputRequest历史列表Project Role guard。
- 执行边界：GitHub源代码；测试只用Hosted D: runner/云端沙箱，不在本机或C盘运行项目代码。

## 编码前检查

- 当前 Phase：Phase 2 Platform Core。
- 当前 WBS：OUT-01-A01-P37。
- 输入基线：OutputRequestListView/Client、P36 Artifact引用GET、Document内容下载route。
- 前置任务：P36 GET与Windows受保护Platform组合已由Hosted run 42121003242验证；router仍opt-in。
- 涉及模块：frontend output API client、OutputRequestListView及组件/API测试。
- 涉及实体：仅客户端映射OutputRequest和OutputArtifact固定引用；无新增实体。
- 涉及API：消费独立Artifact引用GET；内容经严格验证的同源content_url进入已有Document下载route；不改后端/API/Schema。
- 涉及权限：保留输出列表既有角色检查；仅SUCCEEDED出现下载操作；服务端重查Session/CSRF/License/Project成员/Artifact状态。客户端仅接受预期Project/Request、合法ID、hash/size/MIME及固定同源Document内容路径，拒绝外域/query/fragment。
- 验收标准：成功态显示下载操作，其他状态不显示；加载防重复；错误无导航、无自动重试；前端定向/全量测试、typecheck/build。
- 风险：正式Platform trust未建立时服务route可能未挂载；404/服务不可用应提示暂不可下载，不猜Document、不直读磁盘。
- 回滚：移除新客户端/按钮/状态；不改服务器文件或生成事实。
- Hosted计划：Windows D:；前端全量测试/build与后端全量/wheel；沿用P36 PG18及A17/A34/A35/P24/A50。真实Win11下载受正式trust/用户环境缺失限制，不虚报通过。

## 范围

仅完成输出历史受控下载按钮与同源客户端消费；不接License trust/ACL、不执行插件、不读本地磁盘。