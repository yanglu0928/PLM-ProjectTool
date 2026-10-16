# P07-A17 Session HTTP拒绝与安全响应

2026-09-27编码前检查：Phase2/WBS AUT-04-A12-P07-A17；输入冻结64cdf09/0049/A16完整Auth84.717%分支；前置现有Session GET/renew/logout与真实Windows登录链。仅Auth HTTP契约测试，实体SessionPrincipal/LoginSessionView与原Service Port；无生产/API规则/权限/Schema/算法/依赖变更。

验收：三router缺依赖构造拒绝；GET validate异常/投影身份错配/来源异常/非法public flag固定错误；renew validate/投影拒绝不调用renew，renew自身错误无新Cookie；logout非exact True不清Cookie，Service异常按原固定码返回；所有错误有trace且无私有详情/Token/Set-Cookie。明确Mock只HTTP Port合同，不模拟SQL成功、真实提交或浏览器TLS。

风险/回滚：新增contract测试可撤，无升级；完整unit/contract本批实际跑，14PG/coverage/wheel/性能不重跑，原raw/Hash/90%与84.717%保持不推算。正式trust/CR008性能FAIL/Gate/可用包待。

结果：新增7参数化方法；三router八缺依赖拒绝，GET四故障、renew validate四/投影三/Service四、logout四非True与三异常安全响应通过。错误Envelope含有效trace、固定error.code，无Set-Cookie/Token/私有详情；renew前置失败无renew调用。完整1508unit/contract failures0/errors0/skipped2，exit0。Mock只HTTP合同，无生产变更，coverage/14PG/wheel/性能本批未跑，原84.717%/Hash7d6fbfc0…保持。下一P07-A18仅User read Service依赖/clock/DTO异常/最终License拒绝无commit与闭合；余owner独立，后统一完整实测，不提前关Gate/包。
