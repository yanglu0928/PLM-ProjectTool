# 项目状态

|字段|当前值|
|---|---|
|Current Phase|Phase 2：Platform Core|
|Current WBS|`AUD-03-A06-A04-P03-A07-P01 Jobs事务内续租`（实际技术事实/并发/回滚/到期接管PASS；Audit受权心跳/调度待）|
|Current Status|PHASE_1_COMPLETE / DOC_03_A03_P04_P04_PRECONDITION_BLOCKED / DOC_02_A02_P01_INTERNAL_PASS / DOC_02_A02_P02_PRECONDITION_BLOCKED / DOC_03_A04_A03_P04_P03_CONTENT_HTTP_PASS / DOC_03_A04_A04_P01_JOB_SCHEMA_PASS / DOC_03_A04_A04_P02_JOB_LEASE_PASS / DOC_03_A04_A04_P03_OUTBOX_PASS / DOC_03_A04_A04_P04_P01_PARSE_QUEUE_PASS / DOC_03_A04_A04_P04_P02_COMMIT_INTERNAL_PASS / DOC_03_A04_A04_P04_P03_P01_ABORT_STATE_PASS / DOC_03_A04_A04_P04_P03_P02_PRECONDITION_BLOCKED / DOC_03_A04_A04_P04_P04_A01_FINALIZE_HTTP_PASS / DOC_03_A04_A04_P04_P04_A02_WINDOWS_COMPOSITION_PASS / DOC_03_A04_A04_P04_COMMIT_ABORT_IN_PROGRESS / DOC_01_A02_INTERNAL_PASS / DOC_01_A03_P01_CURSOR_PASS / DOC_01_A03_P02_HTTP_CONTRACT_PASS / DOC_01_A03_P03_HTTP_DB_PASS / DOC_01_A03_P04_WINDOWS_COMPOSITION_PASS / DOC_01_A04_P01_VERSION_INTERNAL_PASS / DOC_01_A04_P02_VERSION_CURSOR_PASS / DOC_01_A04_P03_VERSION_HTTP_CONTRACT_PASS / DOC_01_A04_P04_VERSION_HTTP_DB_PASS / DOC_01_A04_P05_WINDOWS_COMPOSITION_PASS / DOC_01_A05_P01_VERIFIED_SNAPSHOT_PASS / DOC_01_A05_P02_DOWNLOAD_SOURCE_PASS / DOC_01_A05_P03_PREPARE_DOWNLOAD_PASS / DOC_01_A05_P04_DOWNLOAD_HTTP_PASS / DOC_01_A05_P05_WINDOWS_COMPOSITION_PASS / DOC_01_A05_P06_DISCONNECT_CAPACITY_BOUNDED_PASS / DOC_03_A04_A04_P04_P03_P02_A01_GATE_ADAPTER_PASS / DOC_03_A04_A04_P04_P03_P02_A02_P01_CONTENT_GATE_PASS / DOC_03_A04_A04_P04_P03_P02_A02_P02_COMMIT_GATE_PASS / DOC_03_A04_A04_P04_P03_P02_A02_P03_ABORT_GATE_PASS / DOC_03_A04_A04_P04_P03_P02_A03_P01_READONLY_INSPECTION_PASS / DOC_03_A04_A04_P04_P03_P02_A03_P02_A01_STORAGE_STEP_PASS / DOC_03_A04_A04_P04_P03_P02_A03_P02_A02_INTERNAL_CLEANUP_PASS / PLT_02_A07_P05_A09_CEREMONY_PENDING / PHASE_2_IN_PROGRESS|
|Completed Phases|Phase 0 技术验证（`COMPLETE_WITH_APPROVED_ALTERNATIVES`）；Architecture / Data Model / DB Schema / API Contract Freeze；Gate 2 `APPROVED`；Phase 1 基础工程|
|Completed WBS|POC-01、POC-02、POC-04、POC-05、POC-06、POC-08、POC-09 已按验证或批准例外收口；POC-03 以批准替代方案收口；Gate 1 已通过；AF-01～AF-05、DM-01～DM-06、SC-01～SC-05、API-01～API-05 PASS；Gate 2 已批准并冻结四份基线；1.01～1.09、PLT-01-A01～A03、PLT-02-A01～A06、API-RUNTIME-01（仅 Win11）、PRJ-03-A01～A04、AUD-01-A01～A03、AUT-01-A01～A03、AUT-02-A01～A05、AUT-03-A01～A06、AUT-03-A07-P01～P03（P02/P03 仅 Win11）、AUT-03-A08～A10（仅 Win11）、PRJ-01-A01～A06、PRJ-02-A01～A04、LIC-01-A01～A04、LIC-02-A01～A05、LIC-03-A01～A03、DOC-03-A01、DOC-03-A02（限定范围）、DOC-03-A03-P01～P03（P03 内部合成验证）、DOC-03-A03-P04-P01～P03（内部合成验证）、DOC-03-A04-A01（Schema 验证）、DOC-03-A04-A02（内部合成验证）、DOC-01-A01、DOC-02-A01、DOC-02-A02-P01（内部合成验证） PASS|
|Blockers|DOC-03-A04-A04-P04-P03-P02 内部清理/崩溃对账已在隔离库/临时文件验证；A03-P03 证实 Server 2025 VM 可启动但远程管理/桌面端口未连通，正式旧版进程停写、目标账户 ACL 与恢复演练未完成，生产物理删除入口仍关闭；AUT-03-A07 Windows 11 合成端到端已通过，Server 2025 目标运行账户/HTTPS 代理与 Debian 安全凭据来源未验证；PLT-02-A07 显式生产写组合已合成验证，正式发行公钥、目标账户可信时间/游标/Secret 主密钥供给、Server 2025 恢复演练仍待；POC-03 质量失败继续阻塞 Gate 3/UAT，Server Office、Debian 未验证和 Ghostscript 发行合规继续作为 Release 约束|
|Pending User Decisions|LIC-03-A03 方案 A 已确定；当前无人工决策待办。客户数据外发、付款/额度重置和不可恢复生产操作不在持续授权内|
|Architecture Version|`ARCH-CANDIDATE-V1`；Gate 2 原冻结内容 `64cdf09`，License ADR-006 经用户批准 CR-LIC-001 修订|
|Data Model Version|`DATA-MODEL-CANDIDATE-V1`；Gate 2 原冻结内容 `64cdf09`，DM-02 License 授权粒度经用户批准 CR-LIC-001 修订|
|DB Schema Version|`DB-SCHEMA-CANDIDATE-V1`；原冻结64cdf09保留；增量至`20260926_0042` 审计不可变成功结果（CR-AUD-002），0001～0041历史不改写；无生产迁移|
|API Contract Version|`API-CONTRACT-CANDIDATE-V1`；API-01～API-05 PASS，Gate 2 已冻结（内容提交 `64cdf09`）|
|Test Summary|P03-A07-P01 Windows11/Python3.13后端968项无失败（2既有环境跳过）；5新unit/真实PG双Scope技术续租期限一致、并发串行、未commit/后置异常整UOW回滚、错Worker/fence/成功/取消/实际到期与接管旧代拒绝新代续期，原发布完整回归/wheel成功。只是Jobs技术Port，Audit受权心跳/调度/正式材料/性能/发行待|
|Next WBS|AUD-03-A06-A04-P03-A07-P02：当前Audit授权与原Root/受理pair绑定的短事务续租，然后真实调度/Worker循环/失败取消恢复与提交Jobs HTTP；技术Lease不充当权限、未验Worker前POST关闭。质量/Gate/正式材料/完整Scope保留，Server2025未验、Debian13暂缓|

