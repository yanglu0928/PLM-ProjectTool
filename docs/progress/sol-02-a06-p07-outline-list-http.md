# SOL-02-A06-P07 SolutionOutline 列表可选 HTTP

日期：2026-10-09。状态：可选 HTTP 合同及 Windows 11 隔离 ASGI/PostgreSQL 验证通过；Windows 平台组合未挂载。

## 编码前检查

- 当前 Phase/WBS：Phase 2 Platform Core / SOL-02-A06-P07。
- 输入基线：冻结 API-04 `SOL_OUTLINE_LIST`；P04 内部 Owner/keyset、P05 独立签名游标、P06 Windows 当前账户密钥工厂。
- 前置任务：P04～P06 对应读取/游标/临时密钥恢复均已验证。
- 模块/实体/API/权限：Solution 可选 HTTP 与 app 注入；SolutionOutline 摘要；冻结 `GET /api/v1/projects/{project_id}/solution-outlines`，有效 Session/License/当前项目成员。
- 验收标准：默认404，读模式 POST仍404；有界 page size 和签名 cursor，真实 PG 多页、固定最小响应、trace/no-store；游标篡改/跨会话/项目/查询及非法 Origin、权限、License 均失败关闭。
- 风险：本切片使用合成游标 key；正式 Windows 组合密钥供给/目标服务账户与非空已批准版本尚未验，不能宣称生产可用。

## 实施与验证

新增 `create_outline_list_router` 与 app 可选注入点。HTTP 先校验可信 Host/Session，规范项目 UUID、page size、唯一 query key 与独立签名 cursor；每页由 P04 Owner 重验 License/项目成员。只返回目录 ID、项目、名称、状态、已批准指针、创建时间、ETag，不返回草稿正文；`data.items/next_cursor/has_more` 与 trace_id、no-store 固定。默认无路由，未破坏冻结 `/api/v1` 合同。

- 定向合同：3 passed / 13 subtests；默认关闭、双页、字段投影、游标上下文、错误响应。
- Windows 11 隔离 PG18.6/ASGI：真实 Session 下三根三页/签名游标、默认 GET/读模式 POST 404、跨项目/暂停成员/匿名/Origin/License 拒绝通过；临时库/实例按夹具清理。
- 后端全量回归：3384 passed / 3 skipped / 5088 subtests passed。
- Schema/Migration/依赖：均无变化；撤下可选注入即可回滚，历史保留。

下一项：`SOL-02-A06-P08` Windows 显式只读/写平台组合，使用 P06 独立游标密钥并验证缺密钥失败关闭；之后再推进 UI/浏览器。正式发行信任源与性能仍待。
