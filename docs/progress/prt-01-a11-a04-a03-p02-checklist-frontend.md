# PRT-01-A11-A04-A03-P02：Prototype Checklist 前端安全写客户端

日期：2026-10-08。状态：前端客户端合同通过；页面和生产服务仍关闭 Prototype 写入。

编码前检查：依据 Gate 2 冻结的 Checklist 记录合同、`CR-PRT-005`、A04-A02 可选后端组合。仅扩展两个固定 Prototype item 的 Session 写边界与业务客户端；不改 Schema、服务端或权限。前提是当前 Workflow 快照属于同项目、当前 PROTOTYPE 阶段与强 ETag；服务端写时必须再次复验，前端资格预览不能代替。风险是未知网络结果重复提交，因此沿用原请求、原 Key、原 ETag 的单次传输与首回执语义。

实现：`PROTOTYPE_SCOPE_DECISIONS`、`PROTOTYPE_COVERAGE` 加入固定 item/stage 映射及 Session 私有 CSRF 写路径；Checklist 客户端继续验证 Evidence、状态、版本、幂等 Key 和响应白名单。首回执保留 `is_current_state_proof=false`。项目流程页的 `mayRecord` 仍仅允许旧三阶段，故本项不会在尚未验收的生产实例显示 Prototype 按钮。

验证：Session 写边界/Checklist 客户端定向 191 项，前端全量 101 文件/1602 项、typecheck、220 模块构建通过。真实浏览器、HTTP、PG、制品物理校验和并发待 A05。

兼容性/升级/回滚：无迁移或依赖变化，重建前端即可；撤新固定键映射可回滚，历史不变。下一项 P03 阶段推进客户端，P04 页面，再由 A05 真实验收决定生产开关。

TraceLink：`CR-PRT-005` → A04-A02 后端可选组合 → A03-P01 只读资格 → A03-P02 安全写客户端 → A03-P03/P04 → A05。
