# P07-A36 成员名称来源防御合同

2026-09-27编码前检查：Phase2/AUT-04-A12-P07-A36；输入冻结64cdf09/0049与现有project_member_names。代码检查修正原任务假设：适配层只在上层Project授权后做最小名称投影，未承诺非法user_ids前SQL验证，不加新权限或静默过滤。仅错误/缺事务来源、真实inactive与active空tuple合同测试。

验收：错误Session/真实inactive抛原RuntimeError且不启动事务，缺session原AttributeError；真实active无bind Session空tuple返回{}且仍在原事务（若执行SQL将无法绑定），退出事务闭合。禁止mock成功SQL；非法编号的实际SQL/缺行/名称映射另A37明确验证，不冒充前SQL校验。完整unit实跑，17链coverage/性能/wheel不跑；只测试可撤，无生产/API/权限/Schema/依赖变，无升级，Gate/包待。

结果：新增3参数化方法，完整1541unit/contract21.763秒失败0/错误0/既有跳过2、exit0。错误来源与真实inactive分别空/非空均拒绝，缺来源原AttributeError保持；真实active无bind空tuple返回{}且退出闭合，无成功SQL模拟。无生产变化，17链coverage/性能/wheel未跑。下一A37真实名称映射/缺行/非法编号SQL行为，保持授权上层，不称投影适配层权限通过；Gate/包待。
