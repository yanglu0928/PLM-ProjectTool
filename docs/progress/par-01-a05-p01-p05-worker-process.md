# PAR-01-A05-P01-P05 Parser 独立 Worker 进程

日期：2026-09-30；Phase 2；编码前检查，实施中。

当前 Phase：Phase 2 Platform Core。
当前 WBS：将已验 Parser 领取、解析、失败、取消和到期恢复链装配为单产品的独立受控进程；按维护模式停止新领取并收敛进程。
输入基线：Gate2 冻结架构/API/Schema，ADR-007 PostgreSQL Job/Outbox、ADR-011 SystemActor，PAR-01-A05-P01-P02/P03/P04 现有内部实现与真实 PG 验证。
前置任务：真实 Document 上传/Parser Job、Worker 单步、取消 Owner/到期恢复和候选调度内部 PASS；Gate3 尚未通过，不作正式发行声称。
涉及模块：Parser 应用层/进程入口、Platform 现有 Worker 数据库与受控身份来源、Document 现有存储、Jobs 租约；不改业务表。
涉及实体：Job/Lease/Attempt、Document ParseRecord/ResultRef、AuditEvent；不新增实体。
涉及 API：无 `/api/v1` 变化。
涉及权限：实际运行账户 Vault SystemActor 每次使用/状态提交前重新校验，同原始 User/Project/trace/目的来源；不授予系统身份普通用户权限。
验收标准：真实 PG18、当前 Windows 11 受控源与合成文档，在独立进程组合中跑通领取→解析→发布及取消到期恢复；身份材料变化、License 失效、数据库/文件来源错误、维护停止、信号和旧代竞争均失败关闭；限时停止无强杀承诺；wheel/全量回归通过。Server2025/Debian 另测，不外推。
风险：当前 Parser Owner 用构造时固定 UUID，启动时只读 Vault 不足以阻断长解析中身份材料变化。实施前需使关键发布/失败/取消事务在提交前重验同一受控身份；在此完成前不得将内部步骤直接接生产进程。无 Schema/API 迁移；回滚为停用 Parser 入口，保留已提交 Job/Audit 历史。

## A01 受控身份动态接线（内部 PASS）

`ParserSystemActorBinding` 支持既有内部固定 UUID 与正式可注入 `assert_current()` Port 二选一。准备输入的完整性审计、后代记录启动、结果发布、失败及协作取消均在状态事务开始捕获身份、写 SYSTEM Audit 并在 `commit` 前复核同一身份；到期取消恢复已有动态复核且只读确认也要求相同来源。固定 UUID 构造仅保留旧内部夹具兼容，独立进程必须传动态 Port。

Windows11 隔离 PG18/真实已提交合成文件/HTTP 用户取消：在 Audit 写入后切换合成受控身份，Document/Audit/Jobs 整事务零写；恢复原身份后当前活代成功取消。单元测试覆盖身份变化/失密、模糊双源拒绝、发布路径提交前变化。Python3.13 后端全量 1642（3 既有跳过）、wheel PASS；无 Schema/API/依赖变更。正式 Windows 运行账户 Vault、进程入口、License/Project 现时授权和 Server2025/Debian 尚未验证，P05 整体仍 INCOMPLETE。

## A02 前置：原用户与项目现时授权

编码前检查：Phase2/P05-A02-P01；输入 ADR007/011、CR-PAR-001/003、已验上传来源/Job Worker/受控身份；前置 A01 PASS。涉及 Auth 当前 User、Project Application 操作策略、License Guard 和 Parser 准备/发布，不动公开 API、Schema、Secret 或客户数据。验收为原 actor 与实际 Project/Scope/trace 绑定、撤权/归档/License 失效后不得发布、GLOBAL 仅部署管理员、清理终态仍可执行；风险是异步期间撤权导致原 Job 失败而非发布，按现有有界 Jobs 失败链处理。迁移/回滚及方案比较详见 `CR-PAR-003`。正式 Worker 组合在此通过前不装配。

结果：P05-A02-P01 Windows11 内部 PASS。`ParserCurrentAuthority` 经 Auth 当前启用 User、Project 新内部 `DOCUMENT_PARSE_PROCESS`（角色同上传）、License Guard 验原 actor/trace；GLOBAL 只允许部署管理员。`AuthorizedParserInputSource` 在每次准备/启动/最终发布的调用者事务中先验权再读不可变上传来源；这些 Parser 流程调整为先源/权限后 Job 锁，保持与用户取消 Owner 同向。取消/失败清理不依赖新授权口。

隔离 PostgreSQL18/实际合成上传的首代 Parser：User 停用时最终发布零写，Project 成员暂停时重新准备拒绝，License 失效时最终发布零写；恢复后相同当前租约发布唯一 ParseResultRef/Job SUCCEEDED。GLOBAL 管理员/项目四角色/归档/License 单元矩阵与后端全量 1646（3 既有跳过）、wheel PASS。合成 License/账户仅内部证明，正式信任锚和 Windows 独立进程/Server2025/Debian 尚未验；P05 整体仍 INCOMPLETE。异步撤权可耗尽既有有界 Job 尝试，后续运营策略需在 Worker 组合/Retry 任务明确，不得显示为解析成功。
