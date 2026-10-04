# AUT-04-A12-P07-A10-P01 Session投影入口防御

2026-09-27；编码前检查：Phase2；WBS P07-A10-P01；输入冻结64cdf09、Schema0049及A09；前置已有Session投影与完整Auth缺口实测。模块Auth，实体User/Credential/Session只读投影；无API、权限、生产、Migration或依赖变化。

验收：缺构造依赖、非法用户ID、未开启真实SQLAlchemy事务均在SQL/Project读取前拒绝；公共转接优先绑定token来源且不降级，来源异常原样拒绝、不调用旧入口；无绑定入口才保留既有legacy调用。

范围调整：源码投影自行读取UTC时间，没有注入clock接口；本分项不人为增加clock接口。时间输入检查属于原SessionCredentialFacts，实际当前Credential绑定、Project来源错误与事务回滚留P02隔离PG验证。只证明入口/Port合同，不模拟成功SQL、不声称A10整体完成。

风险与回滚：仅测试，可撤新增测试，无升级；无覆盖率推算，不替代11实际链或90%验收；完整unit本批跑，coverage/PG/wheel/性能未跑。原测量Hash和性能FAIL、正式trust/Gate/可用包缺项保留。

执行结果：新增4参数化方法，全量1480unit，errors0/failures0、2既有跳过，exit0。真实未开启SQLAlchemy Session拒绝后仍无事务；Project未调用。绑定来源成功仅转交uid/token，异常和非callable不fallback；只有无绑定来源保留legacy。生产代码不变。本分项PASS，A10整体尚未完成；下一P02实际PG当前凭据和Project来源异常，再统一coverage实测。
