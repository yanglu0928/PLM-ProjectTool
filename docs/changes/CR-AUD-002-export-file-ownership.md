# CR-AUD-002：审计导出文件归属与发布结果

日期：2026-09-26；Phase2；状态：IN_PROGRESS / 分项验证见当前结果，整体发布未验收。执行依据：用户2026-09-24及2026-09-26持续授权、V1.1。保留冻结提交64cdf09、ADR-008、既有0001～0039；不修改原冻结文件。

## 来源与实际冲突

API-02 AUDIT_EXPORT要求部署或项目范围的202 JobRef；DM-03/DOC-03 FileObject及当前ORM/LocalFileStorage/PublishFile仅GLOBAL/PROJECT。DM-04 OutputArtifact为PROJECT，需OutputRequest/PluginExecution/GENERATED_ARTIFACT DocumentVersion。审计导出无这些业务来源；部署导出也无ProjectId。A04-P02四项实际只读探测确认当前入口不兼容，见对应进度与验证脚本。A04-P01已完成安全JSONL/独立manifest，不代表真实文件发布。

## 比较与选择

- 改标GLOBAL、虚构Project/Document/Plugin来源：拒绝，违反权限域和追溯真实性。
- 扩大Document/Upload/Parse/Output全链路到DEPLOYMENT：拒绝作为首选，影响不必要的业务规则及公开接口。
- 选择：DOC-03内部FileObject增加专用AUDIT_EXPORT用途与DEPLOYMENT归属；PROJECT审计也用同专用用途。Document/Version/Upload/Parse保持原Scope/用途，业务OutputArtifact不修改。Audit保存自己的导出结果和尝试引用，不伪造文档版本或新增业务输出范围。模块化单体、本地文件+PostgreSQL和既有技术栈不变。

## 受控数据契约（实施前约束）

1. FileObject新增`usage_kind`（DOCUMENT/AUDIT_EXPORT）和`owner_object_id`内部逻辑来源。旧数据升级为DOCUMENT/NULL，原ID/Scope/Hash/Locator/状态不变。AUDIT_EXPORT必须owner非零UUID且Scope为PROJECT或DEPLOYMENT；DEPLOYMENT项目为空，PROJECT非空；GLOBAL不能AUDIT_EXPORT。DOCUMENT保持GLOBAL/PROJECT及NULL owner。标识不是授权，跨Owner引用实际验证走公共Port，不跨模块直接写表。
2. DocumentVersion/Upload绑定必须拒绝AUDIT_EXPORT FileObject，即使PROJECT坐标相同；补数据库关联校验防止直接SQL绕过，不只改DTO。既有FileObject用途/owner/Scope/Project/内容身份不可静默变更；专用文件一旦发布不得替换Hash/Size/Locator/归属或被普通清理删除。必要DB保护为本CR后续分项，尚未实现。
3. Audit owned尝试记录：固定Export、原Job、当前fencing/attempt、独立file_id及创建时点，绑定原acceptance/capture。一个Worker重试或接管使用不同file_id，禁止复用路径、跨token覆盖。它只是恢复坐标，不是成功或可下载凭据；无来源历史不猜回填。具体字段/唯一键/封口SQL另在Schema实施前精化。
4. Audit owned成功结果每Export最多一个，固定文件Ref、原Job/实际generation、完整成员摘要、规范manifest及其SHA-256、文件SHA-256/Size/MIME、发布时点、版本及发布Audit Ref。FileObject Ref每结果唯一。结果记录不可更新/删除/truncate；限制读取保留独立完整性/状态历史，不覆写原成功事实。manifest是bounded安全元数据而非正文或自由文本，验证与P01规范字节一致。
5. 跨模块以Document owned caller-UOW登记/读取/AVAILABLE状态转换Port和Jobs owned caller-UOW完成Port对接。Audit不得操作Document/Job私有表；数据库FK/触发器仅用于存储完整性且须明确模块拥有者，不当权限实现。旧自建UOW FilePublishService与JobLeaseService.finish不能直接嵌套为全流程原子命令。
6. 私有Locator在Document owned存储层生成；建议部署区域`generated/audit/deployment/objects/{bucket}/{file_id}`及对应temp，项目审计同样独立generated/audit/projects区域，不混入普通上传扫描。实现前核查正则/恢复扫描/目录权限/大小写/符号链接/重解析点边界。不接受客户端路径、原始文件名或Worker作为物理路径。

