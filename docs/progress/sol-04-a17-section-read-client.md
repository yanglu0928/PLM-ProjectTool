# SOL-04-A17：Section 独立安全只读客户端

日期：2026-10-09。结果：`SOL_04_A17_SECTION_READ_CLIENT_PASS`；仅客户端与合同测试，Section 页面/浏览器未验。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / SOL-04-A17。
- 输入基线：Gate 2 冻结 API-04、A08/A14 Section GET/LIST HTTP、A15 Windows 显式组合和 A16 拆分；前置满足。
- 模块/实体/API/权限：Solution 前端 `SectionReadClient`；Section 身份与所属 Project/Outline，GET/LIST 不改冻结 API。最终项目成员、License/Session 仍由服务端复验。
- 验收：GET 同项目/Section/强 ETag 绑定；LIST 项目内严格投影、升序/游标/页长；同源凭据、无缓存、Trace/媒体类型及错误失败关闭；合同与前端回归/typecheck/build。
- 风险：把批准版引用误当正文、与 Outline cursor 串用、跨项目投影泄露或不可信响应被 UI 展示。

## 实施与验证

新增独立 `SectionReadClient` 与 `SectionSummary/Current/Page` 类型；仅接受 Section 固定字段，详情额外 `created_by`，拒绝正文或未知字段。验证 canonical 非零 UUID、同项目/指定 Section、键/时间/状态/强 ETag、签名游标表面格式和每页 UUID 升序。GET 用同源 Cookie/no-store、JSON/no-store、响应 Trace Header/Envelope 一致性，详情要求 Header ETag 与数据相同；只映射状态匹配的已知会话、License、不可见错误，其余失败关闭。客户端不自行判断批准指针是否真的已审，依赖后端 Owner 复验；UI 后续仍需显著声明边界。

定向合同 `6 passed`；前端全量 `114 files, 1667 passed`；`pnpm --dir apps/frontend build` 包含 typecheck/build，退出 0。构建原有大块提示，未作为本项阻断。无数据库、后端或浏览器测试（本项范围不涉及），A15 真实 PG/ASGI 证据不替代后续 UI 验收。

兼容/升级/回滚：无 Schema/Migration、依赖、冻结 API 或既有页面变化；撤下新客户端可回滚，Section 历史不变。下一项 `SOL-04-A18` 页面与 Outline 入口/Router；A19～A21 另行施工。TraceLink：Gate 2/API-04 → A14/A15 → A16 → A17 → A18。
