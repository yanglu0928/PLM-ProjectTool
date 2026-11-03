# CR-PLG-006：签名插件包流式导入与异步验证Job接入

- 日期：2026-11-03
- 状态：APPROVED_BY_CONTINUOUS_USER_AUTHORIZATION / IMPLEMENTATION_IN_PROGRESS
- 适用WBS：PLG-01-A08
- 分支：feature/p51-a33-launcher-checksum-recovery
- 依据：冻结API-03 PLUGIN_PACKAGE_IMPORT、DM-04 Job/Plugin、ADR-005/007、CR-PLG-001～005、用户持续自主执行授权

## 触发与差异

A07完成了元数据登记Owner，但冻结API的 POST /api/v1/admin/plugins/packages:import 尚无生产路由、流式字节持久暂存和验证Job enqueue。A06 Inspector接收内存bytes，HTTP不能将包整体载入内存再异步返回。A08在不改冻结API语义下接通受控导入请求与可恢复验证Job。

## 方案比较

1. 一次性把HTTP正文完整读入RAM，再登记Job：实现简易，但达到A06上限256MiB时形成较高内存峰值，进程崩溃会丢失已响应工作。
2. 先持久暂存至私有本地文件，再在同一数据库事务写入PackageImport staging metadata、Job、Outbox和Audit；数据库提交失败时按inode/摘要删除本轮文件，崩溃残留由受限扫描识别。Job载荷只存opaque上传ID/摘要，不存字节/路径/签名正文。选择方案2。

## 实施边界

- 实现冻结DeploymentAdmin Session/License/CSRF/Idempotency/Audit控制；流式读取request body，严格限制总大小为MAX_PACKAGE_BYTES，拒绝Content-Length与实际长度不符及重复/畸形关键Header。
- 使用项目私有数据根下同卷、拒重写、拒绝reparse的staging文件；不写C盘Temp。目录位置只从配置好的程序数据根读取。
- staged文件发布后，在一个UOW内建立有界GLOBAL verification Job、Outbox及Audit；相同幂等键+相同正文摘要返回首次JobRef，不同摘要冲突。Job payload仅含opaque package upload reference及SHA-256，不含路径、签名、包正文。
- 数据库失败时仅清理本调用创建且文件身份/Hash仍匹配的暂存文件；进程崩溃可能遗留孤儿。未登记或状态不确定的文件不得盲删。
- Worker异步验证是否可归本WBS，编码前检查需确认单一范围并检视已有Worker。不得安装、解压至插件目录或启用插件；生产trust为空时必须失败关闭。
- 只使用GitHub hosted Windows runner D盘临时根及合成包/测试key；不用用户本机/C盘、客户包或外部AI。

## 风险、迁移/回滚与验证

- 风险：HTTP/文件系统/DB提交非原子、停机遗留文件、超大/慢速正文、幂等键误复用、worker重复投递、path traversal/reparse/hardlink及日志泄露。
- 控制：opaque UUID locator、限制长度与逐块摘要、授权前置、transactional outbox、稳定安全错误码、按精确文件身份和Hash补偿。恢复扫描仅处理可明确证明为孤儿的文件。
- 若新增schema，仅含opaque upload ID、digest、size、state和时间等必要元数据；采用新增migration并验证空库/含数据up/down。冻结Package字段不变。
- 回滚：停用route和producer；保留Audit/Job/登记文件历史。只有未被DB引用且身份/摘要匹配的本次暂存文件可补偿删除；含历史记录时只关闭写入，不删除。
- 验收：冻结HTTP/header/错误合同；权限/License/CSRF/Audit、边界大小与摘要、畸形/缺失/重复头、幂等/冲突、DB失败补偿、孤儿安全、Outbox at-least-once与Job载荷最小化；PG18集成、全后端/wheel/前端及父包云端验收。仅合成数据，不代表Win11实机、正式trust、插件执行、Gate/Pilot/Release。

## 实施前观察

仓库已有Document bounded streaming、ValidatedContentSpool、LocalFileStorage opaque locator以及Jobs transactional enqueue/Outbox模式；Plugin模块尚无import Router、staging schema或worker。编码时先复核上述共享原语边界，尽量复用而不复制宽泛文件系统代码。A08编码前检查见 docs/progress/plg-01-a08-package-import-job-precheck.md。

## 验证记录

尚未开始；后续偏差须在实施前回写本CR并同步STATUS/CHANGELOG。
