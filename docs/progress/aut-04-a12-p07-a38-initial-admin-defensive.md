# P07-A38 初始管理员内部防御

2026-09-27编码前检查：Phase2/AUT-04-A12-P07-A38；输入冻结64cdf09/0049、当前InitialAdminService。仅本地一次性Service依赖/命令/UTF8字符长度/claim非True/Hash来源/底层故障与密码擦除合同，不创建正式账户或供给正式口令。

验收：UTF8字节达15但字符不足15拒绝，非法命令擦除可变密码、前UOW拒绝；四依赖None拒绝；claim必须exact True；错误Hash形状和哈希故障固定SYSTEM_UNAVAILABLE；Repository/Audit/commit底层RuntimeError保持原传播，不误称Service统一错误转换。进入UOW后异常退出/不提交，密码清零。Mock仅Port，不模拟成功SQL/生产trust。完整unit实跑，实际初始管理员临时PG来源另项；完整coverage/性能/wheel不跑。只测试可撤，无生产/API/权限/Schema/依赖变，无升级，Gate/包待。

结果：新增7参数化方法，1548unit/contract21.805秒失败0/错误0/既有跳过2、exit0。依赖/claim非True/UTF8字符不足/非法命令/六坏Hash/Hasher异常/四底层故障均拒绝，密码擦除和已进入UOW退出，不提交；Hash故障固定码、Memoryview已release。仅Port证据，原RuntimeError传播不假称统一Service错误。无正式账户创建、无生产变更，完整coverage/性能/wheel未跑。下一A39数据库适配层inactive来源与原临时PG初始化验证，Gate/包待。
