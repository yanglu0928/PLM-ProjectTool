# RVW-01-A07 内部 PM Review identity 创建

2026-09-26；0.1.0.dev0；结果 WINDOWS_INTERNAL_CREATE_PASS；真实 Subject Owner/License 来源/送审/HTTP 未通过。

## 编码前检查

Phase 2 Platform Core；输入 AF-02/DM-02/API-02 REVIEW_CREATE、0034/CR-RVW-001 和 A06 创建前置。前置内部结构/设计已具备；仅内部身份创建，不做 Round/决定/正式业务状态。权限真实 Session/CSRF、当前 ACTIVE ProjectManager 和 Owner 管理资格；无 GLOBAL/admin 旁路。无新表/迁移/API/角色/依赖/架构变化。

验收：DRAFT 根创建、固定输入校验、未知 Owner 默认拒绝、并发同 Key 一次、异内容冲突、审计/收据故障全回滚、旧 Key 不绕过撤权与归档、后续 Review 状态变化不改首次 Ref。风险：Owner/License 合成只验证协议；真实 Owner/版本与客户资格未具备，不能装配生产公开路径。

## Changed / Files

- `review/application/create_review.py`：命令、窄 Owner Port、稳定不可变 CreatedReviewRef、同事务创建/审计/收据；Session/CSRF 不进入 repr；输入 version 参与指纹，不假造固定送审快照或业务 Audit version。
- `review/infrastructure/create_repository.py`：Review owned Core DRAFT insert、当前 Scope 共享锁读取 immutable 创建字段，永不直读写业务 Owner 表。
- `project/application/authorization.py` 与策略测试：REVIEW_CREATE 仅 PM/write，归档拒绝、无新增角色。
- `tests/unit/test_review_create.py`：8 项单位验收及拒绝/异常矩阵。
- `validation/rvw-01-a07-create/verify.py`：随机自建 PostgreSQL 隔离库，只清理自建目标。

## Tests / Result

Windows 11/Python 3.13 后端 **712 项无失败，2 项既有符号链接权限环境跳过**。新增 8 项覆盖同事务/commit、重放不重复 Audit/create、缺 Owner/错误主体绑定/非法 policy、非 PM/错误 Project proof、Audit/receipt 故障不提交、旧 Key 重新 Owner 授权与非 bool 真值拒绝、错误结果/输入/时钟/Key 和 token repr。

PostgreSQL 18.6 隔离验收 PASS：真实 Session/CSRF/当前 PM/Project、Audit 与通用 receipt。同 Key 两并发调用收敛为相同完整原始 Ref，一个 Review/一次 REVIEW_CREATED Audit/一 COMPLETED receipt，且没有 Round；错误 CSRF、非 PM 三角色、无成员部署管理员、跨项目、缺 Owner、合成 License 拒绝不改变八表/来源/完整审计/收据快照。

同 Key 异 version 冲突；重放被 Owner 撤权拒绝。Audit 故障在插入后全回滚；receipt 完成后故障使 Review/Audit/receipt 一并全回滚，不仅比较 count。通过合成 Schema helper 完成后来 APPROVED 轮后重放仍返回相同不可变创建 Ref（该轮不是实际客户批准）；新 Key 允许独立 Review，遵循既有无逻辑根唯一约束。归档 CREATE/重试拒绝，撤销 Session 拒绝。

RVW-01-A05 真 Session/Project 内部读、0034 Schema/空与已有数据 upgrade/down/re-up/metadata/拒绝/并发、既有 Workflow/Windows 双显式组合回归 PASS。开发 wheel SHA-256 `ad8967c5513209c72b8efa86855cc17d8c55f087a93e8bf30be7f36a2c62e118`，不是可用最终安装包。未运行 HTTP/实际 Owner/覆盖率/性能/Server 2025，Debian 13 暂不验证。

## Migration / API / Compatibility / Known Issues / Next

无 Migration/公开 API/依赖/角色/总体架构改变；需 0034，升级无新动作。可停用新服务回滚，保持 owned 历史/审计/收据；不自动清理生产数据。创建只记录逻辑身份，不建立 Subject Snapshot/身份锁，不能把构造/SQL 成功当送审或客户确认。正式 Owner/确认人资格/版本锁/审批命令/HTTP/Gate 仍待。

Next：RVW-02-A02 送审政策、确认人真实资格与 Subject Owner 固定快照/身份锁前置设计，再实现内部 start-round；持续交付目标未完成。