## 自动执行策略

- 模式：按 `AI自主执行与最小人工确认规则 V1.1.md` 持续自主执行至可用程序包；偏差先建立 Change Request，再实施、验证并同步 GitHub；Gate 按实际证据关闭，不虚报。
- 代决策授权：用户 2026-09-24 明确授权原方案不兼容时自主分析并执行解决方案，默认接受，不再逐项询问；范围和安全边界见 `docs/changes/CR-EXEC-001-continuous-delivery.md`。客户数据外发、付款/额度重置、不可恢复生产操作和伪造客户确认不在授权内。
- 周额度规则：用户已于 2026-09-23 取消自动检查和 20% 停止线；后续仅在用户明确要求时查询。额度重置或购买仍需逐次明确确认。
- GitHub：允许在当前 Scope 和正确分支内自动 fetch、commit、push；禁止 force push、直接提交 main、覆盖未知远端修改或提交 Secret/客户数据。

## 最近检查点

- P03-A07-P01补独立Jobs caller-UOW续租，原checkpoint只读/通用Service不改；真实PG两Scope一致期限/并发/后置失败回滚、取消/实际到期与真实接管旧代拒绝新代续期PASS。968无失败（2环境跳过），原发布/wheel成功；无Schema/API/依赖，不宣称业务授权或调度完成。下一项P02 Audit原源/当前权限短事务心跳，正式包/Gate仍待。

- P03-A06-P03将四GET装入Windows两显式平台模式，实际PG已发布来源/完整文件/当前Session与Scope/许可/坏文件验证、三装配故障不发布dispose通过；963无失败（2环境跳过），旧WindowsAudit/上传Finalize和原子发布/wheel成功。default/login-only/POST404；正式材料/账户/三平台/代理/性能与完整包待，下一项Worker协调/心跳核查。

- P03-A06-P02两个opt-in内容GET真实当前Session/完整快照/二次授权、安全附件、有界名额与Response/线程资源Owner通过；prepare/read取消不提前释放活跃工作，start/body失败/未启动生成器取消close复用实测。962无失败（2环境跳过）、实际PG/文件双Scope空/260及撤权/坏文件Audit/旧发布/wheelPASS。无Migration/依赖，默认404，生产组合/代理/性能与正式包仍待。

- P03-A06-P01实施前CR-AUD-003/增量契约保原冻结，两可选结果GET真实当前Session/实际成功源/Scope安全投影PASS；955项无失败（2环境跳过），真实PG双Scope/权限/无写与原子发布回归/wheel成功。无Migration/依赖，默认404，内容响应/断连取消/P03生产组合尚待，不宣称完整包或Gate通过。

- P03-A05实际当前Session/Scope访问成功来源与UOW外完整私有快照、二次授权、坏文件受权最小Audit通过；951项无失败，Storage128MiB物理边界/普通100MB保持与旧下载/恢复发布回归PASS。无HTTP/Migration/依赖，下一项增量结果/下载HTTP契约与生命周期；正式材料/三平台/Gate/完整包未完成。

- P03-A04-P04真实来源command-only恢复/内部成功重放，当前权限/原代Lease或真实Job成功来源→全Hash→再次授权；三形状恢复、并发重放无写、确认丢失/坏缺来源/撤权取消过期拒绝与接管原capture新file保旧final通过。945项无失败，完整发布/旧Jobs/File回归及wheel成功。中断模拟、HTTP/当前Session内容访问/心跳/正式账户/三平台及完整包仍待；下一项P03-A05。

- P03-A04-P03实际原子发布成功，元数据/发布审计/结果/Job单UOW及四写后故障回滚、撤权取消到期/失身份/实际取消两锁顺序通过；939项无失败、三真实回归/开发wheel成功。文件Hash/提升不持DB事务，失败final仍私有/STAGED，尚无受控恢复/授权成功重放/HTTP/心跳；下一项P04，不标可用完整包/Gate。

- 原子发布核查受控SystemActor实际来源缺失，按Skill停止受影响编码，实施前登记CR-AUT-004并完成独立AUT-04-A01只读来源/临时Vault恢复；无User/角色/Schema/HTTP改变。934项无失败；下一项恢复实际原子发布并使用公开SystemActorPort，正式账户供给仍属Release材料，不把临时身份当生产验收。

- P03-A04-P02真实受理/固定capture/当前权限/Lease/plan到128页源与私有暂存文件，所有write/fsync/hash不持UOW，完整尾验及页间撤权/取消/到期/故障私有、新代独立file通过；930项无失败。尚无metadata/final/结果/Job成功/发布Audit，下一项全链路原子发布，不能宣称交付。

- P03-A04-P01 Jobs caller-UOW完成原pair/完整当前Lease→技术终态、真实双Scope/并发/取消两锁顺序/检查后到期与接管/不自提交及caller真实Audit后故障回滚通过；926项无失败。Export/权限/成果File/SystemActor未接，合成marker不能证明发布；下一项实际有界文件Worker渲染。

- P03-A03-P04 own结果record/get实际来源/规范bytes重核、原结果重放/真并发单次变化/后置Audit+结果整UOW回滚通过；919项无失败，0042/实际Worker计划/renderer/文件元数据回归PASS。跨Owner Job/File/Lease/SystemActor仍合成，不冒充真正发布，下一项Jobs caller-UOW完成Port。

- P03-A03-P03/0042不可变唯一结果，own计划/发布Audit绑定、完整规范manifest重建字节/SHA256、空与非空规则及真实历史down写锁通过；914项无失败，计划/旧文件元数据回归PASS。Job/File/SystemActor合成，内存清单不是正式Worker/物理文件/原子发布证明，下一项own结果Repository。

