# CR-SOL-018：OutlineVersion 项目成员选择 GLOBAL 参考候选的只读边界

日期：2026-10-09。状态：实施前登记，依据 CR-EXEC-001 持续授权分析与实施；不追写 Gate 2 冻结提交 `64cdf09`。TraceLink：冻结 API-04 `SOL_OUTLINE_VERSION_CREATE` → CR-SOL-016/017 → P05 双 Scope 服务端 CREATE → 本 CR → 项目角色安全候选读取 → P06 页面/浏览器。

## 冲突及证据

冻结 CREATE 允许本项目 ProjectManager/ImplementationMember 引用当前 ELIGIBLE 的 PROJECT 或 GLOBAL ReferenceVersion，服务端 Owner 已可重证两种 Scope。现有 `/api/v1/global/reference-solutions` 列表/详情通过 `GlobalReferenceReadService.AdminPort.authorized_admin` 仅允许部署管理员，不能作为项目成员的候选数据源。把项目用户伪装成管理员、复用管理员会话或让用户手填 GLOBAL UUID，均破坏权限边界、来源可核查性和操作体验。该缺口仅影响浏览器候选选择，不否定已验的受控后端 GLOBAL CREATE。

## 方案与选择

- 不选择开放现有 GLOBAL 管理列表/详情给所有项目成员：详情含来源元数据，权限扩大过度。
- 不选择裸 UUID、静态导入表或前端缓存管理员结果：缺现时资格、无法安全核查来源。
- 选择先新增管理员显式发布的独立、版本绑定的非敏感项目候选展示标签与发布审计（未发布的现有 GLOBAL 行默认不可见），再新增项目上下文中的最小 GLOBAL 候选只读投影：先验证本项目当前成员的 Solution 写资格与 License；只返回已发布且当前可供候选的 GLOBAL 根/版本固定 ID、经人工审定的展示标签、版本号与状态，不返回原始名称、客户来源、正文、Locator、脱敏证据或管理员凭据。服务端最终 CREATE 仍重新证明当前资格、来源和人工确认；候选列表不是正式业务事实。标签生命周期、撤回、分页/游标签名密钥须独立测试，缺其中任一证明时失败关闭。

## 差异、风险、迁移/回滚与验证

这是相对现有管理员专用只读 API 的最小新增读面及发布账本；不改旧 API、CREATE 路径/角色或 License。发布账本须独立 ORM/Alembic 线性迁移，空/有数据 up/down/re-up 与非空历史拒降；旧 GLOBAL 行默认无发布，不回填为已审定。版本修订、资格撤回或确认过期须立即使旧发布不可用；撤回以历史事件记录，不物理覆盖。新路由默认不挂载，可关闭读面回滚，已发布/CREATE/审计历史不可删除。验证计划：管理员发布/撤回审计、项目 PM/IM 正例、Customer/暂停/跨项目/License 拒绝、GLOBAL 资格撤回/确认过期/旧版本不可见、列表分页/重放/响应不含原始名称或敏感字段、Win11 ASGI/PG 与浏览器；正式服务账户、Server2025 与 Gate3 独立验收。

在该读面通过前，P06 页面只能安全选择本项目 Section、当前批准 RequirementVersion 和 PROJECT ReferenceVersion；GLOBAL 选项保持不可提交，不能把项目内子集报告为完整 P06 PASS。Debian13 实机依用户指令跳过。

## P06-A03-P01 实施记录

2026-10-09 按 DEC-1148 增加线性 0157 GLOBAL 固定版本发布事件账本、ORM、封闭 DML Guard 与空/历史库迁移复验。旧行不回填；尚无管理员 Owner、公开 API 或项目端读面，因此本 CR 仍在实施中，P06 GLOBAL 前置仍阻塞。验证与回滚边界见 `docs/progress/sol-03-a04-p03-p03-p06-a03-p01-global-publication-schema.md`。下一项 A03-P02 先建设受权发布/撤回 Owner，再分项推进公开受控入口和项目候选读取。

## P06-A03-P02 实施记录

2026-10-09 按 DEC-1149 完成内部管理员发布/撤回 Owner 与线性 0158 受限 INSERT Guard；真实 Win11/PG18.6 来源、权限、重放、Audit 回滚和迁移验证见 `docs/progress/sol-03-a04-p03-p03-p06-a03-p02-global-publication-owner.md`。原 0157、Gate 2 冻结提交均保留。发布事件不自动向项目成员开放；当前 CR 仍在实施，后续管理员 HTTP、Windows 组合、项目最小读面和浏览器须分别验收。

## P06-A03-P03 实施记录

2026-10-09 按 DEC-1150 新增默认关闭的管理员发布/撤回 HTTP 命令及增量 API 合同，真实 Win11 ASGI/PG 发布、撤回、普通用户拒绝、幂等重放和最小响应验证见 `docs/progress/sol-03-a04-p03-p03-p06-a03-p03-global-publication-http.md`。默认和当前 Windows 生产组合仍未挂载，项目成员候选读面仍未开放；本 CR 不关闭。

