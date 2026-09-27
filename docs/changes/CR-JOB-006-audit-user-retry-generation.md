# CR-JOB-006：Audit用户重试新generation

P01（2026-09-27）：immutable Audit lineage/首次版本DTO及ORM/Migration0045内部完成，真实空/有数据up-down/错源-Query/不可变/回滚/有历史down拒绝、旧取消/Worker retry/Windows读取回归及1216后端无失败/2既有跳过、开发wheel669958通过。仅结构事实；Jobs实际FAILED/Attempt/expected_version与Owner当前授权/原子receipt/HTTP仍待。0044及64cdf09不改，未迁移生产；CR保持IN_PROGRESS，不得据此复活原Job或开API。

2026-09-27 / PROPOSED_FOR_IMPLEMENTATION，按用户持续自主授权执行；原冻结64cdf09与0044历史不改，当前仅设计，尚无新Schema/命令实施或PASS。

## 来源与冲突

冻结API-03要求用户retry创建新Job并引用原Job/新幂等Key，终态不能复活。当前Worker retry仅在原RUNNING Lease操作；Audit原Export绑定唯一Job/Outbox/Acceptance/结果。直接复用原enqueue只重放原Job，直接复制Job payload产生无法经Owner核验的孤儿。现库无持久新旧generation链。

## 比较与选择

- A：复活原FAILED或重用旧Job：违反终态/历史，拒绝。
- B：裸复制Job payload或另HTTP重新提交而不记录来源：丢失原源/可逆追溯/唯一首次响应，拒绝。
- C（选择）：Audit owned新不可变generation关系，以旧原源及Jobs安全技术事实为证明，创建新Export、新Job/Outbox/Acceptance与USER retry Audit，并同事务记不可变原响应/幂等收据。跨模块只Application Port，不让Audit直查Job私表；新旧Jobs只通过owned Jobs Port核对/加锁。

## 规则与边界

- 首个Owner仅Audit；不会顺手提供Document Parser/AI/RAG新Owner或扩Scope。ProjectManager且满足当前Audit Export权限/归属，DEPLOYMENT仅当前Admin；泛Job角色许可不能替代Owner业务授权。其他Owner保持JOB_NOT_RETRYABLE，仍保留未来Scope。
- 原Job必须FAILED且由原Jobs Attempt和Audit失败事实证明为可重试临时AUDIT_UNAVAILABLE；越权/Schema/签名/Secret/配置/来源损坏不重试。未结束/成功/取消不变更；不伪造失败分类。
- 当前Session/CSRF/License/Project状态与成员每次同UOW再核，包括同Key重放；原Job强expected_version核对、原Root/Jobs锁顺序对齐现安全序列，防与读取/取消/其他重试交错。
- 每个不同Key是明确的新generation；相同Actor/Scope/操作/源Job/Key重放首次202，不再创建。异载荷expected_version冲突保通用收据规则。新Job引用新Export/当前请求actor/trace；旧actor与旧Job固定留关系，Admin/项目权限不借旧actor绕过。
- 原spec/policy/固定时间窗口不隐式变化；新generation按该固定查询重新采集当前可授权Audit事实，不承诺重用原文件/捕获或字节相同，结果版本必须独立。这一差异明确写运行Contract，不改旧结果。
- 新lineage/结果快照结构不可变、非零ID/Scope/时间/一新结果一链及FK约束；旧数据不强制补伪造来源，已有普通Export不变。同事务创建任一点失败回滚全部，文件仍由既有Worker独立新generation产生。

## 迁移、风险、回滚与验收

新迁移须连续0045或实际当时head，空库/有数据up/down；down必须拒绝丢失已使用generation历史，不删除生产数据。正式Schema评审后再编码，不能本记录即PASS。原Job/旧Export/结果绝不改写；关闭新命令/Router可回滚，保新旧历史。新锁竞争/并发重放/源错配/当前权限变化为主要风险，使用实际PG串行/并发验证，不凭静态推断PASS。

验收分项：P01 immutable ORM/Migration/持久generation与首次结果快照；P02受权失败来源与原Job安全技术事实Port；P03原子命令/幂等/强版本/Audit及可重试安全投影；P04冻结HTTP；P05 Windows运行/缺依赖安全拒绝。每项前置、测试、版本记录与GitHub分别追溯。性能/正式账户/完整Owner/发行Gate独立，新增generation关系不关闭整体模块或Gate。