## 事务、权限与文件边界

- 先短事务真实当前授权→原Root/acceptance/pair→当前Lease→固定capture，登记精确尝试；commit后才进行受控私有临时写入。渲染期不用长事务持User/Job锁；需公开固定源读Port/封口一致性验证，重新开始或读回同一封口，不重采live事件。
- 文件写入必须bounded，flush/fsync后重新打开并验证全部Hash/Size，包含空JSONL合法场景；manifest单独有界保存/核验。磁盘不足/短写/异常无成功结果，部分文件保持不可见；禁止把I/O当数据库可回滚操作。
- 同卷不可覆盖提升在事务外完成；先做必要当前授权/Lease检查，但最终发布必须再次重核，不能把之前检查当跨事务凭据。文件提升成功后DB失败、撤权、取消或旧Worker失效，不存在可下载成功结果。
- 发布事务锁序必须与既有User→Project/member/department→Export→Queue→Job/Outbox→Lease/Attempt兼容，随后Document文件锁；实际锁竞争/死锁测试后确认。当前Job-first finish回调不可凭设计宣称安全，必要新增公共完成Port并独立验证。实际PG40P01只整UOW有限重试/重新授权；不盲重试未知commit或外部I/O。
- 同一短UOW内原文件元数据AVAILABLE、唯一Audit结果、Jobs终态、状态来源及发布Audit必须全有或全无；后置时点检查在提交前完成。失效/到期/取消/故障回滚所有数据库发布状态，提升文件仍私有，按实际尝试恢复或隔离。
- 当前License、enabled User、PM或DEPLOYMENT_ADMIN与实际项目事实在CAPTURE/RENDER/PUBLISH/下载各阶段核验；已注销提交Session不自动取消异步Job，但下载需要当前Session。原Actor、owner UUID、FK和Hash均不是授权。Admin无项目旁路，归档仅维护导出例外。

## 恢复、取消与访问

|观察|可见性|处理要求|
|---|---|---|
|只有尝试/无文件|不可下载|当前授权/Lease后重跑新file_id或登记失败|
|临时/部分文件|不可下载|不可截断当完整；校验后重跑或受控隔离|
|最终文件存在/无成功结果|不可下载|必须匹配原尝试与完整Hash；当前授权/token/取消重核后发布，不能以路径猜成功|
|新Worker接管/旧Worker仍在写|旧尝试不可发布|独立file_id；DB fencing阻止旧结果；当前代重用原capture而非旧可变文件|
|取消先获得Job锁|不可新发布|当前Worker确认或实际到期恢复；不能删除已发布结果伪装回滚|
|已成功后取消|原结果保留|返回原终态，不改历史|
|结果已发布/文件缺失或Hash损坏|读取失败关闭|保留成功历史、登记完整性异常/限制；不造文件|

下载通过Audit真实当前权限与结果查找后Document公共内容Port；无静态目录、绝对路径、Locator、Lease、worker或hint对外投影。内容HTTP扩展另写明确非Breaking契约/权限测试，不凭本CR开放POST/下载。实际清理需引用/保留/活动Lease/旧进程停写/目标账户ACL证明；生产不可恢复删除仍不授权。恢复不能自动复活FAILED/CANCELLED Job。

## 迁移与回滚

后续增量Alembic（当前head0039，实施时读取实际head）；ORM parity、up/down/offline review、空库和真实旧DOCUMENT数据验证。旧Upload/Parse/Document及FileObject Hash/定位完全保留，不回填虚构审计来源。维护备份/停写是发行前置，当前仅独立临时DB与临时目录。

down先固定顺序ACCESS EXCLUSIVE锁受影响表，任何专用文件、尝试或发布结果历史拒绝，不能仅检查成功结果或删除子表绕过。无新历史可撤增量；离线危险down关闭。新文件路径不搬迁旧内容，撤应用入口不删除历史；含新数据时只前滚修复或实施团队协调全备份恢复，不承诺自动回滚。

## 实施与客观验收

