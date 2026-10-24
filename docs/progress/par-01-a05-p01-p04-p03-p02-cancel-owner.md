# PAR-01-A05-P01-P04-P03-P02 Parser 用户取消 Owner

日期：2026-09-30；Phase 2；结果 INTERNAL_PASS，Gate 3 与完整发行仍未通过。

编码前检查：当前 WBS 只接通冻结 `JOB_PROJECT_CANCEL` 的 `document/DOCUMENT_PARSE` Owner。输入 Gate 2 API-03、CR-PAR-001/002、已验 P04-P01/P02 Worker 协作取消及 Migration 0050。前置具备，Gate 3 不因此通过。涉及 Project 授权、Document 固定上传来源、Jobs Job/Outbox/Lease/Attempt、Audit USER 事件、Platform 幂等收据和现有 Job Cancel Router；不增加路由或实体。权限为当前 Session/CSRF/License、当前项目成员且原上传创建者或 ProjectManager，部署 Admin 无项目旁路。

验收：当前真实来源及 ProjectId 严格绑定；PENDING/RETRY_WAIT 立即 CANCELLED、RUNNING 进入 CANCEL_REQUESTED、已终态检查不复活；`If-Match` 强版本与同 Key 原结果重放，Worker 终结后仍返回首次状态/版本；错 Key/跨项目/撤权/过期 License/CSRF 拒绝且无写；同事务 Audit/Job/版本/收据及末端故障回滚；真实 PostgreSQL/HTTP、后端全量和 wheel。风险为跨模块锁顺序、伪造 dispatch hint、现有取消历史未必有合法首 USER 事件；选择先当前权限/Document 实源、再 Jobs 锁绑定，历史不完整时失败关闭。回滚可卸载新 Owner 并保留 0050/历史，不删已提交取消事实。无生产数据外发或生产迁移。

Changed/Files：Project 新增 `JOB_PROJECT_CANCEL` 当前成员只读锁策略；Document `DocumentParseJobCancelOwner` 事务内重查 Session/CSRF/License、原上传创建者或 ProjectManager、Document Version/Upload Audit，再验证 Job/Outbox 实际绑定；Jobs 自有 Repository 处理三类可取消状态、首响应版本与已有取消历史；Audit 自有 Source 验证首 USER 请求/重放事件。Windows 显式写组合把 Parser Owner 接入已有 `POST /api/v1/projects/{project_id}/jobs/{job_id}:cancel`。无新路由、新 Migration 或新依赖；需上轮已验 `0050`。

Tests：`validation/par-01-a05-p01-p04-p03-p02-cancel-owner/verify.py` 使用真实合成上传/文件、PostgreSQL18、当前 Session/CSRF/Project/License 和现有 HTTP Router；PENDING、RETRY_WAIT、RUNNING、已终态检查、非创建者成员/跨项目/Origin/CSRF/License 拒绝、角色撤销后重放拒绝、同 Key 并发单一首事件、Worker 后当前 v3 仍重放原 v2、末端收据写后异常全部回滚均 PASS。Windows 显式只读模式 405、合成信任源写模式 200。运行中版本漂移测试直接调用 Jobs 当前租约确认，仅证明 HTTP 首响应快照；完整 Document/Audit Worker 取消确认另由 P04-P02 独立验证，不把该测试称为同一端到端执行。3 项新增 Unit、Python3.13 后端全量 1635（3 项既有环境跳过）、开发 wheel PASS；隔离随机数据库清理，PoC PG 恢复停止。

Migration/API/兼容性：沿用 `0050` 和冻结 `/api/v1`，没有本轮 Migration；原 Audit Export Owner 不变。生产 Schema 尚未迁移，正式运行须先按 CR-PAR-002 备份停写升级；没有正式 License 信任材料不宣称可部署。回退仅卸载新 Owner，保留已发生 Job/Audit/收据与快照。

Known Issues/Next：Parser CANCEL_REQUESTED 的租约过期/崩溃恢复、确认丢失证明与独立 Worker 守护进程仍待；终态前无 ParseRecord 的用户状态、跨 Job 主动 retry、Evidence 精确定位、POC-03 质量、Server2025/Debian 与完整包/Gate3 仍未关闭。下一项 P04-P03-P03。