## P06-A03-P04 实施记录

2026-10-09 按 DEC-1151 将管理员发布命令仅装配至 Windows 显式写模式；缺受控来源或安全端口失败关闭，默认/只读模式保持不挂载。Win11 隔离 PG18.6 工厂/ASGI/真实合成文件与后端全量证据见 `docs/progress/sol-03-a04-p03-p03-p06-a03-p04-global-publication-windows.md`。项目成员最小读面、正式服务账户和 Gate 3 仍待验，本 CR 不关闭。

## P06-A03-P05-A01 前置核查

2026-10-09 按 DEC-1152 锁定独立项目读投影、同事务当前来源证明与原始根有界分页/签名游标的分项路线；不复用含原始名称的管理员列表，也不扩大四角色普通读权限。静态证据与后续 A02～A06 拆分见 `docs/progress/sol-03-a04-p03-p03-p06-a03-p05-a01-global-candidate-read-precheck.md`。本项无功能开放，本 CR 仍在实施。

## P06-A03-P05-A02 实施记录

2026-10-09 按 DEC-1153 增加 GLOBAL 原始根有界扫描、同版最新发布过滤、最小标签投影及既有当前来源/确认证明复用。Win11 隔离 PG18.6 未发布→发布→撤回与空页续页证据见 `docs/progress/sol-03-a04-p03-p03-p06-a03-p05-a02-global-candidate-internal.md`。此项仅内部组件，未开放项目授权/HTTP，CR 仍未关闭。

## P06-A03-P05-A03 实施记录

2026-10-09 按 DEC-1154 新增项目上下文 PM/ImplementationMember 专用只读授权 Owner 与独立签名游标，当前 Session/License/成员重证后才调用 A02 Catalog。Win11 隔离 PG18.6 角色/归档/跨项目与空页续页证据见 `docs/progress/sol-03-a04-p03-p03-p06-a03-p05-a03-global-candidate-owner.md`。正式密钥、可选 HTTP/Windows 装配仍未完成，本 CR 不关闭。

## P06-A03-P05-A04 实施记录

2026-10-09 按 DEC-1155 新增默认关闭的项目 GLOBAL 候选 GET 与增量 API 合同，只投影人工标签及固定身份，允许空页续游标；真实 Win11 ASGI/PG 证据见 `docs/progress/sol-03-a04-p03-p03-p06-a03-p05-a04-global-candidate-http.md`。Windows 正式密钥/受控来源组合及浏览器尚未通过，本 CR 不关闭。

## P06-A03-P05-A05 实施记录

2026-10-09 按 DEC-1156 将项目 GLOBAL 候选 GET 仅装配至 Windows 两种显式平台模式，使用独立当前账户 Vault 游标密钥与受控 Document/Parse/Evidence 来源；缺安全依赖拒启动。Win11 隔离 PG18.6/ASGI、启动失败关闭、密钥备份恢复及后端全量证据见 `docs/progress/sol-03-a04-p03-p03-p06-a03-p05-a05-global-candidate-windows.md`。正式目标账户/Server2025、项目浏览器及 Gate 3 尚未通过，本 CR 不关闭。

## P06-A03-P05-A06-P01 实施记录

2026-10-09 按 DEC-1157 新增项目上下文专用 GLOBAL 候选前端读取客户端，严格五字段/游标/no-store 合同与空可见页续页；全量前端测试、类型检查和构建证据见 `docs/progress/sol-03-a04-p03-p03-p06-a03-p05-a06-p01-global-candidate-client.md`。客户端未挂页面，浏览器及正式环境未验；本 CR 仍不关闭。

## P06-A03-P05-A06-P02 实施记录

2026-10-09 按 DEC-1158 将 GLOBAL 项目候选完整有界分页与 PROJECT 候选并入草案创建页，任何来源读取失败均不开放新建；固定双 Scope 引用、刷新清空旧确认和原操作重试保留首稿。前端全量/构建证据见 `docs/progress/sol-03-a04-p03-p03-p06-a03-p05-a06-p02-global-candidate-page.md`。真实浏览器/PG、正式运行与 Gate3 待验，本 CR 不关闭。

## P06-A02-P02 前置核查

2026-10-09 核查 `GlobalReferenceReadService` 当前仅调用 `AdminPort.authorized_admin`；`SqlAlchemyGlobalReferenceReadRepository` 投影含 `Root.name`，而 GLOBAL 创建只验证名称格式，不证明其已被人工审定为可向项目成员展示。现有 `Reference` 当前资格/来源证明是内部最小端口，不提供可读标签；以截断 UUID 当标签虽不泄露正文，却无法让用户核对所选方案。故项目成员 GLOBAL 候选页面编码前置不满足，状态为 `PRECONDITION_BLOCKED`，不是 Gate/功能 PASS。先实施本 CR 的发布账本与管理员确认、再开放读面；这需要独立 Schema/Owner/API/Win11/页面任务。当前转做不依赖它的 OutlineVersion GET/LIST 与原操作恢复，保持 P06-PROJECT 子集可用。
