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

## A02-P02 编码前检查：有界 Worker 调度循环

当前 Phase：Phase 2 Platform Core。当前 WBS：PAR-01-A05-P01-P05-A02-P02。
输入基线：Gate 2、ADR-007/011、CR-PAR-003、已验 ParserWorkerStep 与到期取消 Sweep。前置任务：A02-P01 已通过；独立进程入口尚未装配。
涉及模块：Parser 应用层调度，不涉及新持久化实体、Schema、公开 API、角色或依赖。
验收标准：每轮最多一扫一领；取消候选不使正常 Job 永久饥饿；停止请求后无新扫描/领取；并发运行和未退出时资源释放失败关闭；故障不吞没、无强杀假设。以单元测试验证，随后才接真实进程组合。
风险：单步长解析无法即时中断，只能等待现有租约心跳和解析结束；进程退出不能将仍运行任务误报为安全静止。回滚为停用未接入的循环，无数据迁移。

结果：调度层 Windows11 内部 PASS。每轮一条到期取消候选及一个 Parser Job，双空闲有界轮询；停止时当前单步自然收敛，`quiescent` 拒绝活跃调度/执行。定向15、Python3.13 后端全量1649（3既有跳过）、wheel PASS。尚未接真实 Worker 组合、运行账户、OCR模型或数据库维护信号；因此 P05 独立进程及 Gate3 均未通过。

## A02-P03-A01 编码前检查：显式 Parser Worker 组合根

当前 Phase：Phase 2 Platform Core。当前 WBS：PAR-01-A05-P01-P05-A02-P03-A01。
输入基线：Gate2、ADR-007/011、CR-PAR-003、已验当前权限/Worker 单步/过期取消/调度层。
前置任务：A02-P01/P02 内部 PASS。正式维护停写栅栏尚缺，本子项不关闭 P03 或 Gate3。
涉及模块：Parser 进程组合根，既有 Auth/Project/License/Document/Audit/Jobs 公共 Port；不改变各 Owner 的表。涉及实体：只连接既有 Job/Lease/Attempt/Document ParseRecord/AuditEvent；不新增。涉及 API：无。涉及权限：必须注入动态 SystemActor、当前原 User/Project/License；OCR 必须是显式离线受检引擎，不允许隐式模型下载。
验收标准：只接受 PG18 当前 Migration 的 WorkerDatabaseRuntime、实际数据根、受控身份/许可/项目 Port、显式 OCR；缺一拒绝。组合后真实隔离 PG 与合成已提交上传运行一个 Job 并发布；Secret 不从 argv/env 进入工厂。单元、回归、wheel。
风险：正式 Windows 运行账户材料、OCR 配置供给、维护模式及 Signal 尚未接线；本子项只形成可注入组合，不宣称可发行进程。无 Schema/API/依赖迁移；回滚停用未挂载组合，保留 Job/Audit 历史。

结果：A02-P03-A01 Windows11 内部 PASS。组合根拒绝缺失或无效 Worker runtime/Migration/身份/License/本地数据根/离线 OCR 引擎；把现有 Auth、Project、Document、Audit、Jobs 和 Parser Port 接成一条真实流程。隔离 PostgreSQL18/真实已提交合成 PDF 的一次 Worker 调度发布唯一 ParseResultRef/Job SUCCEEDED；首轮旧夹具的假 PDF 因 `PARSER_PDF_INVALID` 正常失败，改用真实合成 PDF 后重跑通过。单元2、Python3.13 后端全量1651（3既有跳过）、wheel PASS。此集成验的是文本页，OCR 使用绕过初始化的内部假引擎，不是 OCR 模型/断网验收；正式目标账户和维护停写栅栏仍缺，不能关闭 P03/Gate3。
