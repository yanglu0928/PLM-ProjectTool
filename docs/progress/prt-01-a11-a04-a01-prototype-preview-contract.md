# PRT-01-A11-A04-A01：Prototype 资格预览兼容投影

日期：2026-10-08。状态：内部只读投影合同通过；运行路由白名单和 Registry 尚未开放 Prototype。

编码前检查：承接 Gate 2 冻结 `/api/v1`、`CR-PRT-005` 的兼容增量与 A11-A03 内部 Owner；本项只解决资格预览响应如何表达混合 `REQ-03`/`PRT-03` 主体，不改 Schema、权限、写请求或 Handover/Survey/Requirement 既有响应。验收是 Prototype 阶段专用、严格有序且非空的 `qualified_subjects[]`，每条只含主体类型/根ID/版本ID/批准轮次，保留最小 Evidence UUID 集和 Workflow ETag，不泄漏正文、指纹或文件路径。风险是旧客户端严格字段解析；本投影仅在 Prototype 新阶段返回，旧阶段字段集合不变。回滚为不注册新阶段，历史不变。

实现：预览内部 DTO 新增 Prototype 专用 `QualifiedChecklistSubject`；Prototype 聚合只输出 `qualified_subjects[]`、`evidence_refs` 和既有公共字段，不复用语义错误的 `requirement_version_refs`。旧三阶段响应序列化路径保持原状。当前 HTTP item_key 白名单仍关闭 Prototype，直到 A04-A02/A03 完成 Registry/Checklist/Transition 与前端客户端组合，避免半开放。

验证：定向 9 项/7 子例覆盖混合主体、旧响应合同、空/冲突变体失败关闭；后端全量 3239 项通过、3 项条件跳过、4791 子例通过。真实 HTTP/PG/浏览器未执行。兼容性/升级：无 Schema、依赖或迁移，随服务端同步代码；旧响应不变，新增 Prototype 响应是只读附加变体。

TraceLink：`CR-PRT-005` → A11-A03 Owner → A11-A04-A01 预览合同 → A04-A02 Registry/Checklist/Transition → A04-A03 HTTP/前端 → A05 Win11 PG/HTTP。
