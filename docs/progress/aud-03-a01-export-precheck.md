# AUD-03-A01：审计导出前置核查与实施设计

日期2026-09-26；Phase2；版本0.1.0.dev0。结果：PRECHECK_GAPS_DOCUMENTED；公开导出PRECONDITION_BLOCKED，不是导出PASS。当前仍可继续必要前置任务。

## 输入、证据与差异

来源冻结API-02/AUDIT_EXPORT（两范围POST、S/L/C/I/A、202 JobRef、用途/范围受审、脱敏、请求/完成/失败审计）、API-03 Job/结果引用/协作取消、DM-02 Audit追加与归档允许审计导出、DM-04 Job/Outbox、现有A01～A05受权查询和安全游标。原冻结64cdf09保留。

1. DM-04/Job的scope明确为GLOBAL、PROJECT或DEPLOYMENT；API-03管理面明确DEPLOYMENT/GLOBAL。当前jobs/infrastructure/orm.py JobRow、OutboxEventRow scope CHECK只允许GLOBAL/PROJECT，migration head0035亦如此。
2. validation/aud-03-a01-export-precheck/verify.py在own UUID PostgreSQL库升级到0035，实际部署Job及Outbox插入分别被ck_job_jobs__scope、ck_job_outbox_events__scope拒绝，零行持久化；finally清理own库。证据确认实现遗漏，不能把DEPLOYMENT重标GLOBAL来过关。
3. 现有ParseJobQueue只允许Document GLOBAL/PROJECT且绑定DocumentVersion，不可复用假Document/任意payload作为审计导出。已有租约/fencing、Outbox投递可复用其内部公共Contract，但没有Audit导出enqueue、immutable source membership、受权结果Artifact/下载或通用Job HTTP。
4. 当前Audit查询只固定time window/稳定keyset，不固定数据库MVCC集合。发生迟提交或历史时间回填时，逐页查询不是审计快照。新增普通文件正文/静态目录也不能替代受权导出交付。

## 设计要求（后续逐项实施，不声明已存在）

- 两个固定路径：项目只当前PM/显式成员，部署只DeploymentAdmin且DEPLOYMENT，无项目旁路。License、Session、CSRF、幂等、用途/筛选白名单均在受权事务检查。归档项目审计导出为明确维护例外，不放开普通业务Job。
- 用途采用受控code及有上限人工说明，说明不复制到Audit自由正文/Job payload；具体白名单在请求合同任务收敛，不接受客户端SQL/字段列表/路径/endpoint或外发选项。默认导出格式拟UTF-8 JSONL与最小manifest，避免CSV公式注入；发行格式说明与实际实现必须一致。
- 请求固定Actor/Scope/Project、完整范围和筛选指纹、政策/投影版本、ExportRef。Audit唯一拥有导出聚合及源集合；Job仅最小ExportRef/政策引用，无事件正文、原始Session/Token/Secret、文件路径或客户资料副本。幂等receipt引用不可变首次ExportRef/JobRef，不重复请求Audit。
- source membership须真正固定：在明确capture事务用单次受权数据库statement固定所有合格event ID及顺序（UTC time/UUID），Seal后禁止增删/重排/换Scope。选取时点与请求时间分别记录在manifest，不谎称capture发生在POST瞬间。快照来源只追加不可变AuditEvent；安全projection在受控投影版本下读回，校验count/来源Scope/hash。新事件、迟提交、回填不能进入已封口集合。失败不得截断后声称完整。
- capture大集合的事务耗时、空间/行数上限与批处理策略需要实际性能验证，不能为凑202/P95虚报。若capture后移至Worker，需有持久capture阶段/重试幂等与原始Actor当前权限重新核验；未seal不得生成可下载结果。首轮和重试的实际snapshot身份不可静默替换。
- Worker只持租约fencing和最小引用；每个安全检查点及发布前由Owner用真实当前用户/角色/成员/部门/Scope事实重新核验。不能把历史Actor UUID或请求Audit当权限。是否需要原Session仍有效、怎样使用Auth提供的非secret授权引用，由专门Port设计/测试明确，禁止存原始Token或调用已有Query绕过真实权限。
- 完成发布必须同事务验证最新租约/未取消、固定source hash/count、文件hash/长度/受控artifact归属及当前权限，再关联不可变结果Ref、Job成功和完成Audit；任何失败全部回滚。过期Worker不得发布或覆盖；失败/取消保留历史并记安全Audit，不能谎称外部文件已回滚。
- 文件存储通过Owner公开Port及受控FileObject生命周期，不跨模块写Document/File表。只受权API按固定结果引用交付，访问时当前License/Session/Scope/权限重验，hash与AVAILABLE/归属核对；无静态路径/通用未授权download。冻结API-03 JobView仅result ref，若新增下载资源路径须单独API CR，不能静默扩写冻结合同。
- Job重试创建新generation/引用原结果，不复活终态；后续重试策略必须明确重用哪个seal snapshot或新capture，新集合不能冒充原幂等结果。取消和临时文件清理需崩溃对账，普通用户不能改/删Audit历史；本项不实施自动Audit retention删除。

## 分项实施与验收

1. AUD-03-A02：先登记CR-JOB-001并核对正式基线，恢复Job/Outbox的DEPLOYMENT scope。ORM+增量migration、空/有数据up/down/re-up；含DEPLOYMENT数据down拒绝，表锁防检查后并发插入。既有GLOBAL/PROJECT唯一/Scope/claim/lease/outbox回归，原Document Parse仍拒DEPLOYMENT。
2. AUD-03-A03：导出请求/用途/Scope/权限/维护例外与Worker授权Port合同；不以DTO作为当前权限证明。
3. AUD-03-A04：导出聚合/不可变capture membership及完整性存储，必要CR-AUD-001，Schema/迁移/源归属/封口/late commit/回填/并发/空集合验证。
4. AUD-03-A05：内部受权请求+enqueue Port+Audit+receipt原子/并发重放，任一失败不留半成品。
5. AUD-03-A06：Worker capture/render/lease/发布、取消/故障/恢复/真实权限再验，跨模块结果安全生命周期和输出空间限制。
6. AUD-03-A07：可选两个POST HTTP、Job安全结果/下载Contract与实际接线；默认关闭、Windows显式装配与缺信任源关闭、权限/归档/撤权/到期/反篡改/性能。

Role×API×Project、重放异载荷、晚提交/新增事件、过期Lease/双Worker、读/写故障、磁盘满、取消、不可用源、错误Scope、恢复历史和脱敏零泄漏都必须实际验证。分项通过不能替代完整导出/UAT/Gate证据。

## 本轮验收、兼容性与下一任务

本轮只设计与新隔离库证据，未改变生产代码/数据库/API/角色/依赖；无Migration或升级动作。现有794项后端测试的上轮结果保留，本轮未将其重跑冒充新导出验收。新增前置复现脚本实际PASS（确认缺口），导出仍未实施。Windows11执行，Server2025未验、Debian13暂不验证，目标不变。原Scope与所有正式发行材料/质量/性能/Gate/UAT/可用程序包要求保留。

下一项AUD-03-A02 / CR-JOB-001：修复已证实的DEPLOYMENT实现遗漏，无需逐项人工批准，先记录变更和基线影响再迁移/验证/同步。
