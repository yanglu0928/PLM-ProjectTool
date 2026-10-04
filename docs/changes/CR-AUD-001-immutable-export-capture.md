# CR-AUD-001：审计导出不可变意图与来源集合

日期2026-09-26；Phase2；执行依据V1.1及用户持续授权。实施前记录；原冻结64cdf09及0001～0036不改写。

## 缺口、选择及边界

冻结API-02需要异步受权审计导出，但当前只有追加aud_events和分页读取；时间窗口/游标不是MVCC快照。A01已记录迟提交和回填风险。新增Audit owned导出意图、capture header及来源成员，保持模块化单体/PostgreSQL任务。选择一次capture事务内单条INSERT SELECT固定来源，再封口；不选逐页查询追加、不复制原始请求/Session、不通过假Document实现文件归属。

请求固定原Actor、Scope/Project、起止时间/筛选/目的、策略/投影/格式及指纹；请求时间与实际capture时间分离。意图不可变，实际Job绑定及结果后续按公共Port另验；不用外模块内部表写入。Worker异步capture时重新核验实际权限，不声称POST时点快照。一个Export首个成功封口集合永久固定，失败事务整批回滚；后续Job generation复用原集合，不静默换集合。需要新集合必须新请求/ExportRef。

## 数据库设计与实施分项

1. A04-P01：先固定CAPTURE-MEMBERSHIP-V1规范摘要：有域分隔的SHA-256，逐条规范UUID和UTC微秒时间，以查询既有顺序(time,UUID)降序流入；禁止重复ID、逆序、无时区、零UUID，明确空集合摘要。只验证成员坐标，不是权限、来源真实性或文件Hash。
2. A04-P02：增量0037/ORM新增不可变Export意图、单一capture header、成员关联。Export保存服务器版本化意图且禁止更新/删除/truncate；capture唯一Export，成员(event,time,position)关联真实不可变aud_events且必须符合原Scope/完整筛选。禁止修改/删除/truncate。单次查询选择、封口及调用者UOW将分项实现，Schema须通过真实空/有数据升级/降级。
3. 事务提交完整性要求：header声明count与全部成员数一致、位置连续、排序正确、摘要与P01一致；空集合合法。提交后禁止再追加，成员插入必须锁header/Export；deferred约束及封口状态必须防止并发在封口后塞入。不能只依靠应用DTO或CHECK count>=0。最终Schema设计在P02实施前补充具体SQL/锁序并验证，尚未实施不得标PASS。
4. A04-P03：实际capture repository以真实授权调用方事务执行单statement INSERT SELECT，验证迟提交/回填/新增事件不会进入已封口集合，重试读同一集合，错误Scope/源缺失/空集合/故障全回滚。实际Actor权限、Job fencing、publish和下载在A05～A07完成，不以Schema验收替代。

## 风险、迁移、回滚及验收

增量DDL需要维护窗口与备份；AI仅使用独立UUID临时库，不操作生产。旧Audit/Job/业务数据不得回填、重标、删除或改写。down先按固定锁序锁新增表，再检查任何历史；有记录拒绝降级，不销毁导出历史；离线down禁止，无记录可撤新增结构。并发down写阻塞必须实测。未来任何格式/摘要版本变化使用新版本规则，保留旧读回，不拿当前常量重算旧历史。

成员量可能很大：应用摘要增量计算，不载全部事件正文；P01为拒绝不同时间的重复UUID保存O(n)标识集合，不能宣称常量内存或性能达标。后续实际capture须规定行数/空间上限，数据库唯一约束与SQL摘要可避免完整成员驻留应用，但必须验收规范一致性；capture SQL/排序/数据库摘要与空间上限的实际性能待验。超限明确失败，禁止截断后声称完整。文件Hash是输出字节完整性，成员摘要是固定来源坐标完整性，两者不能互换。无秘密字段/自由正文/路径/Session/Token进入成员。

验证要求：P01规范向量/空集/时区等价/排序/重复/腐损/字段绑定；P02 ORM parity、真实空/旧数据up/down/re-up、不可变/源归属/完整性/锁竞争；P03晚提交/回填/重试/故障。无公开API/角色/依赖变化；新增结果下载API如需扩展冻结合同另建CR。Windows11先验，Server2025未验，Debian暂缓但目标保留。Gate3/质量/UAT/完整包仍未通过。

当前状态：IMPLEMENTATION_IN_PROGRESS。不得将计划视为Schema或真实权限证据。

A06-A04-P01执行结果（2026-09-26）：真实固定member source显式安全列/Scope/筛选连接canonical JSONL内存字节及独立manifest，重核完整成员摘要/count/顺序/唯一，输出hash/size、空集/新事件排除、不安全码/短写/源故障/小上限及资源关闭通过。880项无失败（2环境跳过）、真实Worker回归和开发wheel通过；详见aud-03-a06-a04-p01-render.md。未生成/发布实际文件，纯renderer/source不授予权限，正式Artifact/渲染checkpoint/存储/发布/下载/性能仍待，CR整体IN_PROGRESS。

A06-A03执行结果（2026-09-26）：实际已受理Root/acceptance/原Queue pair/真实claim、当前Actor权限与租约前后核验接真实capture全UOW通过；新事件/新generation不改原seal，真并发首次单seal，撤权/实际取消/到期及seal写后故障回滚，真实40P01第二次恢复与三次耗尽无残留通过。873项无失败（2环境跳过）、相关真实回归及开发wheel通过，详见aud-03-a06-a03-worker-capture.md。License合成，无渲染/Artifact/公开HTTP/性能/正式包，CR整体IN_PROGRESS。

