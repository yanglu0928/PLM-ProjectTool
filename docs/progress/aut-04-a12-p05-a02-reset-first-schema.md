# AUT-04-A12-P05-A02 重置first Schema

编码前检查：Phase2/Gate3未通过；基线64cdf09/API02/CR-AUT007/DEC317，前置c7f1bb3 strict15字段pure契约已验；Auth resetfirst ORM/Alembic0049，0001～0048不改写。实体User/actor/前后Credential/Audit/Session，新内部来源表，无公开API/依赖/权限变化。

DEC-20260927-318：15字段独立不可变first；actor仍ENABLED Admin，other actor current normalCredential、self after受限时核before normalCredential，允许disabled目标/count0，不更新状态。DB只证明坐标/当前源/Audit/版本/全撤销与计数，不代Session-CSRF/License当前授权。锁User/actor按UUID序；server acceptedAt，UPDATE/DELETE/TRUNCATE拒绝，down锁表非空拒绝。

验收：真实空有数据0048↔0049/no backfill/旧十三表不变/ORM parity；正常2Session含expired/disabled0/self源、wrong normal after/actor/flag/版本/state/Audit/time/count拒绝、实际写后回滚、唯一并发/历史保护/非空down保head。目标不可用生产环境不凭空PASS；正式升级备份停写，回滚撤入口保历史非空不down。完整KDFsource/原子命令/HTTP/三平台/包/Gate待。

## 实施与验证

新增0049/注册ORM15字段和对应head/新表登记，旧0001～0048不改写。五旧Schema validator仅当前head断言推进49，原来源/历史/回滚断言保留；change日志文字改为current head防误报48。

1374 tests无失败（2既有跳过）。真实空库及有数据0048-49往返/no backfill、十三旧表保持/ORM列类型nullable-PK-FK-check-unique-default一致；正常两Session含expired、disabled0保持停用、自Admin重置新受限源均可登记。坏actor/角色/state、前后凭据/version/trace/Audit/count/changedAt/future-infinite accepted拒绝；实际合法first INSERT后故障回滚，真实完整转换后normal-new flag错误/other受限Admin/self before受限拒绝并全夹具回滚。

错误审计分别actual Audit Port append后source拒绝，覆盖actor/action/trace/before-after/outcome。首轮错误outcome夹具写FAILURE不在Audit允许枚举，被DTO提前拒绝；改为合法FAILED后验证真正source P0001，未放宽生产规则。两独立PG连接同源争用仅一first、后来改名不改历史、UPDATE/DELETE/TRUNCATE及非空down拒绝保head49。

五旧Schema（create/state/change/cancel/retry）实际回归、Windows改密actualFactory普通/受限及登录链/构造故障/缺正式信任拒绝、原双Scope发布通过。开发wheel740067 bytes，SHA256 `70b4dbb7642bdbfc4b12ce440305ad4f79e95e94911da2557d24c7fc4d24266c`，不是安装包。

内部Schema PASS，TEST_ONLY凭据复制/SQL转换只证明来源，不证明真临时密码/原子reset/当前Admin-CSRF-License/HTTP/完整发行。无生产迁移/API/依赖/权限变更；正式升级备份停写0049，历史非空不得down。下一P05A03真实reset first Repository与当次临时密码Scrypt来源，后续完整命令/self末核/HTTP/性能/三平台/包/Gate保留。
