# AUD-03-A04-P02：不可变导出/capture Schema

日期2026-09-26；Phase2；0.1.0.dev0；结果ISOLATED_SCHEMA_PASS。不是完整capture/实际权限/导出HTTP或发行PASS。

## 编码前检查 / Changed / Files

任务仅落实Audit owned三表及数据库完整性。输入冻结API-02/API-03、0005追加审计、head0036、A01设计、A03Spec、P01成员规范与实施前CR-AUD-001；前置满足。模块Audit，实体Export意图/成员/capture；无公开API/角色/依赖变更。CR实施前补充先根FOR UPDATE、先成员后capture、延迟提交完整性及down锁序；原冻结与0001～0036不改写。

新增export_orm.py、0037与3项unit、隔离verify.py；env/metadata注册三表，迁移head测试更新。aud_exports显式安全字段保存原Actor/Scope/Project/目的/窗口/筛选/版本/指纹；User/Project FK只是元数据归属，不授予权限。指纹只有形状约束，真实命令仍须从固定Spec计算/读回核对，不把合成测试'a'*64当实际意图一致性证明。

成员核验真实aud_events的Scope/Project/time及六项筛选，根行锁保持至事务结束，position和(event,Export)唯一。成员强制当前事务xid，deferred约束拒绝没有同事务capture的提交。capture不可变插入核验数量、连续位置/time UUID降序、成员xid、P01摘要及不早于请求的时间，空集合合法；封口后连同事务也禁止再加成员。三表禁止UPDATE/DELETE/TRUNCATE；capture唯一Export，不可替换首个成功集合。旧事件/Job表保持不变。

## Migration / API / Tests / Result

0037只新增三表/约束/触发器/函数。down先父到子ACCESS EXCLUSIVE锁全部三表，任何意图（含待处理）或capture历史即拒绝，不删历史/不回填；离线down关闭。生产升级需备份/维护窗口，只在隔离UUID临时库实测，本轮未操作生产。

Win11/PostgreSQL18实际验证空库up/down/re-up、旧Audit有数据升级/降级/再升级且原行完全一致、ORM metadata无diff、错误Scope/Project/目的/窗口/筛选/版本/零UUID拒绝；真实源Scope/time/全部筛选、未封口延迟提交回滚、count/hash/位置/排序/UUID并列顺序、重复成员、早capture拒绝、合法项目/空集合；三表修改/删除/truncate拒绝；三表down并发写锁、根锁等待、真实等待的同一append在seal提交后安全拒绝；导出历史拒绝down且head/所有意图原行不变。独立库finally清理，无客户数据。

后端816项无失败，2项既有符号链接环境跳过，含新增3项Schema/离线down/历史守卫unit。初次全量出现旧head预期0036失败，已更新0037后重跑通过；Job历史回归初次固定旧head断言失败，已改成实际ScriptDirectory head，验证迁移多步回滚后版本仍不变，重跑通过。真实Job/Outbox部署范围、唯一/旧行、租约/投递/双表锁、Document Parse限制回归PASS；Windows显式平台审计真实数据库HTTP回归PASS（License/key合成）。未运行新导出权限/真正单statement选取/晚提交/回填/性能/文件交付/API验收。

开发wheel PASS，SHA-256：`1bcccb6ba0a280d3bbd085071eaad08bd94bc80aefc21e1d456d91da8945ddf1`，非正式安装包。新增Schema不保证客户端选全了合法事件；P03必须单statement选择并验证集合完整/late commit。SQL摘要string_agg占O(n)数据库内存，实际上限/性能在capture阶段验收，不作常量空间/P95承诺。

## Known Issues / Compatibility / Next

API/权限/依赖不变；默认导出入口未开放。正式生产材料、业务Owner、真实质量/性能/Gate3/UAT/可用包未完成。仅Win11实测，Server2025未验，Debian13暂缓但正式目标保留。

下一项AUD-03-A04-P03：可信调用方事务的真实单SQL capture/replay/读回完整性，固定原Spec重验、晚提交/回填/新增事件排除与故障全回滚；之后A05真实权限/幂等/Job编排，不直接开放当前Schema。
