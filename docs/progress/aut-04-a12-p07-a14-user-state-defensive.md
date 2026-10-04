# P07-A14 用户状态Service防御

2026-09-27编码前检查：Phase2，WBS AUT-04-A12-P07-A14；输入冻结64cdf09/0049/A13及A11全Auth缺口；前置UserState Service已有真实Windows链。模块Auth，实体User/Session/ActorProof/first/Receipt/Audit；无生产/API/权限/Schema/算法/依赖变更。

验收：七依赖None、非法clock/ActorProof、坏收据/首次结果引用、Repo返回view/状态/版本/count错误、首次结果归属与Audit错配全部固定拒绝，不commit、不继续complete；已经进入UOW均闭合。Mock仅Port合同，不模拟成功SQL/实际回滚；真实Repo独立下一任务。

风险/回滚：撤测试无升级；完整unit实际跑，coverage/13PG/wheel/性能本批不重跑，旧raw/Hash/82.186%不推算，90%保持。正式trust/性能CR008 FAIL/Gate/可用包未完成。

结果：6新增参数化方法，七依赖、六clock/proof、四receipt/first、八change响应、五first/Audit来源、最终改变的proof拒绝，最后一种complete已调用但不commit，其他列明路径不继续写。所有已进入UOW均退出。完整1497unit failures0/errors0/skipped2、exit0。仅Port合同，无真实SQL回滚新证据；生产无变化。下一P07-A15仅User状态Access/Repository的前SQL违约与异常，真实缺行/自停用末核另分项，再13+实际链统一覆盖；coverage/性能/wheel未跑，原82.186%与Hash/90%保持，Gate/可用包未完成。