- P03-A03-P02在真实受理/claim/固定capture/当前权限/Lease下登记或读回原代计划；双Scope/真并发、新代独立file、实际撤权/取消/到期/写后故障和40P01限次整UOW恢复通过；912项无失败。无文件/成功状态，下一项不可变结果Schema，完整交付仍待。

- P03-A03-P01/0041不可变渲染计划源绑定、单Job/token单file、新代次独立文件及真并发/历史down写锁拒绝通过；904项无失败。合成Job/Lease refs不能证明真正Worker，下一项P02实际公共Port/当前权限登记。

- P03-A02-P02完成Document owned caller-UOW元数据，原内容/归属/首次事件重核、并发单次变化及共享锁、caller真实Audit故障全回滚；902项通过。合成Export不冒充真Root/权限/Lease，AVAILABLE不是成功结果，下一项持久尝试/结果Schema。

- P03-A02-P01完成独立generated/audit存储，bounded sink/private partial/flush/fsync/Hash读回/不覆盖及真实linked/final恢复、普通扫描隔离；14项新增/897后端通过。只有物理原语，元数据/真正Worker权限与Lease/发布/下载待，不宣称文件提升即交付。

- P03-A01/0040完成内部FileObject用途/归属，旧DOCUMENT完整保留；同PROJECT普通Version/Upload误绑与旧通用状态/发布拒绝，专用身份/内容/状态和delete/truncate历史保护，实际down竞争表锁/历史拒绝通过。合成owner不冒充真实Export/Lease/文件，P03-A02公共Port/存储待。

- P03先记录CR-AUD-002/ADR010：内部FileObject用途/DEPLOYMENT归属、Audit自有尝试与唯一结果，普通文档/业务Output范围不改；文件I/O与短事务数据库发布分开，权限/Lease/取消重核，按实际来源恢复。仅变更设计，无Schema/生产代码/HTTP验收，下一项P03-A01。

- A04-P02真实入口探测确认DEPLOYMENT locators/PublishFile拒绝，FileObject ORM仅GLOBAL/PROJECT；普通OutputArtifact依赖PROJECT/Plugin/DocumentVersion不可伪造。核查完成不代表发布可用，下一项先CR。不改Schema/API/生产数据，4项只读探测通过；详见对应进度记录。

- A04-P01固定member源显式安全列接canonical JSONL/独立manifest，逐条Scope/全筛选/位置/完整成员hash重核，写入大小/短写/源失败不返回成功；source关闭、sink由Owner管理。真实两Scope内存字节/新事件排除/无hint与数据库无写通过，未宣称落盘/Artifact/权限发布或空间性能。既有发布仅GLOBAL/PROJECT，DEPLOYMENT归属留P02核查不重标绕过。

- A06-A03将实际提交/原acceptance/Queue pair/claim及当前权限/Lease接真实capture；User-first锁序与无锁peek后Root精确重核，结束前再授权/验期限。故障/真实取消/到期接管全回滚、真并发单seal/新事件及generation原集合、PG40P01限次恢复通过。License合成，文件/公开HTTP尚待，不宣称完整Worker交付。

- A02-P02-A02接实际Jobs取消/当前Worker协作确认/到期恢复，原pair与首信息固定、真并发单次变化/故障回滚/取消与finish两个锁竞争顺序PASS。合成发布marker仅数据库证明，Owner授权/receipt/Audit/Artifact尚未接入，完整Worker/公开取消待。

- 核查取消申请人/原因在Job实现缺失，先登记CR-JOB-002，0039恢复首次申请人/原因/时点元数据；旧NULL无回填、首信息与技术身份固定、不可删除/复活/含历史down拒绝及实际表锁PASS。合成转换不冒充真正取消，A02命令/确认/恢复仍待，POST关闭。

- A06-A02-P01新增Jobs caller-UOW只检查租约公共入口，实际Job→Lease→Attempt锁及一致性/未到期核验，不续租、不完成或commit。真实接管/旧Worker及三事实锁/业务无写通过；取消状态仅合成拒绝，真实取消流程留P02，完整Worker/交付待。

- A06-A01新增Auth owned当前enabled User/部署角色锁及Audit每stage当前许可/PM成员部门权限Port，实际撤权/范围/归档维护/锁持有与业务无写PASS。注销Session不伪装异步取消；坐标不是Root/Lease证明。现有Job无capture/render只检查Lease公共Port或取消行为，留A02，不声明完整Worker或文件发布通过。

- A05-A03-P02 完整内部原子受理与真实 Job/Audit 引用通过；新 trace 重放保持首次结果，缺失/替换/旧无受理历史拒绝且不修复。真实死锁整 UOW 最多三次、每次重新授权，耗尽无残留。License合成，Worker/HTTP/文件交付仍待；详见对应进度记录。

- A03核查当前Job不能独立证明首次响应，先修订CR-AUD-001并实施0038受理历史；固定Job/Event/Audit Ref，精确Root源绑定、不可变/唯一/旧行无回填/down保护实测PASS。合成Job refs未冒充实际关联，完整原子命令留P02，POST仍关闭。

- AUD-03-A05-A02新增Jobs owned Audit专用最小ExportRef/政策enqueue公共Port，真实同Export并发首次pair/原Ref、双Scope/故障回滚/终态不复活/缺边篡改拒绝PASS。Queue不读Audit内部表、不自鉴权或commit；合成ExportRef不冒充根存在，A03完整受权原子仍待，POST关闭。

- AUD-03-A05-A01接实际Session/CSRF/License与PM/Admin提交授权，仅AUDIT_PROJECT_EXPORT write归档维护例外。真实五事实锁/撤权/范围/显式PM管理员与业务无写实测PASS（License合成）。结果metadata不是跨事务凭据，Job公共Port/receipt/Audit/Worker仍待，POST关闭。

- AUD-03-A04-P03已用真实单statement固定原Scope/Spec完整集合，同capture时点记录并封口；迟提交/回填/新事件不进入旧集合，真实等待重试返回同seal，故障/小上限超限整UOW回滚实测PASS。存储入口不自鉴权/commit/授予权限，POST未开放，A05/A06真实权限/Job/Lease及交付待。

- AUD-03-A04-P02/CR-AUD-001新增0037三表，实际源Scope/筛选、根锁/同事务封口、数量/顺序/摘要、并发等待后拒追加及历史down保护实测PASS；旧Audit/Job不变。Schema不能证明选全合法事件，P03单statement完整capture仍待，POST保持关闭。

