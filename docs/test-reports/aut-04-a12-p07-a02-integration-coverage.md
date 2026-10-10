# AUT-04-A12-P07-A02 实际集成覆盖率报告

2026-09-27；0.1.0.dev0；Windows11/Python3.13.15/coverage7.13.5；输入35072d0，生产源码不改，Schema0049。先启动branch coverage再发现执行完整unit/contract与四组实际隔离PG/Windows入口，没有omit/pragma/删源码路径。

1433 tests无失败/errors0/2既有跳过。以下四入口实际完成并断言通过：reset-history（包含原reset atomic）、change-history（包含原change atomic）、windows-reset、windows-password-change。包含真实Scrypt、当前授权/CSRF/撤权与Session竞争、原first历史来源/幂等、实际原子写后与commit故障/恢复、Cookie/ETag及缺信任/构造失败、旧Windows状态与双Scope文件发布回归。正向角色/信任材料明确合成，不是正式生产账户证据。

密码同一21文件968/1017行=95.182%，282/370分支=76.216%，综合90.123%；**综合超过90不抵消分支不足**，严格行/分支均90%仍FAIL/exit1。全Auth3056/3334行=91.662%、705/974分支=72.382%；Windows全工厂362/369行与8/10分支单列，均不能宣布全Auth/Gate3安全达标。

## 同一21文件完整分母

相对apps/backend/src/plm_assistant；A01相同范围，没有缩小到高分文件。

|文件|行|分支|
|---|---|---|
|entrypoints/password_capacity.py|15/15|6/6|
|modules/auth/api/password_change.py|65/72|18/22|
|modules/auth/api/password_reset.py|64/71|21/28|
|modules/auth/application/password_capacity.py|26/26|9/10|
|modules/auth/application/password_change.py|131/137|48/70|
|modules/auth/application/password_change_actor.py|21/21|3/4|
|modules/auth/application/password_change_replay.py|46/47|17/18|
|modules/auth/application/password_change_result.py|28/28|2/2|
|modules/auth/application/password_reset.py|129/136|35/50|
|modules/auth/application/password_reset_replay.py|34/34|10/12|
|modules/auth/application/password_reset_result.py|29/29|2/2|
|modules/auth/application/ports/password_hash.py|10/10|0/0|
|modules/auth/application/ports/password_verify.py|5/5|1/2|
|modules/auth/infrastructure/password_change_access.py|62/69|20/32|
|modules/auth/infrastructure/password_change_repository.py|28/31|6/12|
|modules/auth/infrastructure/password_change_result_repository.py|68/72|22/24|
|modules/auth/infrastructure/password_issue_access.py|26/28|6/8|
|modules/auth/infrastructure/password_reset_access.py|41/42|15/20|
|modules/auth/infrastructure/password_reset_repository.py|27/28|9/14|
|modules/auth/infrastructure/password_reset_result_repository.py|64/67|20/22|
|modules/auth/infrastructure/scrypt_password.py|49/49|12/12|

原完整JSON另存.poc-runtime/auth-security-integration-coverage/coverage.json，SHA256 edf38e4eb929907d12e8752ba9af82fcf00fab9feffb2bf3f6079fa42ab4261d。A01原JSONHash c107495509db5e3c122a3720478722ecfd401cef5df0931b8352eb8cc866dd6e复核未覆盖；原报告、基线及历史保留。只同步聚合数字/源码范围，不上传Secret/SQL参数/连接字符串/客户内容/运行日志。默认Protocol排除2行仍明确，与A01一致，未增加忽略规则。

下一P07A03按实际缺口补HTTP不可信principal/result、postcommit Session异常与依赖缺失等边界；Application Service/适配器防御分支分项补充，不模拟成功SQL假称PG证据。权限输入矩阵仍需独立行为审查，覆盖率不等于所有短路组合都已测试。无生产源码/Migration/API/依赖/升级；本轮unit及真实集成已跑，wheel未重跑。性能CR008仍FAIL、默认4，完整安全/正式trust/目标账户/平台/安装包/Gate3未完成。
