# TRC-01-A09-P02：Trace 创建原始三字段同事务入口与安全重放

日期：2026-10-02；Phase 2；结果：**内部 DOC-02 三字段/隔离 PostgreSQL 18 PASS，通用公开创建 HTTP 继续关闭**。输入冻结 API-02、DM-03、CR-TRC-002、A09-P01/DEC-20261002-620，Gate 2 原冻结提交不改。

`CreateTraceLinkRefs` 在同一命令事务中先验证当前 License、Session/CSRF 与 ProjectManager/ImplementationMember 当前项目权限，再以冻结原始 source/target 三字段与关系类型建立持久幂等指纹。历史同 Key 的 Receipt 必须对应 201 TraceLinkRef，且该 LinkId 仍属于请求项目；仅返回首次 LinkId，不声称它仍 ACTIVE，也不重证现在可能受限的端点。首次写入才调用显式注册的 `TracePublicEdgeResolver`（当前仅 DOC-02）在该事务中确定 Scope/Project，重证两端固定版本/当前权限，验受控关系无环，然后去重创建与 Audit/Receipt 同事务提交。原已解析内部入口保留，也补齐显式 License 与相同安全重放顺序。其他 Owner、GLOBAL/Owner Service 写路径仍关闭。

验证：新增/扩展单元覆盖来源失效后历史重放、改载荷同 Key 冲突、失效 License、Receipt 引用不属于项目、未知 Owner/非法输入、权限与 Audit/环失败回归。Windows 11 一次性 PostgreSQL 18 使用真实 Session/Document Owner：原始三字段同边去重、来源 File RESTRICTED 且原边 REVOKED 后同 Key 返回首次 LinkId、失效 License 拒绝重放、新 Key 不能从受限来源创建；原 Trace 图、撤销与替换 HTTP/PG 链回归 PASS，临时资源清理。后端 **1902 运行、3 跳过、无失败**；开发 wheel SHA-256 `939efcd3d2bcfce8413ddd9f19ad30621fc660d35f2c082098f82f37c2aeaad0`。这不是可用发行包。

兼容/升级/回滚：仅 Trace 内部 Application/Repository 的新入口和显式许可依赖；无公开 API、Schema/Migration、新依赖或旧数据改写。内部调用方须注入已有 RuntimeLicenseGuard；不装配原始引用入口即可停止新创建。既有关系/Receipt 不删除，已撤销关系历史不恢复。通用创建 HTTP 仍遵循 CR-TRC-002 方案 B，不因仅有 DOC-02 就正式开放；其余业务 Owner、正式目标账户信任、Server2025/Debian、性能/UAT/Gate 3 与可用程序包未完成。

Next：评估 Phase 2 余项与 CR-TRC-002 的真实 Owner 依赖顺序，优先推进不需要伪造业务 Owner 的可用路径；若当前阶段完整验收与后续业务 Owner 构成时序冲突，先登记 Change Request 再调整 Gate 序列。