- AUD-03-A04-P01已在实施前登记CR-AUD-001，固定CAPTURE-MEMBERSHIP-V1域分隔/UTC微秒/降序/空集合规范及纯领域摘要，拒绝重复/逆序/腐损/源失败截断；O(n)UUID去重内存未作性能承诺。0037尚未实施，摘要不是权限/实际来源/封口证明，POST仍关闭。

- AUD-03-A03 固定内部导出Scope/明确窗口/筛选/用途code和版本化JSONL投影指纹，不接受cursor/路径/Secret；Worker坐标不是权限证明，实际当前Actor事实/归档维护策略仍待。纯合同unit PASS，无新增真实权限或持久化，POST未开放。

- AUD-03-A02 已按实施前CR-JOB-001补齐0036 Job/Outbox DEPLOYMENT范围，旧GLOBAL/PROJECT保留，down先双表锁并拒绝任何部署历史，离线down关闭。真实空/有数据与并发/租约/投递/Parse范围回归PASS，无生产迁移，不代表导出或Gate完成。

- AUD-03-A01 真实head0035临时库证实DEPLOYMENT Job/Outbox被当前scope CHECK拒绝，与冻结DM-04/API-03不一致；不重标GLOBAL绕过。记录导出当前受权、真正seal snapshot、幂等/Job/fencing、Artifact安全交付/再授权和迁移验收分项；POST保持关闭，下一项先CR-JOB-001。

- AUD-02-A05 将四个审计GET装入Windows两种显式平台，独立Audit key缺失拒启且dispose；default/login-only404。真实数据库Session/PM/Admin/Scope双页、许可拒绝与14项受影响集成回归PASS。正式账户及发行信任锚未供给，非生产/Gate验收。

- AUD-02-A04 新增audit-list-cursor-v1独立Windows当前账户只读入口，缺失/长度错误/provider异常统一失败关闭，不自动生成或复用其他key。唯一临时Vault引用丢失/恢复旧游标实测PASS并清理；正式账户供给/离线保管/平台组合待完成。

- AUD-02-A03-P02 新增四个冻结审计GET的可选Router、安全筛选/默认24h或显式最大31天/同事务签名分页/投影/no-store；真实PostgreSQL Scope/无Admin项目旁路/撤销Session/License拒绝与读无写PASS。普通默认404，正式专用key与Windows组合、导出仍待。

- AUD-02-A03-P01 接入受权同事务搜索解析Port，真实Session/Scope授权后才使用实际Actor解码；错误或改变筛选/page_size不触发查询，有效签名窗口供查询和响应复用。内部/隔离数据库PASS，默认生产仍无审计HTTP，专用密钥来源/导出未完成。

- AUD-02-A02 新增独立 HMAC 审计游标，绑定实际 Actor/Session/Scope/全查询/UTC窗口与稳定位置；明确日期严格匹配，仅未显式日期可恢复原窗口。真实数据库双页和当前撤权拒绝PASS。签名不是授权/加密/MVCC快照；公开GET、正式专用密钥来源与导出未完成。

- RVW-02-A10核查Review仍只有Owner协议、无真实固定版本/身份锁/消费实现，公开前置BLOCKED；转Phase2独立AUD-02-A01。已接审计当前Session/PM或Admin实际授权、同事务private能力与Scope/安全投影/范围/排序/分页/筛选核对。项目归档可读历史，撤权/Session失效拒绝；五类授权事实锁与读无写实测PASS，暂无HTTP/导出。

- RVW-02-A09-P02 已接当前Session/CSRF/Project角色、assigned reviewer或PM、不可变事件receipt与当前历史版本Owner重放权限；新命令完整结构/Audit/receipt同事务，消费/审计/收据失败全回滚；真实40P01整UOW限次恢复。无实际业务Owner/客户资格或正式License信任源，不挂HTTP、不标Gate通过。

- RVW-02-A09-P01 已加入不可变命令事件Ref，用历史决定前缀/完整集合与前轮封口计数还原首次响应，不拿当前终态或根版本替代旧响应；后续新Round不改变旧结果，Scope/非STARTED或COMPLETED命令引用明确。查询不写库；权限/receipt入口与实际Owner仍待。

- RVW-02-A08 新增可信调用方事务决定/撤回完整 owned 写与真实 Audit，前后 Owner 锁核验、终态同事务消费与消费后独立重核；首 RETURN 不释放，撤回保留旧决定和 pending/原因，决定与撤回竞争单终态。故障全回滚含合成消费记录；不自建 UOW/commit/鉴权/receipt，不挂 HTTP。真实 Owner/跨模块锁序/客户批准仍待。

- RVW-02-A07/CR-RVW-002 新增0035事件原因和固定读回，旧NULL保留、中文原因完整、其他事件/空白拒绝、历史不可变；downgrade表排他锁防并发丢失，含原因拒绝down。隔离Schema/关联回归PASS，无实际Owner/受权撤回/公开API。

- RVW-02-A06 已核对冻结 decide 不增加 If-Match 必填、withdraw 保持根 ETag/PM；新增不可变单步交接合同，禁止代理/替换历史/跨轮次/终态再写。Owner 同事务消费才能正式化/解锁，APPROVED 必须重验当前 Sources 和资格。发现 AF-02 reason 在 0034 无持久字段，先登记 CR-RVW-002；迁移/真正业务 Owner/受权命令尚未完成。

- RVW-02-A05-P02 已接真实 Session/CSRF/PM/基础资格与幂等送审内部入口，账户预锁/PM 后才报资格、同事务完整结构/Audit/receipt；原始 Ref 重放不重复送审，当前权限仍重验。实际 40P01 整 UOW 回滚后限次重试成功；不声明所有旧命令无死锁。Owner/License 合成、无公开 HTTP 或实际客户批准。

- RVW-02-A05-P01 已完成可信调用方事务完整 Round owned 持久化与真实 Audit，Owner 准备/两次锁重核、Source 错版本/绑定/审计故障全回滚。服务不创建 UOW/commit/授权/收据；完整受权 start/P02 与实际 Owner 仍待，禁止直接公开。

- RVW-02-A04 已固定送审请求与 Prepared 的 Actor/Project/Review/逻辑主题/policy/Version/Round/完整确认人绑定，来源 Scope/唯一/UTC/时序校验；Owner prepare 和实际身份锁 assert 独立，禁止 DTO/UUID/True 代替事实。无真实 Owner 实现，完整 start 尚未完成。

