# P07-A07-P02 AST等价排版与完整实际复验

2026-09-27；0.1.0.dev0；Windows11/Python3.13.15/coverage7.13.5；输入68b56e7，生产原版c004980，Schema0049与冻结64cdf09保留。

仅password_change/reset Service条件与raise分行；两文件分别通过相对c004980 AST dump完全相等（不含行位置），无判断、异常类型、算法、权限、事务顺序、API或Schema变化。首次补丁context不匹配工具整体拒绝，读回确认无文件改动后修正补丁；不是生产运行失败，不修改校验绕过测试。

同轮完整1470unit/contract无失败/errors0/2既有符号链接权限跳过；原五实际PG/Windows链全部通过，含reset/change history/atomic、两Windows HTTP链、八真实final故障九表全行回滚/Session保留/擦除与两真实提交控制，原发布回归保持。

|范围|行|分支|结论|
|---|---|---|---|
|完整原21密码文件含SCRYPT/进程预算|1031/1047，98.472%|350/384，91.146%|本范围>=90%通过|
|完整Auth|3119/3364，92.717%|773/988，78.239%|未达90%分支|
|完整Windows工厂单列|362/369，98.103%|8/10，80%|仍有缺边|

入口exit0仅密码范围门槛和全部声明测试通过，不能据此报告完整Auth安全/Gate3通过。行分母1017→1047、分支370→384均增加，没有缩减文件/分母、增加pragma/omit/排除或降低门槛；旧1007/1017与321/370保留。覆盖变化包含排版后静态分支与上下文退出对应改善，并非新增用例或新权限能力带来的提升。分行同时显露Service部分从未执行raise行，仍需真实缺口补测，不能把AST相等当全部测试完备。

独立guard审计重复既有测试：新guard84、raise85异常两次，记录84→76退出及84→85，missing guard=[]；独立with compact对照仍复现旧13→15缺/实际13→12，expanded无缺，AST及两个输入行为相同。审计脚本按源布局选择expanded新runtime，旧证据不覆盖。

原始忽略证据（不提交raw/日志/Secrets）：

- `.poc-runtime/auth-security-service-layout-coverage/coverage.json` SHA256 `57390683b6a0f69cb95fd25c851c760f1fe28e06ffb121237db387ba6e2c4306`。
- `.poc-runtime/auth-security-branch-audit-expanded/existing-coverage.json` SHA256 `2828c82b7cf46ca16025ec1485e134aaa458b0add8002074357f1b6fbbd60980`。
- 旧final-fault/branch-audit raw与Hash d45e9dd3…/ad862f75…均保留。

无Migration/生产升级/依赖变更，兼容0049；回滚仅把两文件恢复历史排版（保留其他用户修改），不能回滚冻结业务或数据。wheel/性能未跑，默认4与SCRYPT固定参数保持。当前完整Auth测量含全部文件，但只有五密码实际链，姓名修改Repo等其他功能缺实测覆盖；下一A08核对并纳入已有真实用户读取/列表、创建、姓名/状态、Session生命周期入口，随后补真实缺口。性能CR008 OPEN/FAIL、正式trust/目标账户/三平台/UI/安装升级/UAT/Gate与可用程序包未完成。
