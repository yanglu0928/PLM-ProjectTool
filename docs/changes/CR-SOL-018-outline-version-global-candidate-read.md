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

## P06-A02-P02 前置核查

2026-10-09 核查 `GlobalReferenceReadService` 当前仅调用 `AdminPort.authorized_admin`；`SqlAlchemyGlobalReferenceReadRepository` 投影含 `Root.name`，而 GLOBAL 创建只验证名称格式，不证明其已被人工审定为可向项目成员展示。现有 `Reference` 当前资格/来源证明是内部最小端口，不提供可读标签；以截断 UUID 当标签虽不泄露正文，却无法让用户核对所选方案。故项目成员 GLOBAL 候选页面编码前置不满足，状态为 `PRECONDITION_BLOCKED`，不是 Gate/功能 PASS。先实施本 CR 的发布账本与管理员确认、再开放读面；这需要独立 Schema/Owner/API/Win11/页面任务。当前转做不依赖它的 OutlineVersion GET/LIST 与原操作恢复，保持 P06-PROJECT 子集可用。
