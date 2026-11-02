# PLT-PKG-01-A09-P51-A50：交接待办固定来源导航结果

- 日期：2026-11-02
- 结果：PASS_LIMITED
- 变更请求：CR-HND-009
- 代码提交：`ae1c0455f0fdb7c54d4f9fe6b7364c8a5ae37c12`
- hosted run：[41391544470](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41391544470)，12/12 jobs success

## Changed

- 新增只读 Handover Action 来源位置子资源：根据当前项目内 Action 记录的不可变 Version/Item 关系解析父 Analysis ID。
- Action 工作台新增来源跳转按钮；仅消费服务端校验的固定来源ID，HUMAN来源不提供虚构链接。
- 固定版本详情页支持 `sourceItemId`，分页找到对应问题卡并聚焦页面；原有 Evidence Viewer仍独立重新授权获取证据。
- 首轮 hosted 检查发现Windows组合根路由列表测试仍只列两条路径；差异先记录于 CR-HND-009，再将只读子路由纳入预期，重跑全量流水线通过。

## Files

Backend read service/repository/router 与 API contract tests；Frontend source-location client、Action workspace、固定版本详情与对应组件/客户端测试；CR、前置/结果记录、API增量合同和根状态/变更日志。

## Migration

无。数据库实体、Schema与Migration不变。

## API

新增可选只读 `GET /api/v1/projects/{project_id}/handover-action-items/{action_item_id}/source-location`；保留冻结的 Action GET 既有投影。复用当前 Session、License、Project成员读授权；HUMAN来源受控返回 unavailable；越权、跨项目和失效关系失败关闭。响应不含正文、文件绝对路径或任意URL。

## Tests

- GitHub Hosted Windows Server 2025 workflow run 41391544470：后端3,850项及 wheel 成功；前端2,075项/200文件、typecheck/build成功；全12 jobs成功。
- 同run临时PG18.6/pgvector0.8.6生命周期、父包20,122项候选及摘要 `24f37f60eb1f95a893af829b796926873c02b55e4f0b7d4762486f8dc6db3eda`、A34离线替换/显式恢复、A17 PlanVersion Edge/HTTPS/PG 29 API均成功。
- A17 Edge不覆盖A50来源导航；专项Edge合成验收尚待，故限定为PASS_LIMITED。

## Result / Known Issues

代码及自动化全量检查通过；无Migration、未启动产品API/service。未在用户本机或C盘运行程序，hosted Windows runner使用D盘工作/临时目录。本次不能证明真实Windows11设备兼容，也未关闭Gate 3、Pilot或Release。

## Next

`PLT-PKG-01-A09-P51-A50-E01`：在GitHub Hosted Windows Edge上完成Action来源按钮到固定版本准确问题卡片的合成端到端验收，并验证HUMAN不可用、越权/失效失败关闭与Action状态保留。
