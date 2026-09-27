# P07-A38 初始管理员Service结果

2026-09-27 Windows11/Python3.13.15。完整1548unit/contract21.805秒，失败0/错误0/既有跳过2、exit0。新增7参数化方法覆盖四依赖、四claim非exact True、UTF8字节达15但字符不足15、六非法命令、六错误Hash形状、Hasher异常、四Repository/Audit/commit故障。

非法输入在事务前拒绝，Hash错误固定SYSTEM_UNAVAILABLE，底层RuntimeError保持原传播；密码清零、故障Hash memoryview已release、已入UOW退出、不提交通过。只Port合同，不模拟成功SQL，不冒充真实数据库回滚或生产信任锚。测试辅助Transaction新增closed观察字段，不改生产行为。

没有创建正式管理员或代供给正式口令。无生产/Migration/API/权限/依赖变，无升级，可撤新增测试。完整Auth coverage/实际链、性能、wheel未运行，不推算新百分比，原raw/90%保留。完整安全/CR008性能FAIL/正式trust/Gate/可用包待。追溯DEC-20260927-386及同名progress，下一初始管理员DB适配来源与原临时PG初始化验证。
