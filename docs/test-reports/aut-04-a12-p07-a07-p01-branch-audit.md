# P07-A07-P01 事务内单行异常测量审计

2026-09-27；0.1.0.dev0；Windows11/Python3.13.15/coverage7.13.5（默认CTracer），输入c004980；无生产改变。

执行现有`test_bad_source_or_truthy_verifier_never_reaches_global_lock`：独立coverage和独立sys.settrace各实际通过一次，每次含3组source/matched输入；trace仅收集行/exception坐标，不读密码/locals/异常正文。source错误两次在生产83行抛异常，coverage实际记录83→75（with退出）但missing_branches列83→162（外层exception）。不是测试没有触发拒绝。

|独立合成对照|AST等价与输入行为|guard缺边|
|---|---|---|
|普通try/两个except compact与expanded|相等，False accepted/True denied|两者无|
|retry-handler/finally compact与expanded|归一化自调用名后相等，False accepted/True抛ValueError|两者无|
|with事务形态compact与expanded|相等，False accepted/True抛ValueError|compact列13→15未覆，但实际仅13→12上下文退出；expanded无该guard缺边|

证明范围仅这个Python/coverage组合、已检查guard及最小结构：拒绝执行事实与报告的单行分支坐标存在对应差异；不能据此将49个密码未覆边或230个Auth未覆边都称为伪缺口，更不能关闭90%要求。其他真实缺用例仍保留。

首次普通fixture没有复现，随后retry/finally仍没有，加入with后才复现；保三个对照文件及脚本，不删失败假设证据。最终入口exit0，所有assert成立。新独立忽略runtime原证据：

- `.poc-runtime/auth-security-branch-audit/with-fixture-coverage.json` SHA256 `bab3e133a5cf0bc1130f359b5040976a3da5454c746793b137c367f3cd7a871b`。
- `.poc-runtime/auth-security-branch-audit/existing-coverage.json` SHA256 `ad862f7534de1efe9874dffebe64556342f3b5f77df3fdff74da48d4c5b63cb0`。

只记录安全统计/来源/验证入口，raw/日志/秘密不提交。完整unit/五实际链/全量coverage/wheel/性能本批未跑，最近1470与五链通过/密码86.757%/全Auth76.386%及旧Hashd45e9dd3…保持。无生产/Migration/API/权限/算法/依赖/升级变化，兼容0049；回滚撤验证入口。

下一P02按本地证据，仅password_change/reset Service事务内同类单行guard及raise拆行，先记录、确认相对c004980 AST完全相等，再完整unit、五PG/Windows链和原完整范围覆盖复验。若AST不同停止修改，不扩大逻辑修复；不新增pragma/omit/排除、不降低90%，不得比较不同分母却冒充纯用例覆盖改善。其余真实缺口、性能CR008 OPEN/FAIL/默认4、正式材料/环境/UI/安装升级/UAT/Gate/可用程序包仍待。
