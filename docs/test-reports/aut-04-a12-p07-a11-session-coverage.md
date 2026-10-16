# P07-A11 完整Auth覆盖实测

2026-09-27；Windows11/Python3.13.15/coverage7.13.5；完整unit与12隔离PG/Windows/Vault集成同轮。

|范围|行|分支|结论|
|---|---|---|---|
|完整Auth|3190/3364，94.828%|812/988，82.186%|90%分支未达|
|原21密码文件|1031/1047，98.472%|350/384，91.146%|仅本范围通过|
|完整Windows工厂另列|362/369|8/10|非全部安全证明|

1480测试failures0/errors0/skipped2；12实际入口全通过：reset-history、change-history、windows-reset、windows-password-change、current-final、windows-user-detail、windows-user-list、windows-user-create、windows-user-name-patch、windows-user-state、production-login、session-source。包含真实临时PG/current0049及原publication回归；正向License仍合成，不是正式信任供给或目标账户验收。

运行exit1原因ALL_AUTH_THRESHOLD false；综合91.958%不替代分支。完整文件/分母/90%保持，不排除缺口。本轮raw ignored路径.poc-runtime/auth-security-session-coverage/coverage.json，SHA256 a2fb0a38784ba85da924edc0e5ccfea6a87c72aaec14ac2c0c795948881fde37；旧A08 f6a571065b5220c0e9c74952bd8047ae6bca6d56bc9a0c6f3ea4aaa050f82f57复核不变。

剩余Auth176分支未覆盖，最前managed_user_create11、user_create_result_repository10、user_state9、sessionAPI6、user_read6；缺口不一概视为工具误报。下一User创建Service防御，Repo独立实际验证。性能/wheel未跑，CR008 OPEN/FAIL、正式trust/Gate3/可用包不关闭。
