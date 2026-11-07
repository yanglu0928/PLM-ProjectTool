# PLG-04-A01 编码前检查与验收范围

- 日期：2026-11-06；Change Request：CR-PLG-015
- 结论：PASS_WITH_LIMITATION，可开始编码
- 执行：源码只读审计；代码和测试仅由GitHub hosted Windows runner D盘或云端沙箱执行

## 单一问题与核查

Package Import Worker在staging摘要复核及Registration后直接完成Job，ZIP正文只在内存中验证。Registration返回不可变PackageIdentity，含PackageId、签名/key ref、包摘要、版本和Manifest快照，精确重放可幂等返回。LocalFileStorage已提供私有data_root、严格locator/reparse/hardlink检查、同卷无覆盖提升、前后Hash/size复验及精确staging清理，可复用而无需DB表。正式publisher signer列表为空，生产信任仍失败关闭。

## 决策与边界

使用固定UUID locator `plugins/packages/{uuid-prefix}/{package_uuid}`。原始ZIP先写同卷staging并重验SHA-256、长度，再无覆盖提升；同ID精确字节重放幂等，错摘要/链接/越界失败关闭。Worker顺序为staging验证→登记/幂等重放→存储包→完成Job，持久化错误沿既有有限重试，避免跨PostgreSQL/文件系统事务的虚假原子性。只读适配器重跑签名、ZIP和Manifest检查并对比登记快照，只返回元数据，不表示安装、不暴露路径/正文。

无Schema/Migration/API/默认组合变更；不解压、安装依赖、运行插件、客户数据、生产写入或真实trust增加。验收覆盖Storage幂等/哈希/篡改、Worker失败顺序、后端全量/wheel与父包PG18 smoke。
