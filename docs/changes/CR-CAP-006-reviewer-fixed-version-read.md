# CR-CAP-006：受分配评审人读取 CAP-01 GLOBAL 固定版本

- 日期：2026-10-24
- 状态：`APPROVED_FOR_IMPLEMENTATION / NOT_IMPLEMENTED`（依据用户 2026-09-24 持续授权；实施批准不等于验收）
- 关联：`CR-CAP-005`、`CAP-02-A05-P04-P03-A04-P02`、Gate 2 原 API-02/API-04 冻结提交 `64cdf09`

## 事实、差异与影响

`CR-CAP-005` 的 GLOBAL Review GET 只返回固定版本和决定元数据，不返回能力条目。当前通用 Capability Read 对部署管理员开放 `ADMIN_HISTORY`，对普通项目成员仅开放 `CURRENT_APPROVED`；普通但当前启用、受分配的评审人虽可读 Review 和决定，却无法查看本轮未批准的固定版本内容。直接增加前端批准操作会让合法 Reviewer 盲审，不能以 UI 文案或管理员代阅替代其本人核对。原冻结 Capability 目录权限和 PROJECT Review 路径保持不变。

## 方案、范围与优先级

- A（选定）：新增 Review 作用域的只读固定版本及条目分页 API，只在 `CAP-01`、`GLOBAL`、唯一首轮绑定、当前 Session/License、当前 DeploymentAdmin 或受分配且启用 Reviewer 下开放；Review 服务在同一读取事务内重验 Capability Version 的 Review/轮次绑定，读取该固定版本的条目、来源文档版本引用及 Evidence 引用。默认应用不挂载，Windows 显式写模式才开放；前端评审页必须在核对内容后才允许决定。
- B（未选）：把未批准 Capability Version 放开给所有项目成员，破坏 `CURRENT_APPROVED` 边界。
- C（未选）：仅展示评审元数据并允许点击批准，存在盲审风险，不满足人工确认要求。

新增 GET `/api/v1/global/reviews/{review_id}/fixed-version` 返回固定版本安全投影与数量、ETag；GET `/api/v1/global/reviews/{review_id}/fixed-items?page_size=...&cursor=...` 返回该版本能力条目安全投影，签名游标绑定当前 Session、Review/固定版本、页大小。条目仅元数据与既有文档版本/Evidence ID，不包括客户文档正文或 Secret。失效 Session、License、Reviewer 资格、Review/Version 绑定、错 Scope 均失败关闭。管理员可看本产品内部评审范围，但普通用户权限仅以本轮受分配资格为准，不改变通用 Capability 目录。前端需提示文档引用位置可跳转已授权的 Document/Evidence 页面；未实现跳转前不得宣称已完成文档定位。

## 风险、兼容、迁移、回滚与验收

- 风险：历史评审错误可见、未批准条目泄露、分页跨轮/跨会话重放、来源撤销后误信任。每页重证当前身份/精确绑定/License，游标 HMAC 和上下文绑定；决定服务仍在提交事务内独立重验来源与资格，内容 GET 不构成批准资格凭证。
- 兼容：只增 `/api/v1/global/reviews` 路径，不破坏 Gate 2 PROJECT API、Capability 通用目录或已有 CR-CAP-005 字段；不改 ORM/Schema/数据。与新前端同版本显式装配。
- 迁移：无数据回填或历史 Review 改写。旧客户端不调用新路径。
- 回滚：关闭新增路由及页面，保留 Review/Capability/Audit/收据合法历史；不自动撤销已作决定。
- 验收：内部 Owner/权限/分页/版本绑定正负例、Windows 11 隔离 PG18.6 实际 HTTP、匿名/未分配/停用/失效 License/错 Scope/签名游标重放拒绝；前端固定版本核对及 Edge 正负链另片；完整回归、Secret 检查、GitHub 同步。正式目标服务账户、真人批准与 Gate/Pilot 仍独立验收。

先执行 `A04-P02-A01` 服务/安全投影，再 `A02` 默认关闭 HTTP/Windows 组合，最后 `A03` 页面与浏览器；每片按独立 WBS 验收，不以本 CR 预先标 PASS。

## 实施记录

- 2026-10-24 / `A04-P02-A01`：固定 Version/条目只读服务按 Review 分配资格及双向引用同事务重证，限制每页 50 条；定向13/7子例、后端全量4090/3跳过/6136子例通过。HTTP/PG/页面仍未实现，见 `docs/progress/cap-02-a05-p04-p03-a04-p02-a01-fixed-content-service.md`。
