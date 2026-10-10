# SOL-01-A04-P04-P02：PROJECT Reference GET HTTP 合同与隔离 PG 验证

日期：2026-10-09；结果：`REFERENCE_GET_HTTP_PG_PASS`，限定为可注入路由及 Windows 11 隔离 PostgreSQL/ASGI，不是正式发行或用户端开放。

```text
当前 Phase：Phase 2 Platform Core
输入基线：Gate 2 API-04、DEC-20261009-1114、P04-P01 读取 Owner
前置：PROJECT Reference 创建 HTTP/隔离PG及固定来源读取 Owner 已通过
涉及模块/实体：Solution API 当前版本读取；无 Schema/ORM 变更
涉及 API：新增可注入 PROJECT GET；默认和 GLOBAL 不挂载
权限：有效 License、真实 Session、同项目当前成员；Host/Origin 白名单
验收：响应白名单/ETag、错误Envelope、真实 ASGI/PG、越权/撤权/混源负例、后端全量
风险：正式 License/服务账户、Windows 组合、List/UI、当前来源资格未验
```

GET 只投影固定历史引用与创建时指纹；不重新认定来源当前有效，也不返回原文。读取服务核对所有引用的数量、连续顺序与 PROJECT/ProjectId，混入 GLOBAL 来源即失败关闭。HTTP 成功响应仅安全白名单及 Trace/ETag，默认应用与 GLOBAL 路径仍 404。冻结 API-04 无 Breaking Change，不需迁移或升级。

合同单元 `3 passed, 9 subtests passed`，后端全量 `3312 passed, 3 skipped, 4867 subtests passed`。Windows 11 一次性隔离 PG18.6/私有来源文件、真实 SessionService 和 ASGI 验证 PM/IM/客户读取、缺记录/跨项目/暂停成员 404、无 Session 401、Origin/License 403、查询 400 和混入 GLOBAL 引用 503；脚本退出 0，复用夹具的来源、PROJECT 创建及 Alembic drift 回归也通过。无 20 并发、正式账户/License、Server 2025、Debian13、List/UI/Gate3/发行结论。TraceLink：API-04/DEC-1114 → GET 增量合同 → API Router → 合同与隔离 PG 验证。
