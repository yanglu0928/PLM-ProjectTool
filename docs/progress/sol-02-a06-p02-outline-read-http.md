# SOL-02-A06-P02 SolutionOutline 详情 GET HTTP

日期：2026-10-09。状态：可选 HTTP 合同与 Windows 11 隔离 ASGI/PostgreSQL 验证通过；生产组合仍未挂载。

## 编码前检查

- 当前 Phase/WBS：Phase 2 Platform Core / SOL-02-A06-P02。
- 输入基线：Gate 2 冻结 API-04 `SOL_OUTLINE_GET`，P01 详情读取 Owner，现有可选路由及 Session/Origin 合同。
- 前置任务：P01 内部授权/仓储及隔离 PG 验证通过。
- 模块/实体/API/权限：Solution API 与应用路由注入，读取 SolutionOutline；`GET /api/v1/projects/{project_id}/solution-outlines/{outline_id}`；项目当前成员、有效 Session/License。
- 验收标准：默认关闭；显式注入返回 200、固定 `data/trace_id`、强 ETag、no-store；非法路径/查询、Origin、Session、跨项目/无权限和 License 失败关闭。
- 风险：本切片只暴露已验证的内部 Owner，不代表 Windows 生产模式、正式 License 信任锚、性能或非空批准版本已验。

## 实施与验证

新增 `create_outline_read_router` 并为 `create_app` 增加可选注入点，默认无路由。API 先验证可信 Host 与 Session，再解析规范 UUID、拒绝查询参数，调用 P01 Owner；仅投影目录身份、状态、当前已批准指针、创建者/时间与 ETag，返回异常不含 traceback。

- 合同定向：3 passed / 8 subtests。
- Windows 11 隔离 PostgreSQL 18.6：真实 Session/ASGI 200、ETag、默认 404、匿名 401、错误 Origin 403、非法查询 400、跨项目/不存在/暂停成员 404，通过；临时库/实例由夹具清理。
- 后端全量回归：3372 passed / 3 skipped / 5040 subtests passed。
- Schema、Migration、依赖：均无变化。关闭可选注入即可回滚；保留既有历史与 API 冻结版本。

下一项：`SOL-02-A06-P03` Windows 显式组合挂载与缺信任源失败关闭；随后独立推进 LIST/分页。
