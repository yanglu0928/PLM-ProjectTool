# SOL-06-A12-P06：结构化专项修订安全前端

- 日期/版本：2026-10-16 / `0.1.0-dev.0`。状态：`STRUCTURED_SPEC_REVISION_FRONTEND_PASS`；本项是前端合同与构建验收，真实 Edge/HTTP/PG 留 P07。TraceLink：冻结 `SOL_SPEC_REVISE` → A12-P01～P05 → 本项。
- 编码前检查：复用 P05 已验证的 Windows 显式写入口、现有 Session/CSRF、当前 Requirement/Section/Evidence 候选和固定详情读取；不改变冻结 API、Schema、License 权益、角色或后端行为。修订只产生完整 replacement DRAFT，原版本保持不可变。
- 安全客户端：新增受 SessionClient 保护的 `:revise` 传输及严格回执校验；校验项目、前驱、DRAFT、版本号、固定来源、完整正文、空 Artifact、Location/no-store/Trace。网络中断或矛盾回执统一标记结果不确定，不生成新操作号；明确的版本/状态/幂等冲突单独呈现。
- 页面：固定详情仅向 ProjectManager/ImplementationMember 显示修订入口，客户成员只读。页面读取原固定版本并把四类受支持正文无损还原为中文字段；线性流程以外的分支或任何页面不能完整重建的载荷失败关闭，不展平、不丢字段。专项类型不可跨系列修改。
- 来源与恢复：仅当原 Requirement/Section 的根和版本都与当前候选完全一致、Evidence 仍合格时预选；失效历史来源不自动替换，提示后要求显式选择当前来源。发送前以当前用户/项目/前驱隔离保存完整正文和 Idempotency-Key；未知结果重进页面只能确认后按原正文/原 Key 重试。成功后定位新 DRAFT，绝不显示为已批准。
- 验证：修订表单/客户端/页面/详情入口定向 4 文件 17 项通过；前端全量 145 文件 1805 项通过；`vue-tsc`/Node typecheck 与 Vite production build 通过。构建仍报告既有主 chunk 大于 500 kB 警告，不影响本项功能结论，也未据此声称性能通过。
- 兼容性/升级：仅新增前端路由、页面、静态资源和现有 SessionClient 方法；无 Migration、后端部署参数、新依赖或旧数据升级。升级需重新构建/部署前端静态文件。
- 回滚：移除修订路由、详情入口、页面和客户端即可关闭 UI；服务端 P05 入口可继续独立受控使用。任何已经成功创建的修订版本、收据和 Audit 必须保留。
- 已知边界：真实 Windows 11 Edge→生产组合/PG、正式服务账户/公钥/License/Vault/ACL/CA、OutputArtifact、专项验证/送审、Windows Server 2025、Debian 13、性能、Gate 3、Pilot 和正式发行仍未通过。
- Next：`SOL-06-A12-P07` 在 Windows 11 以真实 Edge、构建后的 Vue、生产 FastAPI 和可弃 PostgreSQL 18.6 验证详情→修订→新 DRAFT→固定详情闭环、未知结果原号恢复、来源漂移和项目隔离。
