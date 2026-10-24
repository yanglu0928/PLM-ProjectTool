# CAP-02-A05-P04-P03-A02-P01：GLOBAL Capability Review 内部读取

日期：2026-10-24；状态：`INTERNAL_UNIT_PASS / PG_AND_HTTP_PENDING / PILOT_NOT_READY`。

|编码前检查|结论|
|---|---|
|Phase/WBS|Phase 2 / `CAP-02-A05-P04-P03-A02-P01`，`CR-CAP-005` 下仅做 `CAP-01` GLOBAL Review 当前管理员内部读取。|
|基线/前置|原冻结 API-02 PROJECT 路径不变；GLOBAL Review 核心持久化、Capability Version 送审、Session/License/当前 User 事实和 Review Snapshot Reader 已存在。|
|边界|只新增未装配服务及 GLOBAL Repository 严格 Scope 读桥；不开放 HTTP，不改变 Schema/ORM、PROJECT Review 或批准指针。|
|安全|License → 当前 Session → ENABLED User → 精确 `GLOBAL/CAP-01/DEPLOYMENT_ALL_V1` → 唯一首轮 → 当前 DeploymentAdmin 或本轮已分配 Reviewer → Capability Version 绑定；错 Scope/Subject/绑定失败关闭。只返回固定元数据快照，历史信息不构成当前来源/客户批准证明。|
|验收|8 项单元正负例及后端单元全量；真实 PG 和 HTTP 留给后续独立片，不宣称公开路径可用。|

新增内部 `GetGlobalCapabilityReview` 服务，读取后要求 Review 的 `subject_id/subject_version_id` 与 Capability Version 的 `review_ref/review_round_ref` 精确一致；Review Repository 新增仅接受 GLOBAL Scope 的读取桥与“恰好一轮”ID 查询。多轮或不可信快照失败关闭，不猜测轮次。返回 Review/Round 强 ETag 供后续 HTTP 传输层使用；未返回来源正文或伪造批准。

验证：新定向 8/8；项目已存在的完整单元集在含 pytest 的既有虚拟环境中 `3474 passed, 3 skipped, 4798 subtests passed`，2 个警告。初次直接用 `unittest -s unit` 启动导致 57 个 `unit.*` 导入错误；修正测试根后所选旧虚拟环境缺 pytest 导致 21 个导入错误；切换项目已有完整依赖环境后通过。以上属于测试调用/环境错误，不掩盖，产品代码未为此变更。未做本片隔离 PG、运行 HTTP、Windows 显式装配、浏览器或真人评审；Gate/Pilot/Release 均未通过。

2026-10-24 `A02-P02` 纠偏复验：依据冻结 Capability Reviewer 资格允许已启用且受分配的普通用户读取，未分配/停用仍拒绝；本片定向增至 10 项，后端单元全量 3483 通过/3 跳过。原 8 项管理员限定结论在先前 Git 提交保留，不再视为当前产品权限结论。
