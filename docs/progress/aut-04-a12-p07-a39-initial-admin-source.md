# P07-A39 初始管理员数据库来源

2026-09-27编码前检查：Phase2/AUT-04-A12-P07-A39；输入冻结64cdf09/0049、A38Service测试、原aut-03-a06-initial-admin临时PG验证。仅Repo真实inactive/错误/缺Session来源与原实际数据库初始化回归，不改生产/API/权限/Schema/依赖。

验收：claim_empty/create合法调用遇错误/真实inactive Session原RuntimeError且不启动事务，缺来源AttributeError/属性异常原传播，不mock成功SQL。完整unit执行；原验证新建唯一临时库迁移head，Audit失败User无残留、两并发仅一个Admin/一次Audit、真实scrypt验证；准确保持原证据范围，不将单表count当九表回滚。临时库自行清理，无正式账户或密码供给。

风险/回滚：只测试可撤，无升级，原验证fixture唯一库删除仅自己创建的资源；完整Auth coverage/性能/wheel另项。下一完整unit+19链覆盖（加入成员名称与初始管理员实际链），Gate/正式trust/包待。

结果：新增3参数化方法，1551unit/contract21.690秒失败0/错误0/既有跳过2、exit0；claim/create错误与真实inactive来源拒绝/不启动事务，缺来源AttributeError及属性RuntimeError原传播。原实际临时PG初始化通过：审计失败User count为0、并发仅一Admin/一AUTH_INITIAL_ADMIN_CREATED事件、真实scrypt验证通过；资源finally清理。没有正式账户创建，生产未变；完整coverage/性能/wheel未跑，下一A40完整19链覆盖，Gate/包待。
