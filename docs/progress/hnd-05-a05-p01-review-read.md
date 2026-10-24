# HND-05-A05-P01：交接 Review 详情读取接线

日期：2026-10-25；状态：`HND_05_A05_P01_REVIEW_READ_PG_HTTP_PASS / PILOT_NOT_READY`。

|编码前检查|结论|
|---|---|
|当前 Phase/WBS|Phase 2 / `HND-05-A05-P01`；只开放已送审 HND-02 在冻结 `REVIEW_GET` 的安全详情读取，不实现 Reviewer 决定或列表发现。|
|输入基线|Gate 2 API-02 `REVIEW_GET`、`docs/api-contract/review-read-v1-increment.md`、HND Review Owner 与 HND-05-A04-P03 包内送审实证。|
|前置|交接 HND-02 已通过原子送审建立 PROJECT Review/首轮；Windows 写组合已注册 HND-02，但独立只读 Registry 目前只注册 SOL-03/05/06。|
|涉及模块/实体|Review 只读 Registry、Handover Subject Owner/Analysis/Version；不读取问题正文，不改 Review/交接表。|
|涉及 API|保持 `GET /api/v1/projects/{project_id}/reviews/{review_id}` 既有路径和严格响应；仅增加 HND-02 主题受控资格，默认应用仍不挂载。|
|涉及权限|现有 License、Session、`REVIEW_GET` 当前 ACTIVE Project 成员不变；Handover Owner 同事务复核 ACTIVE 分析及精确历史版本的同项目归属，未知或无权一律 404。|
|验收标准|Unit 的当前身份/固定版本/无权与异常闭合，API 既有合同回归，Windows 11 隔离 PostgreSQL/真实 HTTP 正向和跨项目/离开项目/错误版本负例；无额外业务写。|
|风险/回滚|读取主题集合扩大，必须显式接线并记录；不把送审或读取当客户批准。无 Migration/API Breaking Change；停止注册 HND 只读 Owner 可关闭新增能力，已存在 Review/Audit 历史不删除。正式信任、Pilot/Gate/Release 不因此通过。|

前置满足，可进入本 WBS 编码。现有通用前端 Review 客户端也只识别 SOL-03/05/06；
本片后另作前端合同和真人操作替身的独立任务，不以后台读取成功推定页面可用。

实现仅为 Handover Owner 增加 `authorize_read`，当前项目成员经既有 Reviewer 资格服务
重验；持久层以共享锁确认 ACTIVE Analysis 与精确历史 Version 的同项目归属。Windows
显式 `REVIEW_GET` Registry 才注册 HND-02；列表 Registry 和写 Owner 不随之扩大。
冻结 GET 响应/权限、Schema、License 与默认应用开关均未改变。

定向 Owner/组合/Review 读取/API 合同共 31 项及 5 个 subtest 通过。首次 PG 运行因
旧夹具默认端口无服务在连接前失败，第二轮自启一次性 PG 时输出管道被数据库子进程
持有而阻塞；两轮均未计通过。夹具改为独立 D 盘合成 PG18 且不捕获启动进程管道，
手工停机并删除卡住的专用目录后重新验收。最终 Windows 11 空库迁移/Alembic check、
HND 原有创建/送审/批准/撤回 HTTP/PG、HND-02 `REVIEW_GET` 实际 HTTP/PG 退出 0：
负责人和当前客户成员 200，固定主题/首轮版本及 `HANDOVER_ALL_V1` 精确回显；
匿名 401、跨项目 404、临时暂停成员 404，恢复后 200；持久层错误 Version 不存在。
测试数据库、端口和目录均已清理。后端全量 4,097 通过、3 跳过、6,149 个
subtest 通过。wheel 构建另尝试当前测试 venv（缺 pip）及系统 Python
`--no-build-isolation`（缺 setuptools backend）均未成功；本片不据此宣称已入包，
后续固定候选须使用受控构建环境重建并复验。
验收脚本接收 `--pg-bin` 与 `--temp-root`，不依赖固定本机解包目录；复跑时应提供
PostgreSQL 18 的 `bin` 目录和专用临时根。修正参数化后整链又退出 0。

仍未完成前端 HND-02 投影/决定页面和包内 Edge、真人客户确认、正式信任/安装、
UAT/Gate 3～7/Pilot/Release。下一片 `HND-05-A05-P02` 只处理交接评审前端安全客户端；
随后独立完成页面/Edge/PG 包内组合，不把本片读取当批准。
