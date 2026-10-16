# AI-04-A06-P04-P04-A03 Document 规划期精确最小投影

日期：2026-10-03；状态：`PASS`（Windows 11 / PostgreSQL 18.6）；依据 CR-AI-016、DEC-726～730/736。该切片让既有 Document Owner 满足 Preview Plan Builder 的真实 Source Port，尚未修改公开 HTTP、Preview 持久化事务或生产组合。

`DocumentAIContentService.resolve_projection` 以 `EGRESS_PREVIEW_CREATE` 权限在同一短事务内选定当前成功 ParseRecord/ParseResult，读取并复核私有结果字节，生成 `minimum.document.text.v1` 最小投影，再复核数据库与 License。`AIDocumentContentOwner.resolve_projection` 将 Document 身份转换为无 locator/正文的 Plan Source 身份，同时只把最小投影字节留在短生命周期对象中。执行期 `resolve_identity/read_exact` 继续要求 `AI_TASK_EXECUTE`，权限没有被 Preview 角色扩大。

编码前发现 A01 合成 Builder 夹具仍使用非正式别名 `document-minimal.v1`，与既有 Egress/Document 正式策略 `minimum.document.text.v1` 不一致；本切片只修正该未装配夹具和新链引用，不改数据库历史或公开协议。

验证：新增单元1项并回归 Document/Builder 合计9项；Windows 11 一次性 PostgreSQL 18.6 与私有临时存储证明 CustomerManager 仅凭 Preview 权限可取得精确当前 ParseRecord 最小投影、执行权限仍拒绝、事务行锁阻止并发更新、投影摘要与正文隐藏正确且零 ContentPlan/Invocation。旧执行期 Document PG 验证同时重跑通过。后端全量 **2202项运行、3项既有环境跳过、无失败**；开发 wheel SHA-256 `2760da76b2fe311d5aabf5e3ef0222b3555497e7035a5354de17afc49a5f919a`。

首次新验证因在创建临时结果根之前初始化安全存储而失败；调整创建顺序后使用全新数据库和目录完整重跑通过，无产品数据影响。无 Schema、公开 API、依赖、持久化或网络变化；回滚为不装配并撤新投影入口。下一切片 A04 组合服务端 Builder、Preview 与 Content Plan Repository 为单一原子事务。