P03-A01：FileObject用途/归属及DocumentVersion/Upload防误绑Schema，真实空/有数据up/down/reup/不可变/有历史down拒绝及并发锁。P03-A02：Document公共caller-UOW元数据/受控存储与实际双Scope临时写/Hash读回/不覆盖/失败恢复；不用假权限证明全流程。P03-A03：Audit尝试/不可变结果Schema与Port，固定manifest/来源/引用完整性。随后Worker短事务渲染→实际文件→原子发布/下载/取消HTTP分项，逐项更新验收而不静态宣称PASS。

最低测试：双Scope空与非空、完整source/manifest/hash、误绑Document/Upload/跨项目/重标拒绝、新事件排除、磁盘不足/短写/DB故障/unknown commit、真实撤权/License拒绝/取消与publish两个锁顺序/到期接管/旧Worker、并发单结果/同代故障恢复/引用保持/损坏下载失败关闭。合成License、模拟磁盘不足与实际环境分别标注；128MiB/20并发性能和三平台/目标账户恢复不能用小fixture替代。新增依赖/服务/生产操作：无。

## 当前结果

2026-09-26 P03-A03-P04：own结果caller-UOW record/get及exact DTO，实际原Root/acceptance/完整capture/plan/发布Audit重核、共享纯canonical清单逐字节复核/双Scope empty/nonempty/真并发/原结果重放无写及真实Audit+结果故障整UOW回滚PASS。919项无失败（2环境跳过），0042/真实计划/renderer/实际文件元数据回归与开发wheel PASS。无Schema/API/依赖；Job/Lease/File/SystemActor/可信caller合成，实际Worker/文件/原子Job完成/HTTP仍待；CR整体IN_PROGRESS。下一项Jobs caller-UOW完成Port。

2026-09-26 P03-A03-P03：0042 own不可变唯一成功结果、原计划/文件opaque/发布Audit字段与时点、独立重建完整规范manifest字节/摘要及空文件规则PASS；实际空/旧双Scope计划与旧Doc/Version up/down/reup/parity/并发/历史与down写锁验证，914项无失败（2环境跳过）、真实计划/旧文件元数据回归/开发wheel PASS。Job/File/SystemActor refs合成、清单内存bytes，未证明正式身份/实际文件/Job/Lease/原子发布/HTTP；CR整体IN_PROGRESS。结果Repository及真正Worker发布继续。

### P03-A03-P03实施前精化：唯一成功结果

0042新增own `aud_export_results`，Export PK/own渲染计划唯一FK/file_id唯一opaque Ref、二进制file_sha256/size/MIME、manifest_version/原canonical manifest_bytes及二进制manifest_sha256、发布Audit唯一own FK、published_at。原Job/generation/成员源从不可变计划及capture反查，不重复可变坐标。触发器own Root锁→计划/封口/受理→发布Audit：计划Export/File必须一致、时点不得早于计划/capture；发布Audit必须SYSTEM形状、原actor/Scope/project/original trace、AUDIT_EXPORT_PUBLISHED/SUCCESS、jobs/JOB-01原Job、purpose、RUNNING→SUCCEEDED，时点处于plan与published之间。SYSTEM字段不是正式SystemActor配置证明，Owner必须以后核验真实运行身份。

manifest最多8192字节；由Root全部Spec/filter/version和capture固定事实及NEW文件摘要/size重建安全JSON，按C排序紧凑UTF8/UTC六位微秒/LF精确字节比较，拒绝空白/重复键/额外键/换字段/hash/time伪造，不仅jsonb语义相等。manifest/file hash32，size0..128MiB；空成员必须空文件标准SHA256。不可变结果无可修改成功状态；UPDATE/DELETE/TRUNCATE拒绝。ownFK不跨Owner私有表；当前Document AVAILABLE/元数据来源、物理Hash/实际Lease/Job终态/权限原子性由后续公开Port编排验证，Schema不能证明这些。

up保留0001～0041、旧计划不补结果；空表可down但先ACCESS EXCLUSIVE锁再检查，任何结果历史拒绝，offline down关闭。验收实际空/旧双Scope计划up/down/reup/parity/字段保持、规范manifest双Scope空与非空、源绑定/时点/摘要/唯一/真实并发/不可变及downgrade写锁竞争、失败版本不变；仅UUID临时数据库，无生产迁移。

