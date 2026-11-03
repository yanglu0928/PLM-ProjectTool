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


## 首段云端验收与复核

- 首段实现提交 f116604885d942fb9f2fa7d3d471d03c9652c9f9；run [41597429890](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41597429890) 全13/13 jobs成功。后端测试/wheel、前端、PG smoke、父包组装、A35/A17/A34通过。
- 复核发现Application直接导入Document基础设施，属于需先登记再修正的模块依赖偏差。CR-PLG-006已记录。此首段不对外装配；A08仍进行中。


## Protocol修正与结果归档恢复

- 已按CR-PLG-006将Application的Document基础设施直接依赖改为Plugin-owned staging storage Protocol。
- 本次提交同时恢复PLG-01-A07结果文档与CR-PLG-005关闭记录，避免早前Git Tree更新遗漏这些新增路径。
- A08修正后hosted验证尚未完成。


## Protocol修正云端验收

- 修正提交 8baaaf827bf6b7bbc1cf4b47e8a5606712e4b02e；run [41599893419](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41599893419) 全13/13 jobs成功。
- Plugin Application跨模块具体依赖已移除；本次仅验证暂存原语及全链路回归，A08导入API/Job/Worker仍未完成。
- 此提交同时恢复A07结果文档和CR-PLG-005的最终PASS_SCOPE_LIMITED关闭证据。
