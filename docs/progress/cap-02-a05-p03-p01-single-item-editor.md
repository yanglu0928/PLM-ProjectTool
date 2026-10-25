# CAP-02-A05-P03-P01：能力版本单条目编辑入口

日期：2026-10-24；状态：`FRONTEND_SINGLE_ITEM_PASS / MULTI_ITEM_AND_PACKAGED_EDGE_PENDING / PILOT_NOT_READY`。

|编码前检查|结论|
|---|---|
|Phase/WBS|Phase 2 / `CAP-02-A05-P03-P01`；只增加从当前基线到一条完整能力项的 DRAFT 版本编辑入口。|
|输入基线|冻结 `/api/v1`、`CR-EXEC-002`、`CAP-02-A05-P01` 拆项和 P02 严格版本 POST 客户端。|
|前置|固定 GLOBAL 文档/基线身份、GLOBAL Evidence CANDIDATE 创建与拒绝矩阵、版本命令客户端均已验证；正式 Evidence 资格仍须由真人确认，测试夹具不能冒充客户事实。|
|模块/实体/API|前端 Capability、Document、Evidence 当前元数据与既有版本 POST；无产品 ORM、Migration、后端 API 变更。|
|权限|当前 DeploymentAdmin Session；后端再次核验权限/License/固定来源和 `ELIGIBLE` Evidence。|
|验收标准|选择 GLOBAL ACTIVE STANDARD_CAPABILITY 的 AVAILABLE 固定版本；按后端规范计算来源集合 SHA 与基线一致，筛选同源 ELIGIBLE Evidence；提交前重读基线 ETag、文档状态/版本、Evidence 当前资格；创建仅 DRAFT，失败或结果不明保留原 Key/内容/ETag。分页和会话变化失败关闭。|
|风险|首片只提供一条能力项，单项上限 100 份文档；最多 500 份来源的基线需要后续多条目编辑器，不由本片宣称覆盖。前端即时校验不能替代后端原子核验。|

新增 `/admin/capability-baselines/{baselineId}/versions/new` 管理员页与详情入口，支持 GLOBAL 文档、固定版本和 Evidence 的独立分页；选定的证据必须在所选固定来源内且列表状态为 `ELIGIBLE`。提交前逐项重新读取当前证据状态和同源关系，并以 WebCrypto SHA-256 计算 `capability-source-set.v1` 规范身份，要求与当前基线 `source_collection_ref` 一致。版本 POST 的完整条目包含稳定 ID、代码、域/模块/功能、描述、边界、前置条件、接口引用、固定 DocumentRef 和 EvidenceRef；成功后仅为 DRAFT。不确定结果保留 SessionStorage 中原条目、基线 ETag、操作号，明确核对历史后才可同号重试。

发现现有后端写模型允许 `DEPRECATED` 条目，当前只读 API `_ITEM_STATES` 只接受 `AVAILABLE/WITHDRAWN`；若开放该选项，成功写入的条目可能在详情读取时失败。因此此页暂只开放可读的 `AVAILABLE/WITHDRAWN`，保留原后端/冻结 API 不变；作为独立 `CAP-02-A05-P03-P02` 合同差异登记，实施前需核查冻结状态枚举并按需记录 Change Request。不把这项限制说成完整多状态编辑能力。

验证：纯来源集合函数 2 项（含与 Python 冻结实现同值比对）；页面管理员/来源/资格/原号恢复 5 项，定向合计 7/7；前端全量 173 文件、1924/1924，typecheck 和 Vite build 通过。曾出现异步 WebCrypto 回调未被测试夹具立即等待的首轮定向失败，改为等待实际状态后重跑通过；未改产品逻辑来掩盖失败。当前没有新候选包、真实 Edge/PG 版本创建、真人资格/批准或正式信任证据，Gate/Pilot/正式发行仍未通过。
