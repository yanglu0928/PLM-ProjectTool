# SUR-07-A05：已批准交接问题的调研来源候选读取

日期：2026-10-25；状态：`WINDOWS11_HTTP_PG_PASS / PILOT_NOT_READY`。

|编码前检查|结论|
|---|---|
|Phase/WBS|Phase 2 / `SUR-07-A05`；仅新增当前已批准交接问题只读候选。|
|输入基线|Gate 2 原冻结 `64cdf09`、`CR-SUR-013`、`SUR-07-A04`；现有 HND GET 与 SurveyVersion POST 不改。|
|前置|交接分析/固定版本/Review 当前批准指针、项目 Session/License/权限 Owner 和 Windows 显式组合已存在；本项无需新 Gate。|
|模块/实体|Handover Owner/API/SQL 投影、Project 操作策略与 Windows 组合；`HandoverAnalysis/Version/Item` 只读。|
|API/权限|新 `SURVEY_HANDOVER_SOURCE_LIST` GET `/api/v1/projects/{project_id}/survey-handover-sources`，仅 ACTIVE 项目 PM/实施成员。|
|验收|当前 ACTIVE 分析的当前 APPROVED 版本且问题为 CONFIRMED/RESOLVED/ACCEPTED_RISK；最小字段、签名页、撤权/跨项目/历史/未批准拒绝；完整回归和隔离 PG/HTTP。|
|风险|固定行 ID/简短标题属于项目内信息；Owner 逐页当前授权、`no-store`、用途族签名与 Survey 写事务重证，选择后撤源仍失败关闭。|

实现为独立可选 GET，不给旧 HND GET 增字段；默认应用 404，Windows 显式
平台组合挂载。SQL 关联三层 ProjectId、ACTIVE 分析、精确批准指针和合格问题
状态；按固定行 UUID 升序 keyset 页。响应仅固定行/版本/分析/业务问题 ID、
标题、状态与 ProjectId，不含文档/Evidence 正文、路径或 AI 输入输出。

验收：新合同/Owner/游标及既有交接定向首先 63 PASS；首次完整后端回归因
Policy 数量与 Windows key resolver 调用期望变化出现 2 项测试失败，调整精确
策略断言并避免重复读取同一 Vault key 后重跑：`4101 passed, 3 skipped,
6153 subtests passed`。一次性 Windows 11 / PostgreSQL 18.6 HTTP 脚本退出0：
未批准空集，批准后固定行 ID 不等于业务问题 ID 且来源三 ID 精确；匿名401、
客户只读/跨项目/暂停成员404、恢复200、畸形/错页长 cursor400；keyset 前后位置，
第二个未批准/返回版本不混入。Alembic head 无新操作，临时数据库/进程清理。
首次隔离 PG 启动验证因 PowerShell 对 PostgreSQL 子进程句柄等待两次中断，
改为只等待 `pg_ctl` 本身并重跑成功；两份失活测试数据目录经确认无服务后清理。

无 Schema/Migration、License 粒度、外部依赖或客户数据外发。API 增量见
`docs/api-contract/survey-handover-source-v1-increment.md`；游标密钥复用决定见
`DEC-20261025-SUR-A05`。尚无前端选择器/调研版本创建、固定包 Edge 复验或
真人访谈确认；正式公钥/服务账户/法律、Gate 3～7、Pilot 与三平台 Release
继续 NOT_READY。下一 WBS `SUR-07-A06`。
