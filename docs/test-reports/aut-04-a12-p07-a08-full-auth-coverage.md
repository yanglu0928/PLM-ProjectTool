# P07-A08 完整Auth实际覆盖

2026-09-27；0.1.0.dev0；Windows11/Python3.13.15/coverage7.13.5；输入1a88d8f/Schema0049；生产代码未改。

同轮完整1470unit/contract无失败/errors0/2既有符号链接账户权限跳过。11实际入口全部通过：

|入口|覆盖实际行为|
|---|---|
|P06A04P02A03 reset history、P06A04P02A04 change history|真实历史源/原子Service/并发/回滚与原发布|
|P05A07 Windows reset、P04A04 Windows change|实际工厂/HTTP/CSRF/受限及正常登录/幂等/失败关闭|
|P07A06 current-final|八真实live/count/User版本/SQL22012故障九表回滚/旧Session保留/擦除、两正常提交控制|
|AUT04A03 Windows user detail、AUT04A07 Windows user list|当前Admin/真实Session/目标/License/分页安全矩阵，两工厂/只读不写/构造异常|
|AUT04A09P05 Windows create|原HTTP first/replay/conflict/权限、真实SCRYPT新用户登录、缺正式trust拒绝|
|AUT04A10P03 Windows name|真实PATCH及Unicode/版本/重名/失败回滚；旧登录失败/新登录同UUID成功、旧Session仍有效|
|AUT04A11P05 Windows state|真实disable/enable、旧Session失效不复活、新登录与历史first重放、构造错误/缺trust拒绝|
|AUT03A07P03 Windows production login|真实临时Vault URL与PG账户，login/GET/renew/logout、Project撤权摘要、Cookie/CSRF、幂等冲突/并发及Audit|

Windows管理正向信任仍明确合成；生产login入口使用随机专属TEST凭据、临时DB/role并清理，不供给正式License/Vault材料。无客户数据/秘密外发、无生产库操作；不使用合成SQL成功替代实际验证。调用已有入口不意味着本项重做全部Schema升降级验收。

|完整范围|行|分支|门槛|
|---|---|---|---|
|完整Auth|3168/3364，94.174%|792/988，80.162%|未达到90%分支|
|原21密码文件/SCRYPT/进程预算|1031/1047，98.472%|350/384，91.146%|本范围通过|
|完整Windows工厂单列|362/369，98.103%|8/10，80%|尚有缺边|

旧全部文件/分母不变，没有pragma/omit/排除。原复用入口退出条件仅密码范围，本新入口增加实际完整Auth独立计数与90%判定，输出ALL_AUTH_THRESHOLD false并exit1，正确保留未完成。完整Auth综合90.993%不替代分支条件，不报告完整安全/Gate3通过。

独立raw `.poc-runtime/auth-security-full-auth-coverage/coverage.json` SHA256 `f6a571065b5220c0e9c74952bd8047ae6bca6d56bc9a0c6f3ea4aaa050f82f57`；前轮service-layout/rawHash57390683…及更早历史不覆。提交仅验证入口/安全统计/文档，不提交raw/日志/Secret/客户资料。

剩余196分支中，Session Service14、managed create11、create结果Repo10、User state9、Session投影8、Session HTTP6等优先；未覆盖边必须结合实际路径查验，不默认都是测量问题。姓名Repo从原未执行多数路径变为实际路径覆盖，但仍有5拒绝边。下一A09仅Session Service时间/结果/异常防御及未commit/UOW闭合，再完整实测；其他owner按独立任务补齐。

无生产源码、Migration/API/权限/算法/依赖/升级变化，兼容0049；回滚撤测量入口。wheel/性能/生产安装升级未跑，SCRYPT/default4保持；性能CR008 OPEN/FAIL、正式trust/目标账户/Server2025/Debian/UI/UAT/Gate与可用程序包仍未完成。
