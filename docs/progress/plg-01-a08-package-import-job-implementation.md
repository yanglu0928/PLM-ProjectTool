# PLG-01-A08：流式暂存实现进度

- 状态：IMPLEMENTATION_IN_PROGRESS
- 日期：2026-11-03
- 变更：CR-PLG-006
- 当前阶段：第一段内部能力已编码；尚未接入HTTP、幂等Job/Outbox、Audit或显式安全组合。

## 已实现

- 新增 PluginPackageImportSpool，复用 Document 私有 LocalFileStorage 的opaque GLOBAL staging locator。
- 按不超过1MiB块读取，校验申报长度、SHA-256和最大包上限（不超过 Inspector 的256MiB）；fsync后验证文件身份/链接数并重读内容Hash。
- 写入失败时只尝试按本轮inode删除；删除失败保留孤儿给后续受控恢复，不按路径盲删。
- staging locator 与摘要字段从对象repr隐藏；无路径返回给HTTP。
- 增加合成单元验证覆盖正常暂存、超长、长度/摘要错误、非法chunk和失败清理。

## 尚未实现

HTTP Session/License/CSRF/DeploymentAdmin route；Idempotency回放/冲突；staging metadata owner；Job/Outbox/Audit原子入队；worker安全执行。A08未完成，不能以此代码单独标PASS。
