# P07-A28 评审启动Auth防御结果

2026-09-27 Windows11/Python3.13.15。新增3参数化方法验证14个token/CSRF输入、5个时间输入、5个事务来源；完整1528unit/contract21.638秒，失败0/错误0/既有跳过2、exit0。

非法输入返回None，在读取tx.session前拒绝；无时区与utcoffset为None时间拒绝。合法输入遇None/缺Session/错误对象/真实SQLAlchemy未激活Session抛原固定RuntimeError，不启动事务。不mock成功SQL，本轮不代表真实Session/CSRF数据库读取验收。

生产/Migration/API/权限/依赖未变，无升级，回滚仅撤新增测试。coverage/15实际链、性能、wheel未运行，完整Auth不推算，旧raw/90%保持。完整安全/CR008性能FAIL/正式trust/Gate/可用包待。追溯DEC-20260927-376及同名progress，下一A29真实数据库来源及拒绝边界。
