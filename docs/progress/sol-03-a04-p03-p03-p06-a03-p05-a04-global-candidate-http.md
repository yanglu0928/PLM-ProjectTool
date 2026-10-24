# SOL-03-A04-P03-P03-P06-A03-P05-A04：项目 GLOBAL 候选可选 HTTP

日期：2026-10-09。结果：默认关闭的 GET 合同及 Windows 11 隔离 ASGI/PG18.6 通过；Windows 正式组合未挂载，项目页面仍不可使用。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / 本项；输入 Gate 2 API-04、CR-SOL-018、DEC-1154/1155、已验 A03 受权 Owner/签名游标。
- 单一问题：以严格、最小且默认关闭的项目 GET 合同提供当前 GLOBAL 候选，而不暴露管理员列表或原始名称。
- 模块/实体/API/权限：Solution API 与 `create_app` 可选注入、增量 API Contract；不变更 ORM/Migration/角色/依赖或已有 `/api/v1` 路径。
- 验收：默认 404、可信 Host/Session、项目角色/License Owner 复核、规范查询/独立游标、空页续页、最小响应、普通 POST 关闭及 Win11 隔离 PG/ASGI。
- 风险：无意扩大管理员读面、空页被客户端误判为结束、错误回显敏感信息、正式密钥缺失时错误开放。以独立路由/白名单投影、`has_more` 语义和默认不挂载控制。

## 实施与验证

新增 `GET /api/v1/projects/{project_id}/global-reference-candidates` 可选路由，严格仅接受 `page_size` 与 `cursor`；预验可信 Host 与 Session，调用 A03 Owner 再验证真实 Auth/License/项目成员及当前候选。每项只返回 GLOBAL 根/固定版本 UUID、审定标签、版本号和 `ELIGIBLE`；不调用管理员 GlobalReferenceRead，不返回 Root 原名、来源正文/路径/指纹或确认信息。允许过滤后的空页继续翻页；响应 `data`/`trace_id`、no-store。独立合同见 `docs/api-contract/solution-project-global-reference-candidates-v1-increment.md`。

HTTP 合同 2 项/11 子例通过。首次定向失败为未加 POST 哨兵时框架返回 405；补默认关闭的 POST 哨兵后定向重跑通过。Win11 隔离 PostgreSQL 18.6/真实合成文件与 ASGI 脚本退出 0：默认 404、不可信 Host 403、无 Session 401、跨项目 404、PM 空首页续到已发布标签、页大小不匹配 400、POST 404，响应严格五字段且不含原始名称/来源指纹。脚本复用 A03 角色、归档及来源夹具；真人客户确认与正式部署信任仍未验。后端全量 3492 通过、3 跳过、5386 子例通过。

兼容/升级/回滚：无数据库升级或旧 API Breaking Change；移除可选路由注入即可关闭新读面，既有发布/Audit/收据历史保留。下一项 A05 要在 Windows 显式平台模式使用独立正式游标密钥、受控存储根与真实 Session/License 组合，缺任一依赖失败关闭。Server2025、浏览器、20 并发、Gate3/发行未验；Debian13 实机依用户指令跳过。

TraceLink：Gate 2 API-04 → CR-SOL-018 → DEC-1152～1155 → 0158/管理员发布 → A02 Catalog → A03 Owner/游标 → 本 HTTP → Windows 组合/页面。