- RVW-02-A02/A03 已完成送审前置及真实账户/项目基础资格服务，先 Auth 共享锁再当前成员/部门锁读，暂停/移除/未来生效/停用/跨项目/角色不符拒绝。返回必要事实不授予具体 Subject 评审权；完整 Session/CSRF/start/Owner 身份锁/政策和跨模块并发仍待。

- RVW-01-A06/A07 已完成创建前置和内部 PM 命令：DRAFT 根/同事务 Audit/收据，重放不可变原始创建 Ref，未知 Owner 拒绝、归档/撤权不旁路、审计和收据失败全回滚；没有 Round/真实送审锁/客户批准或 HTTP。输入固定版本仅参加创建校验/指纹，实际送审仍需独立 Snapshot/Owner 重验。

- RVW-01-A04/A05 已记录两层授权设计并实现内部 PROJECT 读服务，真实 Session/Project 锁读和四角色矩阵通过；固定旧版独立 Owner 权限必须通过后才加载意见/依据，缺 Owner 默认拒绝。Subject/License 协议合成、无公开接口/实际客户批准/Gate 证明；真实 Owner 和跨模块身份锁仍待。

- RVW-01-A03 已提供内部调用方事务 Scope 查询和固定 Round/Subject Snapshot，返回当前身份与独立历史进度，保持 Review→Round 共享锁，拒绝缺子记录/版本异常；后续来源变更不改历史观测。无公开接口/授权服务/新迁移，不能将 APPROVED 或观测 ELIGIBLE 当实际批准/Gate 证明。

- RVW-01-A02/0034 已落地八表、非空 Global Scope 父键、完整集合汇总/锁与事件原子、不可变/封口、Sources 当时事实与并发保护，隔离 Schema PASS。没有真实 Subject Owner/客户资格/审批命令；历史来源观测和合成 APPROVED 不能冒充现在批准或真实业务锁。

- RVW-01-A01/CR-RVW-001 已登记 Review 历史/身份锁八表设计；RVW-02-A01 已实现所有处理人完成才汇总的不可变多人进度，首条 RETURN 不提前终结/释放锁，撤回保留旧决定和 pending。仅纯领域，Review Schema/实际 Owner/客户批准和公开接口尚未完成。

- WFL-02-A01-P04/P05 已记录关联设计并实施 0033，旧 Gate 原值保持、新行必须关联已提交当前 Checklist 记录，固定 typed refs 精确一致且重观测不回退，隔离 Schema PASS。真实 Review/例外/Owner 与受权 Gate 命令仍缺，先进入统一 Review 前置，不以合成 APPROVED 放行业务。

- WFL-01-A05-P04 已实现内部事务当前记录/固定依据查询，核对完整历史链与当前 Item 结果/版本，缺链旧 PASS 和过时值拒绝，保持 Workflow→Item 锁至调用方结束。后续 Evidence 变化不重写历史；查询结果仍需真实受权 Owner 重验，未开放 Checklist 写/Gate 路由。

- WFL-01-A05-P03/CR-WFL-004 已新增两表/0032 与初次/更正可信链、同事务两个版本/当前投影、BLOCKED 保持、观测与不可改写保护，隔离合成 Schema PASS。实际 Review/Owner/受权写命令/Gate 固定记录关联尚缺，不把旧无链 PASS 或合成 APPROVED 当业务事实。

- WFL-01-A05-P02 已实现不可变首次/更正纯 Domain 快照，保留原结果及依据，两个版本序列分离；FAIL 可表示资料不足，正向结果需依据形状。无数据库/公开写路径，UUID 或构造成功不等于真实 Scope/批准/Gate；CR-WFL-004 持久层与 Owner 前置仍待。

- WFL-01-A05-P01 登记 CR-WFL-004：新增 Checklist owned 记录/依据链，不覆盖旧结果或 Gate 快照；首次与更正受控、Item/Workflow 版本分离、旧非初态无链不回填。尚无记录 Schema/命令，真实 Owner/Gate 未验。

- WFL-02-A01-P03/CR-WFL-003 已落地三表历史/0031 和提交完整性、当前状态原子核对、不可变及提交后封口、Evidence 观测事实保护，隔离结构验收 PASS。真实 Review/例外/Checklist 历史与写服务未具备，Schema 可存合成 APPROVED 不等于客户批准，不作为 Gate/发行通过。

- WFL-02-A01-P02 记录 CR-WFL-003/三表设计：Evidence 可变 eligibility 要保存观测事实，Review Schema 当前缺失不能伪造 FK/批准。新增 owned typed refs 与事务内子项追加方案，0031 尚未实施；实际迁移、Checklist/START/完成与 Gate/写服务仍待，不宣称 Workflow 完成。

- WFL-02-A01-P01 已完成不可变成功相邻迁移/完整 GateItemSnapshot 形状与纯领域测试，WAIVED 独立依据不改写 PASS；构造成功不是 Gate 证明。历史数据库/Owner 同事务事实/START/完成/写 API 未实现，不凭 UUID 认定批准。

- WFL-01-A04-P03 已将只读 GET 接入 Windows 两种显式平台模式并验证真实 Session/隔离 PostgreSQL 授权及缺合成信任源失败关闭。默认/仅登录及 Workflow 写路径保持 404；正式信任源/历史/实际 Gate 尚未完成，不代表生产发行通过。

