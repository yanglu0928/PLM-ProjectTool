# P07-A04-P03 历史重放Port违约验收

2026-09-27；0.1.0.dev0；Windows11/Python3.13.15；生产939cff0/0049不改，补充两个history unit fixtures。

新增4个参数化方法：reset prepare first未知对象/错target/actor/原User版本（4类）；reset history write missing/未知reserve、其他合法op/status201、first ID/trace改变、final actor None（7类）；change prepare first未知或错User（2类）；change history write missing/未知reserve、其他合法op/status201、first ID/trace/user改变、final actor None（8类）。操作字符串均符合真实V1 DTO校验，再由Service判错配，避免在构造阶段提前停下。

准备错误：verify/reserve/repo/commit均未调用，准备UOW闭合且密码擦除。写历史错误：reset1/change2次密码source verify确实执行过，随后2个UOW关闭、repo与receipts.complete/tx.commit未调用，密码擦除。正常history控制沿原已有测试保持first与无新hash/写，真实PG数据完整性根据P02实际测试保留；本批Port错误/commit Spy不是实际SQL提交/回滚证据。

完整unit/contract实际1456 tests，failures0/errors0/skipped2（既有符号链接账户权限场景），exit0。无生产源码/Migration/API/权限/算法/依赖改变或升级；本轮没有coverage/四PG/wheel重跑，不推算新覆盖率，最近P02密码82.432%分支/全Auth74.743%继续保留。原runtime/JSON/Hash、冻结历史及当前门槛不改。

下一P07-A05适配器非法输入/当前数据错配/安全错误与无SQL写边界，再统一真实PG覆盖复验。安全完整/90%分支/正式trust/目标账户/三平台/安装升级/UAT/Gate3和可用包未完成；性能CR008仍FAIL/默认4，不能用局部测试通过替代交付。
