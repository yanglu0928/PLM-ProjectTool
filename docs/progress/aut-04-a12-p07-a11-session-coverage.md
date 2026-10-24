# P07-A11 完整Auth同轮覆盖复验

2026-09-27编码前检查：Phase2；WBS AUT-04-A12-P07-A11；输入0049/冻结64cdf09/P07A08完整Auth实测及A09/A10；前置实际投影验证已通过。涉及Auth及原Windows组合测量，无生产/API/权限/Schema/依赖修改。

验收：完整unit与原11实际PG/Windows/Vault链加A10P02共12链同轮执行；Auth所有文件保留、行与分支分别至少90%检查，密码原范围/工厂另列。新runtime auth-security-session-coverage保历史raw/Hash；无omit/pragma/门槛降低，无综合率替代分支。

风险与回滚：新增验证入口可撤，无升级；实际环境失败或覆盖未达均exit1不标PASS；实际临时资源原fixture所有权清理，不动生产/客户数据。正式trust/性能CR008 FAIL、Gate/可用包未完成；本批不跑性能/wheel。

结果：1480unit，failures0/errors0/skipped2；12实际链全部通过。完整Auth3190/3364行94.828%、812/988分支82.186%，综合91.958%不替代分支，ALL_AUTH_THRESHOLD false/exit1。原密码范围1031/1047行98.472%、350/384分支91.146%保持；Windows工厂362/369行、8/10分支单列。生产和分母不变；旧A08 Hash复核未变，本轮JSON SHA256 a2fb0a38784ba85da924edc0e5ccfea6a87c72aaec14ac2c0c795948881fde37，仅ignored runtime不提交。

剩余最多分支：managed_user_create11、user_create_result_repository10、user_state9、SessionHTTP6、user_read6。Session Service和投影已不在前十；不能认为所有剩余边仅测量误差。下一P07-A12仅User创建Service依赖/收据/原结果/写入来源拒绝与擦除及无commit，Repo真实SQL另任务，保原90%与全Scope。性能/wheel未跑，正式trust/Gate/交付未完成。