2026-09-26 P03-A03-P02：真实submit/原pair/claim/capture/当前权限/Lease下RENDER计划登记，同代原计划/新代独立file、真并发、撤权/实际取消/到期接管/写后回滚与实际40P01限次恢复PASS；912项无失败（2环境跳过），既有真实capture回归及开发wheel通过。无Schema/API/依赖；License合成，唯一成功结果/物理渲染/原子发布/下载与正式发行仍待，CR整体IN_PROGRESS，见对应进度。

2026-09-26 P03-A03-P01执行结果：0041不可变计划/ORM、实际own受理与封口源、时点/形状/原Job/唯一/真并发单代次计划/新代次独立file/历史down拒绝与实际写锁PASS；904项无失败（2环境跳过）、0040/0039/文件元数据真实回归和开发wheel PASS。Job/Lease/File refs合成，实际当前Worker计划命令/唯一成功结果/发布/HTTP仍待，CR整体IN_PROGRESS。无生产迁移；详见对应进度。

### P03-A03-P01实施前精化：不可变渲染尝试

新增0041 `aud_export_render_attempts`，Audit owned子记录，不新增公开Root/API。字段render_attempt_id、export_id、原job_id、fencing_token、attempt_no、worker_ref、唯一file_id、固定member_count/membership_hash/membership_version、created_at。每(job_id,fencing_token)最多一个尝试与file_id；同代数据库重试读回原计划，不另换路径，部分写失败走Job失败/重试取得新代次，不在同租约内覆盖旧文件。新代次独立file_id复用原capture。file_id在写入前预分配，是跨Owner opaque Ref，不要求尚未创建的FileObject存在。

插入锁own Export根，要求实际acceptance/capture已存在，原job_id一致、源count/hash/version精确一致、时点有限且不早于请求/受理/封口；FK只连own capture/acceptance。UUID非零、token正BigInt、attempt正int、worker ASCII受控code。无私有Jobs/Document表读写，不把这些列/FK当真实当前Lease/Worker证明。UPDATE/DELETE/TRUNCATE全拒绝；0041空新表可down，先实际ACCESS EXCLUSIVE锁后检查，任何计划历史拒绝降级；离线down禁止，不回填旧Root或推测文件计划。完整caller当前授权/claim/Root/原pair/Lease→登记计划与后验在P02实现，未做不得标PASS。成功结果/manifest的独立Schema留下一分项，不用计划标成功。

2026-09-26 P03-A02-P02执行结果：Document owned caller-UOW元数据登记/查读/可用转换Port，原文件身份/内容与单一状态来源重核、真并发单次变化、实际共享锁、真实文件与post-Audit整UOW回滚PASS；902项无失败（2环境跳过）、0040与旧上传回归/开发wheel PASS。无新Schema/API。Export UUID/可信caller合成，未接真正Root/Lease/Job/唯一结果或下载；CR整体IN_PROGRESS，详见对应进度。

2026-09-26 P03-A02-P01执行结果：Document Application存储坐标/Hash Port与独立generated/audit Adapter，真实私有临时写/flush/fsync/Hash读回/不覆盖提升和final/实际linked恢复、损坏与扫描隔离PASS。新增14项，后端897项无失败（2环境跳过）、P01真实固定源内存字节与旧FilePublish回归/开发wheel PASS。无新Schema/API/生产操作。仅物理原语，元数据公共Port/真实Worker发布/下载待；ENOSPC模拟、未作满盘/空间性能/三平台证明。详见对应进度；整体IN_PROGRESS。

初始设计时仅完成变更决策和验收设计，无Migration、生产代码或公开API变更。后续实际实施见下列分项结果；A04-P02兼容探测证据保留。CR整体IN_PROGRESS，Gate3/质量/正式信任源/发行完整Scope仍未关闭。

2026-09-26 P03-A01执行结果：增量0040/ORM用途与归属、同PROJECT普通引用与通用状态/发布入口隔离、身份/内容/状态历史保护；实际空/旧数据up/down/reup/parity、并发down锁/历史拒绝PASS。883项无失败（2环境跳过）、四项真实链路回归及开发wheel PASS。旧DOCUMENT原值不变、无生产操作/公开API。细节见对应进度记录；合成owner不冒充实际Export根、File/Lease/下载证明。存储公共Port/尝试与成功结果/原子发布/完整交付仍待，CR整体IN_PROGRESS。
