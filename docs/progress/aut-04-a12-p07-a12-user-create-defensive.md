# P07-A12 用户创建Service防御

2026-09-27编码前检查：Phase2；WBS AUT-04-A12-P07-A12；输入冻结64cdf09/0049与A11完整Auth82.186%分支；前置已有创建Service/实际Windows创建链。仅Auth Application Service单元合同测试，实体User/Credential/first/Receipt/Audit；无生产/API/权限/Schema/算法/依赖变更。

验收：九必需依赖None拒绝；坏收据/原结果/验证结果拒绝；错误User/Credential/激活/Audit/四首次来源坐标无commit；非法clock无reserve；hash合同类型、参数类型/范围错误在创建前拒绝；全部已持有bytearray错误路径擦除、进入UOW时闭合。Mock仅Port合同控制，不模拟SQL或宣称真实数据库回滚。

风险/回滚：撤新增unit无升级。完整unit本批实际跑；coverage/12PG/wheel/性能本批不重跑，旧raw/Hash/90%保持，不推算新覆盖。原性能FAIL/正式trust/Gate/可用包待；下一UserCreateResult Repository防御与实际SQL另任务。

结果：新增6参数化方法；九依赖、三收据、四重放结果、八写来源、四clock、十二hash合同案例通过，已进入UOW均退出且无commit/密码清零。完整1486unit failures0/errors0/skipped2，exit0。仅Port合同，未实施生产修改；coverage/12PG/wheel/性能未跑，最近A11全Auth82.186%与a2fb0a38…保持。下一P07-A13 Result Repository前SQL拒绝与底层异常边界，实际SQL缺记录/原Credential错配另分项，不mock成功SQL。
