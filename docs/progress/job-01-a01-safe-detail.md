# JOB-01-A01：内部安全任务详情

日期2026-09-27 / Phase2 / INTERNAL_PASS（仅已验边界）；前置7a478e9/preconditions与CR-JOB-001先记录，原冻结64cdf09保留。项目Skill编码前核查已执行，HTTP/ETag/正式发行不在本子任务完成范围。

Changed：Jobs专属只读事实DTO/Repository/Application Service与显式Owner Registry；Project新增JOB_PROJECT_GET当前四角色只读锁定策略。同事务真实Session/User/Project成员锁、当前License、资源actor/project绑定，PM/IM可见受权任务元数据，其余成员仅原actor；Admin管理面不包含项目任务。Owner回读原Root/Acceptance/pair，最终Jobs快照重读变化拒绝。未知Owner/type没有默认许可。

Audit首个Owner策略通过Audit-owned get_created_for_job Port读原Acceptance，再核原Root/actor/scope/请求审计/Job-Outbox pair；SUCCEEDED必须原不可变Result源证据存在才返回AUDIT_EXPORT逻辑引用，不返回字节/下载权限。retryable=False为该Owner当前未实现公开用户retry命令的策略，不猜Lease自动重试能力；后续受控用户重试仍待实现。当前result类型仅Audit受支持，Document/其他Owner和完整JobView/ETag不得称已完成。

Files：Jobs application/authorized_read.py、infrastructure/read_repository.py；Audit application/job_read_projection.py、submit_export.py Port、infrastructure/export_submit_repository.py；Project authorization.py与相关tests；validation/job-01-a01-read/verify.py。Migration/API/依赖/升级：无；默认/生产Web应用未挂载。DTO不包含payload/idempotency/fencing/Lease/worker/路径/Secret/Session；安全progress/error/ETag与公开DTO仍待下一设计，不在API返回不完整合同。

Tests：11新unit、后端1143无失败/2既有权限跳过；同UOW、严格DTO、License/Session、四角色creator policy、scope/原绑定、未知Owner、Store/Owner异常脱敏、最终快照变化拒绝。实际Windows11/Python3.13/PG18临时库：双Scope实际PENDING→原领取/捕获RUNNING→原render/publish SUCCEEDED与ResultRef，PM/IM元数据/客户仅自身、停用User/停用Department/失效Session、Admin项目隔离、跨项目/不存在/actor源不一致拒绝；每次读/拒绝六业务表快照不变。明确合成License、实际Auth/Project/Repo/原文件发布，非正式信任/HTTP/20并发/其他平台证明。

失败保留：首次新增unit在调用前构造无效DTO抛出正确错误，但测试捕获位置错误导致1143中1error；修正测试边界后通过。首次真实验证误取ClaimedJob.worker_ref不存在，原fixture与生产类型核对后用同一已领取固定worker_ref构造命令，再完整真实复验通过；没有为测试改产品领取语义。

Result：内部已验详情PASS，CR-JOB-001整体IN_PROGRESS；未知Owner不可见不是通用产品Scope缩减，后续Owner需显式接线。原发布回归通过。Known Issues：公开GET/完整JobView/资源版本/列表cursor/POST/取消重试、Document Owner、正式公钥/账户材料、Gate3/UAT/完整包待。回滚撤新只读Port/策略/Repo/Service，旧写路径不改，保历史。Next：JOB-01-A02完整详情投影与GET合同（先分析ETag语义，不能以fencing/常数冒充取消版本），随后Windows显式装配与Audit POST。

最终开发wheel：`plm_project_tool_backend-0.1.0.dev0-py3-none-any.whl` 639533 bytes，SHA256 `2938a7c3180684a68ec99e09498b364c55d9d5260bad5a8d84a2ed5621fbf3ee`；只证明开发构建，不是客户可使用完整安装包。