- WFL-01-A04-P02 已提供可选 WORKFLOW_GET，真实 Session/PostgreSQL 合成 HTTP 验证 PASS。默认与 Windows 显式组合仍未挂载；仅状态只读，不等于 Gate/启动/推进完成，错误项目投影不会返回。
- WFL-01-A04-P01 内部读服务从一条 SQL 快照产生完整固定 V1 状态投影，缺实例不写库。WORKFLOW_GET 为四角色只读并保持当前 Project/成员/部门事实锁，撤权并发已验证；HTTP/性能/真实 Gate 未验，不将存储状态当客户确认依据。
- WFL-01-A03-P05 提供内部 PM 受权初始化：使用 WORKFLOW_START 对应管理权限准备 NOT_STARTED 结构，不执行 start 或自动回填。真实 Session/Project/CSRF/角色拒绝、合成 License/并发/审计回滚已验证；无公开 HTTP/CLI，真实发行信任源与完整 Gate 未具备。
- WFL-01-A03-P04 已在 Windows 显式平台新建 Project 事务装配 Workflow 初始化，真实 Session/Admin/CSRF 与合成 License 拒绝、并发幂等、初始化/Audit 故障全链回滚已验证。已有 Project 和不装配 Port 的旧隔离内部调用仍未补齐，不能视为 Workflow 全链 PASS。
- WFL-01-A03-P03 已完成供授权应用调用的内部同事务初始化（NOT_STARTED/PENDING），新实例一次 Audit，重复/并发收敛并不重置已有进度。入口自身不承担用户授权/License，尚未连接 Project 创建或既有项目回填；不能以合成内部调用方验收判真实权限/生产路径 PASS。
- WFL-01-A03-P02 按 CR-WFL-002 落地四表 ORM/0030 及 deferred 结构保护，隔离 PostgreSQL 合成验证 PASS。当前没有生产 Workflow 实例或初始化接线，真实 Gate/历史/Audit/权限未具备；结构可表示通过状态不代表业务已批准，写 API 继续关闭。
- WFL-01-A03-P01 登记 CR-WFL-002：当前阶段可 ACTIVE/BLOCKED 唯一，终态保留最后阶段指针；四表初始化和提交完整性设计已记录，数据库尚未实施。既有项目不自动推定进度，最终完成 HTTP 不猜测；0030 尚不存在，下一任务执行真实 Schema 验收。
- WFL-01-A02-P01 只校验 ACTIVE Workflow 的相邻目标、非归档及乐观锁一致，返回值不是 Gate PASS，也不创建 Transition。状态枚举与冻结模型一致；Gate、授权、同事务历史与失败 Audit 留待应用层，BLOCKED 恢复/最终完成需独立定义，不能引入虚构终点 key。
- WFL-01-A01-P02 按 CR-WFL-001 发布固定六阶段配置 V1 与策略来源文档；十二项均必需，配置不含项目状态或客户确认。尚无 Gate evaluator/Owner Port 接线，不能凭策略引用判实际 PASS，未创建 Workflow 实例。后续修改须发布新定义版本，不覆盖 V1。
- 分支：`feature/license-runtime-guard`
- TRC-01-A05-P02 内部 PROJECT TraceLink 创建已在 Windows 11/隔离 PostgreSQL 通过真实授权、并发去重、持久幂等、环拒绝和 Audit 回滚；仅 DOC-02 Owner 注册，公开 HTTP 与其他 Owner 仍待，不能视为 TRC-01 整体或 Gate 3 PASS。
- TRC-01-A05-P03 前置核查按 CR-TRC-002 保持通用 Trace POST 不挂载；冻结三字段 ResourceVersionRef 缺各 Owner 的可信 Scope/Project 解析，不能猜测或补未冻结必填字段。转 WFL-01 独立任务。
- WFL-01-A01-P01 仅完成不预设业务清单的版本化阶段/Checklist 定义形状与打包验证；API2-R04 的正式 Stage/Gate 配置仍待设计，不能据此启动项目 Workflow 或判 Gate PASS。
- 最近功能检查点：LIC-02-A05 已实现仅内部管理员受控重验证；拒绝状态可在活动安装文档、真实验签、机器/有效期/可信时间全部通过后恢复 VALID，失败则保持拒绝并记录事件/Audit。公开 HTTP 挂载、生产公钥/选定 MAC/可信时间密钥来源与初始化仍未接线，不得对外开放业务。Auth 仍无公开登录或管理 API。
- LIC-03-A03 编码前发现任务名称仅为上一任务暂定，未有批准的验收定义；冻结架构明确把 SecretKeyProvider 的 Windows/Linux 实现与密钥恢复留给 Release 安全设计，当前仅有未落地的 Secret 访问 Port。生产可信来源不能以明文环境变量/普通 YAML/临时文件替代，受影响的装配工作暂停，见 `docs/progress/lic-03-a03-precheck.md`。
- 用户已选择方案 A 并作出持续执行授权：LIC-03-A03 现只做一次性受控初态初始化，生产信任源留待 PLT-02/Release；执行纪律差异见 `CR-EXEC-001`。上条“暂停”记录作为历史检查结论保留，不代表当前仍待用户决定。
- LIC-03-A03 已按方案 A PASS；初始化不包含生产信任源，不能放行业务。下项推进 PLT-02 SecretRecord 数据层；具体跨平台密钥保护与恢复仍待 Release 安全验证。
- PLT-02-A01 已完成密文版本持久层与迁移；生产 Secret Store 仍需写命令、权限/审计、解密适配及跨平台主密钥方案，不能据此配置真实 API Key。
- PLT-02-A02 已完成只读密文信封适配；使用合成解密器验证消费边界，不代表生产加密/解密已可用。管理元数据、正式写命令与跨平台主密钥仍待后续任务。
- PLT-02-A03 已完成管理员元数据内部查询与脱敏投影；公开 GET、生产 License/Secret 装配和写命令未接线。
- PLT-02-A04 已完成版本化 AES-256-GCM 加解密适配和临时库密文写入验证；生产 Key Provider、正式权限写命令和轮换仍未接线。
- PLT-02-A05 已完成仅内部受控创建/轮换与同事务审计；生产 Key Provider、公开管理 API、停用命令及 License 整体接线仍未完成。
- PLT-02-A06 已完成内部停用并验证停用后受控读取拒绝；公开管理 API 因生产身份/许可/密钥装配与 If-Match/幂等缺口拆至 A07，当前不可开放。
- PLT-02-A07 前置核查未通过，见 `docs/progress/plt-02-a07-precheck.md` 与 CR-PLT-003；该单项公开接线停留在 404，项目转先完成 AUT-03 等前置，不将 A07 标为 PASS。
- PLT-02-A07-P04-A01 已完成可选挂载的 Secret 详情只读 HTTP 与安全投影/ETag 合成契约；生产管理路由尚未装配，列表/写接口和真实信任锚仍待完成，A07 整体未 PASS。
- PLT-02-A07-P04-A02 已完成可选 Secret 列表 HTTP/完整性保护游标及 PostgreSQL 同时间戳 keyset 验证；生产游标签名密钥来源/恢复、只读路由装配与写接口仍待完成，A07 整体未 PASS。
- PLT-02-A07-P04-A03 已完成 Windows 独立游标签名密钥安全来源与临时 Vault 备份恢复测试；正式账户供给与生产只读路由装配仍待完成，A07 整体未 PASS。
- PLT-02-A07-P04-A04 已新增 Windows 显式平台组合，仅在正式 License/游标信任源齐备时挂载 Secret 详情/列表；合成失败关闭通过但正式公钥/账户尚缺，不能把 `--platform` 标为生产 PASS，写 API 仍关闭。
- PLT-02-A07-P05-A01 已修正内部轮换版本条件为记录 `lock_version` 并经 PostgreSQL 版本分离/并发验证；公开 If-Match/幂等尚未接线，写路由仍关闭。
- PLT-02-A07-P05-A02 已增加规范强 If-Match 解析并验证 428/400 安全边界；尚无完整写路由或同事务幂等，不能标 Secret 写 API PASS。
- PLT-02-A07-P05-A03 已完成内部 Secret 创建同事务持久幂等，PostgreSQL 顺序/并发/回滚通过；轮换/停用收据与公开 write-only HTTP 仍待完成。
- PLT-02-A07-P05-A04 已完成内部 Secret 轮换/停用持久幂等与 PostgreSQL 同 Key 并发验证；write-only HTTP 和正式生产信任源仍未完成。
- PLT-02-A07-P05-A05 已完成可选 Secret 创建 write-only HTTP 与 PostgreSQL 隔离合成端到端；默认/生产组合仍不挂载写路由，正式信任源和轮换/停用 HTTP 待完成。
- PLT-02-A07-P05-A06 已完成可选 Secret 轮换 write-only HTTP 与 PostgreSQL 隔离合成端到端；默认/生产组合仍不挂载写路由，正式信任源和停用 HTTP 待完成。
- PLT-02-A07-P05-A07 已完成可选 Secret 停用 HTTP 与 PostgreSQL 隔离合成端到端；默认/生产组合仍不挂载写路由，正式信任源待供给，A07 整体未 PASS。
- PLT-02-A07-P05-A08 已新增 Windows 显式写组合，并在 PostgreSQL 临时库完成合成信任源端到端；默认/只读模式保持关闭，正式发行公钥和目标账户密钥尚缺，A07 整体未 PASS。
- PLT-02-A07-P05-A09 正式发行前置核查发现真实签发密钥、口令独立保管/离线备份及目标账户材料缺失；本项保持 BLOCKED_BY_OPERATOR_CEREMONY，不以合成材料替代，转独立 Project 任务。
- PRJ-04-A01 已完成可选 Project 列表/详情 HTTP 的 PostgreSQL 隔离合成端到端；默认/生产组合尚不挂载，PRJ-04 整体未 PASS。
- PRJ-04-A02 已将 Project 列表/详情挂入 Windows 显式平台模式并在 PostgreSQL 临时库完成合成 License/真实 Session 多用户验证；默认模式仍 404，正式信任源与 PRJ-04 整体未 PASS。
- PRJ-04-A03 编码前发现原内部 Project 创建尚无持久幂等，暂停直接开放 POST；已复用 `0015` 收据完成同事务幂等及 PostgreSQL 并发/回滚验证，公开路由与正式信任源仍待。
- PRJ-04-A04 已完成可选 Project 创建 HTTP 与 PostgreSQL 隔离合成端到端；默认/当前生产组合未挂载，正式信任源和 PRJ-04 整体未 PASS。
- PRJ-04-A05 已在 Windows 显式平台组合挂载 Project 创建，并在 PostgreSQL 临时库验证真实 Session/同 Key 重放/管理员与合成 License 拒绝；默认模式仍 404，正式信任源与 PRJ-04 整体未 PASS。
- PRJ-04-A06 已完成可选 Project 名称 PATCH，补齐冻结 ETag 初始版本 `"v0"` 的通用解析；PostgreSQL 临时库验证 HTTP 冲突/隔离/Audit，默认及当前平台组合仍 404，正式信任源与 PRJ-04 整体未 PASS。
- PRJ-04-A07 已在 Windows 显式平台组合挂载 Project 名称 PATCH，并在 PostgreSQL 临时库验证真实 Session/版本冲突/合成 License 拒绝；默认模式仍 404，正式信任源与 PRJ-04 整体未 PASS。
- PRJ-04-A08-P01 已复用 `0015` 收据完成内部归档同事务幂等，临时 PostgreSQL 验证并发同 Key 仅一次状态/Audit/收据及失败回滚；公开归档 HTTP 仍 404。
- PRJ-04-A08-P02 已完成可选归档 POST HTTP，临时 PostgreSQL 验证同 Key 重放仅一次归档/Audit；默认及当前平台组合仍 404，正式信任源未供给。
- PRJ-04-A08-P03 已将归档 POST 挂入 Windows 显式平台并在临时 PostgreSQL 验证真实 Session/重放仅一次 Audit/合成 License 拒绝；默认模式仍 404，正式信任源与 PRJ-04 整体未 PASS。
- PRJ-04-A09-P01 已完成成员列表独立 HMAC cursor 的会话/项目/查询绑定，并修正旧 Secret cursor 测试的随机误报；可选 HTTP 与 Windows 目标账户密钥来源仍待。
- PRJ-04-A09-P02 已完成可选成员历史列表 HTTP 与临时 PostgreSQL 双页/权限/License 验证；默认及当前平台组合仍 404，独立成员 cursor 密钥来源待验。
- PRJ-04-A09-P03 已完成 Windows 当前账户独立成员 cursor 密钥只读入口与测试 Vault 备份恢复；正式账户供给和平台组合仍待。
- PRJ-04-A09-P04 已把成员历史列表挂入 Windows 显式平台，独立密钥缺失拒绝启动；临时 PostgreSQL 真实 Session 双页/权限/License 及既有组合回归通过，正式账户材料未供给。
- PRJ-04-A10-P01 已按 CR-PRJ-002 新增不可变成员创建结果快照和同事务收据，PostgreSQL 并发/回滚/历史响应/迁移验证通过；公开创建 HTTP 尚未接线，下一项 P02。
- PRJ-04-A10-P02 已新增可选成员创建 HTTP，在临时 PostgreSQL 验证真实 Session 同 Key 两次 201 仅一成员/Audit、异载荷/角色/跨项目/License 拒绝；默认与当前 Windows 组合仍 404，下一项 P03。
- PRJ-04-A10-P03 已在 Windows 两种显式平台模式挂载成员创建，临时 PostgreSQL 真实 Session/重放/权限/License 及缺成员 cursor 密钥失败关闭验证通过；默认模式仍 404，正式账户材料未供给。
- PRJ-04-A11-P01 已新增可选成员 PATCH HTTP，在临时 PostgreSQL 验证强 If-Match、ProjectManager/跨项目/最后负责人/License、历史与 Audit 同事务；默认及当前平台模式仍 404，下一项 P02。
- PRJ-04-A11-P02 已在 Windows 两种显式平台模式挂载成员 PATCH，临时 PostgreSQL 真实 Session/版本/权限/License/历史审计及缺成员 cursor 密钥失败关闭验证通过；默认模式仍 404，正式账户材料未供给。
- PRJ-04-A12-P01 已按 CR-PRJ-003 为成员暂停/恢复/移除增加同事务收据与不可变首次结果快照；PostgreSQL 三状态并发/回滚/历史重放/迁移验证通过，公开 HTTP 尚未接线。
- PRJ-04-A12-P02 已增加可选成员暂停/恢复/移除 HTTP，并在 PostgreSQL 临时库验证真实 Session/重放/冲突/跨项目及合成 License 拒绝；默认和当前 Windows 显式平台组合仍 404，正式信任源和 PRJ-04 整体未 PASS。
- PRJ-04-A12-P03 已在 Windows 两种显式平台模式挂载成员状态命令，PostgreSQL 临时库真实 Session/三状态重放/缺信任源失败关闭通过；默认模式仍 404，正式目标账户材料未供给。
- PRJ-04-A13-P01 已增加独立签名部门列表游标，绑定当前 Session/Project/page size/稳定部门位置并拒绝跨资源族；公开 GET 与 Windows 目标账户密钥来源仍待。
- PRJ-04-A13-P02 已新增可选部门列表 GET，PostgreSQL 临时库双页/角色/跨项目/License 拒绝通过，并修正内部许可失败映射；默认与当前 Windows 平台组合仍 404，独立密钥来源待验。
- PRJ-04-A13-P03 已增加 Windows 当前账户独立部门游标 Vault 只读入口，临时引用备份恢复旧游标验证通过；正式目标账户密钥未供给，平台组合仍 404。
- PRJ-04-A13-P04 已把部门列表挂入 Windows 两种显式平台模式，独立密钥缺失拒绝启动；临时 PostgreSQL 双页/跨项目/License 与 8 个受影响集成脚本回归通过，默认模式仍 404，正式账户材料未供给。
- PRJ-04-A14-P01 已按 CR-PRJ-004 增加部门创建不可变首次结果快照和同事务收据，Migration `0018` 及 PostgreSQL 并发/回滚/历史响应/迁移验证通过；公开 POST 尚未接线。
- PRJ-04-A14-P02 已新增可选部门创建 POST，PostgreSQL 临时库真实 Session 同 Key 两次 201 仅一部门/Audit、异载荷/角色/跨项目/License 拒绝；默认与当前 Windows 组合仍 404，下一项 P03。
- PRJ-04-A14-P03 已把部门创建挂入 Windows 两种显式平台模式，临时 PostgreSQL 真实 Session/重放/权限/License 及缺部门 cursor 密钥失败关闭验证通过；默认模式仍 404，正式账户材料未供给。
- AUT-03-A01 仅完成未挂载的可信 Host/Origin 策略；缺失/重复/不匹配失败关闭。限流、凭据、Cookie/CSRF 与公开登录仍待后续任务。
- AUT-03-A02 完成 PostgreSQL 原子登录限流；真实客户端地址可信代理策略和过期桶清理调度未接线，登录仍未公开。
- AUT-03-A03 完成内部登录编排与真实 scrypt/Session 集成；公开 HTTP/Cookie/CSRF、初始管理员和生产装配仍未完成。
- AUT-03-A04 完成可选登录 Router 的 Cookie/CSRF 传输契约；未注入生产依赖时仍 404，不能视作可用登录。
- AUT-03-A05 补齐 SessionView 身份/部署角色并强制显式 Project 授权摘要 Port；项目成员读层未实现，生产 Router 仍未装配。
- AUT-03-A06 提供仅空 User 表的一次性本机初始管理员 CLI；测试库验证成功，但未在真实部署替用户设置密码或创建管理员。
- AUT-03-A07 生产装配前置未满足，按 CR-AUT-002 先建设当前 Phase 2 的 Project 成员事实，未将 A07 记 PASS。
- PRJ-01-A01 三张 Project 表与约束已落地；该任务本身不包含业务命令或授权读取，后者已由 A02 补充只读摘要。
- PRJ-01-A02 建立当前 ProjectMember 事实的只读授权摘要；逐操作授权及生产登录安全配置仍未完成。
- PRJ-01-A03 完成 13 项 Project 路径内逐操作授权与目标归属核查；Project 列表/创建及实际写命令、生产 Auth/License 装配仍未完成。
- PRJ-01-A04 完成仅内部原子创建 Project、首位 Manager 与默认/指定 Department；真实 Auth Session/CSRF 已接，License Guard 在临时库仍为合成依赖，公开路由未开放。
- PRJ-01-A05 完成内部当前 Session/成员驱动的 Project 列表与详情读取；归档受权可读，跨项目隐藏，公开 GET 与生产 License 装配仍未完成。
- PRJ-01-A06 完成内部项目名称修改与单向归档，按当前管理角色和 expected version 串行化并同事务审计；跨模块归档写拦截及公开 API 仍需后续接线。
- PRJ-02-A01 完成内部授权成员历史列表与 keyset 分页；公开 HTTP 的不透明 cursor、生产 License 与安全运行接线仍未完成。
- PRJ-02-A02 完成内部成员创建与单项目并发唯一性验证；正式 POST 幂等、生产 License 与公开 API 仍未接线。
- PRJ-02-A03 按 CR-PRJ-001 完成内部成员角色/部门修改与历史保存；正式 PATCH 的 HTTP If-Match/幂等、生产 License 与公开 API 仍未接线。
- PRJ-02-A04 完成内部成员暂停/恢复/移除与最后负责人保护；正式 POST 幂等/If-Match、生产 License 与公开 API 仍未接线。
- PRJ-03-A01 完成内部授权部门历史列表和稳定分页；正式 GET 不透明 cursor、生产 License 与公开 API 仍未接线。
- PRJ-03-A02 完成内部部门创建、活动编码唯一与并发冲突验证；正式 POST 幂等、生产 License 与公开 API 仍未接线。
- PRJ-03-A03 完成内部部门名称/编码 PATCH、强版本与并发冲突验证；现有 Audit 不保留字段级旧值，正式 PATCH/生产 License 与公开 API 仍未接线。
- PRJ-03-A04 完成内部部门单向停用与 ACTIVE/SUSPENDED 成员引用保护；正式 POST 幂等/If-Match、生产 License 与公开 API 仍未接线。
- LIC-02-A02 冻结冲突已由用户明确批准方案 B；正式差异见 `docs/changes/CR-LIC-001-single-product-full-bundle.md`。V2.1 原文保留历史，专项补充为当前 License 授权粒度基线。
- 远端同步状态必须在每次任务结束前通过 Git 实时检查，不在本文件固化可能过期的 ahead/behind 数值。
- 本地用户文件和 Git 忽略的客户资料保持不变。
