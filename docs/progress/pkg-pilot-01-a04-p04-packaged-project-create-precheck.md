# PKG-PILOT-01-A04-P04：新候选包内项目创建写链预检

日期：2026-10-24；编码前状态：`IN_PROGRESS / PILOT_NOT_READY`。

|检查项|结论|
|---|---|
|Phase / WBS|Phase 2 / `PKG-PILOT-01-A04-P04`；仅验证固定新非发行候选的真实 Edge 创建项目写链|
|输入基线|CR-EXEC-002，A04-P03-R1 候选 SHA `f5df4493d6c2241a882cda5b367ff69e6c80f366ed007e78ff5d5614ee61892c`；PRJ-01-A04 项目创建/Workflow 原子性已有独立验证|
|前置|固定候选新包的包内 PG18/Caddy/合成 License/Edge 登录与六入口 PASS；正式信任缺失但不阻塞一次性合成试验|
|模块、实体、API|仅新增验证器，不改产品；合成部署管理员、Project、默认 Department、ManagerMember、Workflow、Audit、幂等收据；冻结 Project create API|
|权限|测试账户在一次性库中被明确赋予 `DEPLOYMENT_ADMIN`，并明确选为首位负责人；不把部署管理员身份推定为自动项目成员。不上传测试密码/License 私钥或包体。|
|验收|Edge 独立登录，创建页面读取候选用户，提交一个新项目，页面确认并从项目列表再次读取；隔离 PG 回查恰一个项目、默认部门、项目经理成员、NOT_STARTED Workflow、单 Audit 与单持久收据；无浏览器异常，候选同 Hash、临时资源清理|
|风险|现有合成夹具先预置一个项目用于 Workflow 前置验证，必须按独立新项目编号核对，不能把预置数据当作浏览器创建结果。自签 TLS 和合成 License 不代表正式可信启动。|

本任务只扩大验收证据，不修改冻结设计/Schema/API。失败时记录并保留固定包，不能以原子性单元测试替代包内实际写链。

## 实测结果

固定候选 SHA `f5df4493d6c2241a882cda5b367ff69e6c80f366ed007e78ff5d5614ee61892c` 从已验暂存再次构建两份 22,194 件隔离布局。包内 PG18/Python API/Caddy/合成有效 License 和 Workflow GET/START/重放/CSRF/冲突/Audit 前置通过。一次性数据库仅对测试账户显式授予部署管理员，并复制其一次性测试密码凭据给新建的合成负责人账户；没有产生正式账户、私钥或外发数据。

真实 Edge 独立登录管理员，进入创建项目页，读取启用负责人候选，提交 `PKGEDGE1`/`Synthetic Browser Project`，获得页面确认；管理员项目列表不因部署角色自动显示新项目。退出后负责人重新登录，可在“我的项目”看到新项目并打开详情。浏览器固定标记 `PKG_PILOT_01_A04_P04_PROJECT_CREATE_EDGE_PASS`，8 个 API 响应无非 2xx、加载失败或运行异常。

隔离 PostgreSQL 回查恰一个指定项目，`created_by` 为管理员，恰一个 `DEFAULT` 部门、一个 ACTIVE `PROJECT_MANAGER` 成员、一个 `NOT_STARTED` Workflow，恰一条 `PROJECT_CREATED` Audit 和一条完成的 `V1_PROJECT_CREATE` 持久收据；管理员不是新项目成员。脚本退出0，候选 SHA 前后不变，48 个临时 Vault 引用复查为0、临时安装布局为0，PG/API/Caddy/Edge 进程均停止。原清洁暂存目录保留以供下一任务复用。

Changed：新增包内真实 Edge 项目创建验收器，产品代码/冻结 API/Schema 不变。Files：`validation/pkg-pilot-01-a04-p04-project-create/`、本记录、版本/状态说明。Migration/API/权限：无产品变更，测试中明确授予一次性管理员角色。Tests：语法检查、固定候选完整性/HTTPS/合成 License/Workflow、真实 Edge 创建与双账户读取、PG 原子事实和临时资源清理 PASS。Result：`SYNTHETIC_PACKAGED_PROJECT_CREATE_EDGE_PG_PASS / PILOT_NOT_READY`。Known Issues：仅证明项目创建，交接→调研→需求→原型→方案→计划的实际写链未验；正式公钥/服务账户/CA/法律、离线安装升级、UAT和 Gate 开放。Next：`PKG-PILOT-01-A04-P05` 检查交接分析的实际用户创建入口和包内数据流；不把已存在的空列表页面等同业务可用。
