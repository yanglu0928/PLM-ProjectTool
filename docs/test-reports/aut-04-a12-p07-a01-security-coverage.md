# AUT-04-A12-P07-A01 覆盖率实测报告

2026-09-27；0.1.0.dev0；Windows11/Python3.13.15/本机coverage7.13.5。生产源码基于5bfabe1未改；新增3项scrypt边界/异常测试及测量入口。启动coverage后才发现/import全部unit/contract；branch=True；没有新增omit/pragma/排除规则。测量是测试执行证据，不替代安全行为/平台/生产验收。

最终1433 tests，failures0/errors0/skipped2（既有符号链接权限场景）。密码21文件791/1017行=77.778%，204/370分支=55.135%，综合71.738%；全Auth2738/3334行=82.124%，576/974分支=59.138%，综合76.927%。两范围均未达90%，验证脚本exit1是正确的未达门槛状态，不是测试用例失败。Windows全组合根另报355/369行、7/10分支；不将其混入密码子集假称全部平台装配安全通过。

首次1430基线密码785/1017行、200/370分支；补测第一轮1433出现1个测试期望字符串错误（verify应固定verification而非hashing），没有修改生产异常行为；纠正测试后全量重测1433无失败。最终scrypt49/49行、12/12分支；覆盖率100%不证明全部输入组合、安全强度或原权限测试全部完成。

## 完整密码文件范围与实际分子/分母

路径相对apps/backend/src/plm_assistant；没有仅选通过文件。

|文件|行|分支|
|---|---|---|
|entrypoints/password_capacity.py|15/15|6/6|
|modules/auth/api/password_change.py|46/72|11/22|
|modules/auth/api/password_reset.py|43/71|10/28|
|modules/auth/application/password_capacity.py|26/26|9/10|
|modules/auth/application/password_change.py|115/137|40/70|
|modules/auth/application/password_change_actor.py|21/21|3/4|
|modules/auth/application/password_change_replay.py|46/47|17/18|
|modules/auth/application/password_change_result.py|28/28|2/2|
|modules/auth/application/password_reset.py|115/136|29/50|
|modules/auth/application/password_reset_replay.py|34/34|10/12|
|modules/auth/application/password_reset_result.py|29/29|2/2|
|modules/auth/application/ports/password_hash.py|10/10|0/0|
|modules/auth/application/ports/password_verify.py|5/5|1/2|
|modules/auth/infrastructure/password_change_access.py|31/69|5/32|
|modules/auth/infrastructure/password_change_repository.py|12/31|0/12|
|modules/auth/infrastructure/password_change_result_repository.py|54/72|17/24|
|modules/auth/infrastructure/password_issue_access.py|19/28|4/8|
|modules/auth/infrastructure/password_reset_access.py|29/42|9/20|
|modules/auth/infrastructure/password_reset_repository.py|11/28|0/14|
|modules/auth/infrastructure/password_reset_result_repository.py|53/67|17/22|
|modules/auth/infrastructure/scrypt_password.py|49/49|12/12|

Protocol hash有2行是coverage默认排除（ellipsis），非本轮新增例外；0分支文件不参与branch分母，不称分支100%。文件遗漏行/分支由测量入口逐文件输出，原完整JSON在忽略的.poc-runtime/auth-security-coverage/coverage.json，SHA256 c107495509db5e3c122a3720478722ecfd401cef5df0931b8352eb8cc866dd6e；无原始日志/客户文件/秘密上传。

## 下一补证与未达项

- 真实PG reset/change原子写、历史双源、撤权/Session竞争及Windows HTTP完整矩阵，必须在同一coverage测量中实际执行，不用mock数据库伪造命中。此前这些场景已独立验证，但未做coverage，因此不推算覆盖率。
- 关注两个持久层0/12及0/14分支、change access5/32、两个API10/28与11/22；同时保留全部source，不删除错误处理以提高分数。全Auth源单独测量，密码范围达标也不能宣称整个Auth/Gate3已达标。
- 全部权限数据组合、真实浏览器/TLS/持续负载、正式信任/目标账户、Server2025与发行仍待；Debian验证延期、兼容目标保留。CR-AUT008性能FAIL不变，默认容量4，不以覆盖率代替1秒性能标准。

本轮无生产源码/Migration/API/依赖或生产升级，unit已实际重测、wheel未重跑。整体项目未交付可用安装包，Gate3未关闭。
