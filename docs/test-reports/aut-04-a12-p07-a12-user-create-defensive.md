# P07-A12 创建Service防御测试

2026-09-27；Windows11/Python3.13.15；完整unittest discover 1486项，failures0/errors0/skipped2，exit0。新增6参数化方法，不改变已有通过用例。

|拒绝对象|案例数|边界|
|---|---|---|
|必需依赖None|9|构造拒绝，无UOW|
|收据type/operation/status|3|无get/replay/hash/User/complete|
|原结果缺失/display/ref-user/proof返回错配|4|无写/complete/commit|
|User/Credential/activation/Audit/first四来源坐标|8|无complete/commit|
|非法clock|4|无授权读取/reserve/hash|
|hash类型/算法/hash/参数类型数量/键/成本|12|无User/Audit/complete|

已进入UOW均退出，错误路径持有bytearray全部清零。Mock为Service Port合同控制，不代表实际SQL成功/回滚。生产/API/Schema/权限/算法/依赖无变化；coverage/12PG/wheel/性能本批未运行，最近A11完整Auth82.186%分支及raw SHA a2fb0a38…保留，不推算提升。原性能CR008 FAIL/正式trust/Gate3/程序包未完成。下一Result Repository前SQL与实际来源独立验证。
