# P07-A16 用户管理增量后完整Auth实测

2026-09-27编码前检查：Phase2/WBS AUT-04-A12-P07-A16；输入冻结64cdf09/0049/A11原全Auth82.186%与A12～A15；前置创建结果及自停用真实故障已验。仅完整Auth/Windows组合覆盖验证，无生产/API/权限/Schema/算法/依赖变化。

验收：全量unit与原12实际链+create-result-source+state-final-source共14链同轮；完整Auth原文件/分母与独立90%行AND分支保持，原21密码/工厂另列；新runtime auth-security-state-coverage保所有旧raw/Hash。测试失败或覆盖不足exit1，不把综合率/局部过线当整体PASS。

风险/回滚：仅新增入口可撤，无升级；实际资源由原owned fixture清理，License合成不代表正式来源。本批不跑性能/wheel；性能CR008 FAIL/正式trust/Gate/可用包待，不改变全目标。

结果：1501unit failures0/errors0/skipped2，14实际链全通过；完整Auth3200/3364行95.125%、837/988分支84.717%，综合92.762%不替代分支，ALL_AUTH_THRESHOLD false/exit1。原密码1031/1047行98.472%、350/384分支91.146%保持；工厂362/369行、8/10分支另列。完整文件/分母/90%不变，旧A11 raw Hash复核a2fb0a38…不覆；新JSON SHA256 7d6fbfc0499a6a52d01eb844311e78e14a1338e2d87b135d2f91ec34a91e20c3，ignored runtime不上传。

剩余151 Auth分支；SessionHTTP6、managed_user_create6（无missing lines）、user_read6、user_name_patch_repository5等，不一概认定工具误报。下一P07-A17仅Session HTTP依赖/来源异常/身份错配/logout非True/renew异常拒绝、错误不泄露和失败无Set-Cookie，真实原链保留。生产无变，性能/wheel未跑，正式trust/Gate/可用包未完成。
