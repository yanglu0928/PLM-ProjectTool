# PLG-02-A08：PLUGIN_DISABLE受控HTTP入口编码前检查

- 日期：2026-11-04
- 状态：`PASS_WITH_LIMITATION`（边界明确；等待CR登记后编码与hosted验收）
- WBS：PLG-02-A08
- 变更记录：`docs/changes/CR-PLG-013-plugin-installation-disable-api.md`
- 前置：PLG-02-A01～A07均已按有界范围完成；A07 hosted全量run 41759878694为13/13。

## 编码前检查

### 冻结基线

API Contract V1定义：

- `PLUGIN_DISABLE`: POST `/api/v1/admin/plugins/installations/{installation_id}:disable`
- DeploymentAdmin；控制为S/L/C/I/M/A，即有效Session、License、CSRF、Idempotency-Key、If-Match与Audit。
- 状态改变使用强ETag版本；缺少If-Match返回428，版本不匹配409；同一actor/operation/key + 同请求应返回原结果，同Key异请求409。
- 只返回安全的DISABLED结果；不得泄露包内容、签名、绝对路径、运行环境Secret、进程/stdio或堆栈。

### 当前源码

PLG-02-A06已有 `PluginActivationOwner.disable`，能使用expected lock version原子撤销全部enabled operations，写不可变操作History与Audit，更新DISABLED和Installation lock version；精确DISABLED重放不重复写历史。A07已有只读详情GET和强ETag，在安全显式读组合中可供管理员读取当前版本。

仍缺：CSRF/If-Match/Idempotency HTTP边界、production真实部署管理员写权限核验、错误响应映射、显式写组合装配和首次响应精确重放。目前Owner命令没有可持久化首次HTTP结果的结果行；直接在第二次调用Owner将因旧If-Match冲突，不能实现API合同幂等。

### 本项决定与变更边界

按CR-PLG-013新增一个最小不可变停用结果表/migration 0230，用既有IdempotencyReceipt引用该结果。插件状态变更、逐操作Audit/History、结果快照与Receipt需同事务提交；同键同载荷重放读取结果快照，不再调用Owner；同key异载荷409。扩展或组合受控服务时保持身份/CSRF/License先行、提交前资源与If-Match检查；写Router仅挂载显式Production Platform Write，不挂Read/Login/default/Trace-only组合。

只处理单条Installation停用API，不扩展启用/退役API、列表分页、实际物理卸载、宿主安装器或插件执行。无客户数据外发、无真实系统安装和不可逆操作。

### 验收与回滚

GitHub hosted D盘临时目录完成后端全量/wheel、前端/build、空库/有数据迁移验证、PG18真实SQL和HTTP合成身份、停用/审计/错误/幂等重放/同键异载荷/CSRF/If-Match失败/事务回滚，默认入口及只读组合404，以及父包A17/A34/A35/A50链。Schema downgrade仅在没有A08结果记录时允许；存在结果行时拒绝删除结果表。代码组合可撤除，正式结果历史保留。不得以Hosted PASS声称Win11实机、正式信任、Pilot/Gate/Release通过。

- 计划状态：已登记CR-PLG-013，用户长期自主执行授权适用，无需普通开发逐项确认。
