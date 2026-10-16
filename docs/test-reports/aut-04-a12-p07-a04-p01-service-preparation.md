# P07-A04-P01 准备阶段Service防御验收

2026-09-27；0.1.0.dev0；Windows11/Python3.13.15；生产基线ccfa0cc/0049不改。补充已有reset/change history fixtures，新增6个参数化测试方法。

|边界|reset|change|实际断言|
|---|---|---|---|
|必要依赖None|9项|8项|构造直接拒绝|
|history hint类型/op/status、first ID、source/actor错误|6类|7类（BEFORE/AFTER源分别错误）|静态错误，未KDF/global/reserve/repo/commit，UOW闭合/密码擦除|
|clock None/True/string/无时区datetime|4类|4类|未调用身份Port/KDF/reserve/repo/commit，密码擦除|

最终完整1447 unit/contract测试，failures0/errors0，skipped2（既有符号链接账户权限场景），exit0。事务Spy记录准备UOW并逐个assert commit未调用，不能只凭repo未调用推断无commit；本轮是模拟Port违约测试，未声称实际SQL回滚。原实际PG原子/history及Windows HTTP证据保持P07A03。

中途两项测试错误：OTHER_OPERATION不符合V1操作格式，IdempotencyResult构造先拒绝，未到Service。改用另一个实际合法op产生合法但错配收据后全量复验；生产校验不放宽。强化commit断言后再次完整1447无失败，未隐瞒修复过程。

本轮不重测coverage、四PG集成或wheel；不能推算新的90%达标，原密码分支79.189%仍为最近实测结果。无生产源码/Migration/API/权限/算法/依赖变更或升级，默认4与性能CR-AUT008 FAIL保持。A04写阶段repo/result/current-final-proof边界待A04-P02，后续完整真实PG覆盖复验；全Auth/正式trust/三平台/安装/UAT/Gate3及可用包尚未完成。
