# SOL-02-A06-P04 SolutionOutline 列表内部 Owner/keyset

日期：2026-10-09。状态：Windows 11 隔离 PostgreSQL 18.6 的真实 Session/keyset 验证通过；公开游标/HTTP/Windows 组合未实现。

## 编码前检查

- 当前 Phase/WBS：Phase 2 Platform Core / SOL-02-A06-P04。
- 输入基线：冻结 API-04 `SOL_OUTLINE_LIST`、DM-05 SolutionOutline/OutlineVersion；P01 详情读取 Owner、P03 Windows 详情组合。
- 前置任务：目录 CREATE、当前项目成员授权、Session/License 与 Schema 0146 已验证。
- 模块/实体/API/权限：Solution Application/Repository、Project 策略；SolutionOutline 及可选批准指针；冻结列表 GET 尚未公开挂载；当前项目所有成员可读。
- 验收标准：有界 `limit+1`、根 ID 升序 keyset、稳定下一页/空尾页；同项目隔离、Session/License/成员拒绝；异常批准指针失败关闭。
- 风险：内部 `after_outline_id` 不具防篡改能力，只能作为后续签名 HTTP cursor 的内部参数，不能直接暴露给浏览器；未审批根保持 null，不推断批准事实。

## 实施与验证

新增 `SOL_OUTLINE_LIST` 独立全项目成员读权限与共享读锁；`OutlineReadService.list_current` 验证请求、会话、License、项目成员和分页投影；仓储按项目、根 ID 排序及 `limit+1` 读取，只投影目录摘要，并复用详情的已审批指针一致性防线。包含 ACTIVE/ARCHIVED 身份，不披露未批准版本正文。

- 定向单元：14 passed / 721 subtests；含角色/License、无效 limit/after、重复/乱序/跨项目/伪造摘要失败关闭。
- Windows 11 隔离 PG18.6：真实创建三条根身份，单页与三页 keyset 顺序一致、末页/空尾页正确；跨项目、暂停成员及非法 limit 拒绝，通过。临时数据库/进程由夹具清理。
- 后端全量回归：3376 passed / 3 skipped / 5060 subtests passed。
- Schema/Migration/依赖/冻结 API：无变更。撤下内部列表 Owner/权限即可回滚，历史保留。

下一项：`SOL-02-A06-P05` 独立签名游标及会话/项目/查询绑定；再按独立任务做 HTTP 与 Windows 组合。正式信任源、非空批准链、20 并发和发行仍待。