P02执行结果：0037/ORM三表及实际源校验/同事务封口/不可变/并发/降级保护在独立PostgreSQL库通过；816项unit无失败（2项环境跳过）、Windows审计和Job部署真实回归、开发wheel通过。详见aud-03-a04-p02-capture-schema.md。P03单statement选择完整集合/晚提交及A05～A07权限/Worker/交付未完成，CR整体仍IN_PROGRESS。

P03执行结果：单statement实际源选择/迟提交/回填/新增事件排除、原seal并发重放、caller故障/不commit回滚、Spec指纹/Scope绑定、小上限拒绝不截断和安全读回通过。823项后端无失败（2环境跳过）、P02回归与开发wheel通过，详见aud-03-a04-p03-capture.md。CR的A04存储验收完成，授权/Job/Worker/交付/性能仍待，整体IN_PROGRESS；无生产操作/公开POST。

## A05-A03-P01实施前修订：不可变首次受理结果

2026-09-26。A03核查证实0037意图不存Job/Event ID，而通用receipt只存单一typed Ref；Jobs owned行可变，A02 lookup能验证绑定但不能独立证明当前Job ID就是首次响应。不得只拿当前Queue Ref作为不可变首次结果。选择增量0038 aud_export_acceptances，唯一ExportRef关联own意图，固定首次job_id/event_id/request_audit_event_id/accepted_at；Job/Event是跨Owner opaque Ref，不跨模块读取或直接写Job表，实际存在/全绑定由A02公共Port在A03同事务核验。

Audit own请求事件FK+唯一，插入前锁意图根，核验源事件是同Root原Trace/USER Actor/Scope/Project/SUCCESS/AUDIT_EXPORT_REQUESTED/受控purpose，目标必须为真实Job typed root jobs/JOB-01和固定job_id，before NULL/after PENDING，无target version。不将Export ID假称AuditEvent/AUD-01。事件时点/受理时点不早于请求；新acceptance不可更新/删除/truncate，Job/Event/Audit Ref各唯一防复用。只Schema校验不能证明Jobs实际存在或完整受权，因此不可提前放行POST。

历史0037不追写；旧无acceptance意图不回填/猜Job ID，完整命令重放若receipt指向这种不完整历史则拒绝而不伪造首次结果。后续首次创建必须授权→receipt→Root→Queue→请求Audit→acceptance→receipt完成在同UOW，重复请求先当前授权再加载原acceptance，通过Jobs公开Port核对原ID而不创建/换Ref。

0038空表可down：先ACCESS EXCLUSIVE锁acceptance再检查，有任何首次结果拒绝；离线down禁用，无生产操作。要求ORM parity、空/旧意图和审计数据up/down/re-up保留、错误绑定/来源/目的/时点/唯一/不可变、down并发写锁及有历史拒绝。原授权/Scope/API/角色/依赖不变；该分项完成后A03-P02真实原子命令验收，不能用Schema替代。

P01执行结果：0038/ORM、真实独立Schema/旧Root与Audit保留/no backfill/完整源绑定/不可变/唯一/并发down锁/历史拒绝通过；839项无失败（2环境跳过）、四项相关真实回归和开发wheel通过。Job/Event refs为合成，完整命令实际关联/权限/receipt/Job/Audit原子仍待；详见aud-03-a05-a03-p01-acceptance-schema.md。CR整体仍IN_PROGRESS，无生产操作或POST。

## P02实施前SQL与锁序收敛

A05-A03-P02执行结果（2026-09-26）：真实提交授权、receipt、Root、Jobs公共Queue、请求Audit、acceptance及receipt完成同UOW通过。重放先当前授权并核对原ID，缺失/替换/旧无acceptance历史拒绝而不修复；实际故障全回滚、竞争首次提交和PG40P01整UOW最多三次重新授权/耗尽无残留通过。后端847项无失败（2环境跳过）、相关真实回归与开发wheel通过，详见aud-03-a05-a03-p02-atomic-submit.md。License合成；无新Schema/生产操作/公开POST。Worker、Artifact交付、访问再授权和性能仍待，CR整体IN_PROGRESS。

新增aud_exports（不可变意图，显式安全字段，真实User/Project元数据FK）、aud_export_members（ExportRef+position主键、ExportRef+event唯一、真实event FK）、aud_export_captures（ExportRef唯一、实际时点/count/hash/version）。不用可变seal bool；capture行本身就是不可变封口。意图允许先提交等待Worker；成员必须和capture同事务提交，deferred成员约束拒绝未封口提交。

成员及capture插入先锁aud_exports对应行FOR UPDATE，持至事务结束。成员插入拒绝已有capture，核验源Scope/time及全部筛选，created_xid强制当前事务。capture插入重核全部成员来自当前事务、数量与连续位置、按time/UUID降序、来源摘要、capture不早于请求。先成员后capture；capture插入后同事务也不得再插成员。并发第二个capture/成员等待同一根锁并重查封口，数据库唯一键另行兜底；REPEATABLE READ旧快照存在serialization风险，正式runtime固定READ COMMITTED且P03须验，不把异常当成功。

三个表UPDATE/DELETE/TRUNCATE均禁止。down固定父到子ACCESS EXCLUSIVE锁三个表，任何导出历史（包括待处理意图）拒绝；无历史可回退，不改原aud_events。P02验证成员形状/源Scope完整筛选/封口完整性/并发锁和迁移；单SQL选取真正完整集合及迟提交场景由P03验，Schema不能判断客户端故意漏选了一个合法事件，故不宣称此处已证明选择完整性。SQL成员摘要使用PostgreSQL18内置sha256(bytea)，无需pgcrypto新依赖；规范与P01逐字节比对。参考：https://www.postgresql.org/docs/18/functions-binarystring.html。
