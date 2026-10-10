# P07-A18 用户读取Service防御

2026-09-27编码前检查：Phase2/WBS AUT-04-A12-P07-A18；输入冻结64cdf09/0049/A17与A16全Auth84.717%；前置读取Service/真实Windows详情链已有。仅Auth只读Service四依赖/clock/篡改DTO/License/底层异常拒绝；实体UserGetQuery/UserReadView，原权限不变，无生产/API/Schema/算法/依赖变。

验收：依赖None构造拒绝；非法clock无Access/Repo；篡改Query无UOW/View无最终成功；License首/末拒绝固定码且无commit；Access/UOW enter/exit异常固定不可用；所有已进入UOW拒绝跟踪退出。Mock仅Port合同，不模拟成功SQL/真实授权撤销或回滚。

风险/回滚：撤测试无升级，完整unit本批实际跑；coverage/14PG/wheel/性能不重跑，旧raw/84.717%/Hash/90%保持不推算。正式trust/性能CR008 FAIL/Gate/可用包待；下一按完整缺口独立登录HTTP验证，不跨模块。

结果：6新增参数化方法，四缺依赖、五clock/clock异常、三篡改Query/六篡改View、首末License拒绝与三Access/UOW故障通过，无commit，已进入UOW均跟踪退出。完整1514unit/contract failures0/errors0/skipped2，exit0。无生产修改，Mock仅Port合同，不冒充SQL撤权/回滚；coverage/14PG/wheel/性能未跑，原84.717%与Hash7d6fbfc0…保持。下一P07-A19仅Login HTTP依赖/畸形JSON/Unicode/缺Client/身份错配与来源异常拒绝及密码擦除，无Cookie，不增加生产回退或篡改固定基线；其余Owner独立，后完整统一实测。
