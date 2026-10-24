# CR-CAP-007：Capability 条目 DEPRECATED 读写状态对齐

- 日期：2026-10-24
- 状态：`IMPLEMENTED / WINDOWS_11_SYNTHETIC_VALIDATED / PACKAGED_AND_RELEASE_PENDING`（按用户持续授权；原 Gate 2 冻结提交 `64cdf09` 不追写）
- 关联：`CAP-02-A05-P03-P02-A01`、`docs/api-contract/capability-read-v1-increment.md`、`CR-CAP-005/006`

## 事实与差异

正式 Capability 写模型 `CapabilityVersionCreateService._STATES`、前端写客户端与数据库约束均允许 `AVAILABLE/DEPRECATED/WITHDRAWN`。当前 `GET .../items` 的 `_ITEM_STATES`、前端 `CapabilityReadClient.parseItem` 仅允许 `AVAILABLE/WITHDRAWN`；合法 DEPRECATED DRAFT 写入后，管理员读/评审固定内容可能失败为 `SYSTEM_UNAVAILABLE`，普通用户也无法安全读取批准版本。P03-P01 页面因此暂时隐藏了 DEPRECATED，功能未完整。

## 方案与选择

- A（选定）：读取服务、HTTP 安全投影与前端解析器共同接受 `DEPRECATED`，保持原字段、路径、权限、分页和条目身份不变；前端编辑页只在三层读写合同均通过后开放状态。对严格枚举客户端属于可见 enum 扩展，随同版本协调更新，按 API Change Request 记录。
- B：禁止写入 DEPRECATED，会收缩现有写合同并与 DM/DB 状态不一致。
- C：读时改写为 WITHDRAWN，会歪曲正式历史业务事实。

选择 A。不扩大 Scope、模块化单体或权限；PROJECT API 不变。既有客户端若严格解析 enum，需升级前端/客户端后再写 DEPRECATED；当前受控 Pilot 前端与后端应同包发布，不能把增量变更描述为对一切客户端无感。

## 影响、迁移、回滚与验收

- 数据：无 ORM/Migration，现有合法 `DEPRECATED` 值不改写或回填；原冻结版本保留。
- 安全：读权限、License、Review 分配和来源证据重验不变；不得因 enum 扩展扩大未批准版本可见性。
- 回滚：若尚无 DEPRECATED 内容，可撤新读取支持及页面选项；若已有此状态的合法历史，不能直接回退到旧读取而使其不可读，须先保持新读取兼容或另做受控迁移，绝不静默改写为 WITHDRAWN。
- 验收：写入合法 DEPRECATED → 管理员条目 GET/Review 固定条目 GET 可回读原值；前端严格解析并显示；非法状态仍失败关闭；权限/分页/License 原矩阵回归；Windows 11 隔离 PG/HTTP，前端全量/typecheck/build。Server 2025、Debian 13 和固定候选包另验。

实施前仅登记差异，不将未完成状态标 PASS。随后按 `A01` 对齐读合同，`A02` 独立完成多条目编辑。

实施证据：`docs/progress/cap-02-a05-p03-p02-a01-deprecated-read.md`。Windows 11 隔离 PG/HTTP 合法条目写入、管理员与受分配 Reviewer 固定内容原值回读、批准及拒绝矩阵退出0；后端完整运行3781项（3跳过），前端完整1948/1948及typecheck/build通过。旧固定候选包未重建，正式安装/多平台/Gate不因本 CR 通过。
