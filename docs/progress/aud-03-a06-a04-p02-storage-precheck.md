# AUD-03-A06-A04-P02 文件归属前置核查

日期：2026-09-26；Phase 2；结论：核查完成，直接复用当前发布入口 BLOCKED。本项不修改冻结模型或生产代码。

## 输入、前置与权限

A04-P01 固定成员安全 JSONL/manifest 已通过；冻结 DM-03 FileObject、DM-04 OutputArtifact、API-02 AUDIT_EXPORT，0039 当前实现。涉及 Audit/Document/Jobs，不新增实体、Schema、API、依赖或权限。验收为实际入口兼容探测与持久归属/发布依赖核查，不以静态检查冒充落盘、数据库或跨平台验收。

## 证据

- `document/infrastructure/orm.py`：FileObject Scope CHECK 只允许 GLOBAL+NULL 或 PROJECT+非空项目。Document/DocumentVersion 同样只支持两范围；GENERATED_ARTIFACT 限 PROJECT。
- `document/infrastructure/local_storage.py`：`locators` 与 locator 正则只支持 global/projects 及对应 temp；实际 DEPLOYMENT 调用拒绝。只改调用参数不能解决物理存储边界。
- `document/application/publish_file.py`：`PublishFile` 实际校验拒绝 DEPLOYMENT；该 Service 自建两段 UOW并完成独立 receipt/Audit，不适合作为 Audit 与 Jobs 完成同一 caller-UOW 内的原子发布回调。
- 冻结 DM-04 OutputArtifact 属 PROJECT，AVAILABLE 要求完整 OutputRequest、PluginExecution、DocumentVersion 与 FileObject。审计导出是内部安全投影，不是插件输出，部署导出也不属项目；不能伪造这些来源来通过约束。当前生产模块无 OutputArtifact 实现，缺少它不能当默认许可。
- `jobs/application/lease.py` finish 在 caller publish 回调内提交数据库；文件提升属于事务外不可回滚操作，不能让文件写入成功等同 Job/结果可下载。

## 方案比较与后续

1. 将 DEPLOYMENT 改标 GLOBAL 或创建虚构 Project/Document/Plugin：拒绝，破坏 Scope 与来源。
2. 一并扩大 Document/Output 全链路：影响面过大，不作为最小修复。
3. 建议 FileObject 增量支持内部 DEPLOYMENT 存储归属，Document/Upload/Parse 继续原范围；Audit 自有不可变 export-result 与固定 FileObject Ref/manifest 摘要，通过 Document owned 公共 caller-UOW Port 登记和读取文件状态，不跨模块写表。不复用业务 OutputArtifact 或伪造 DocumentVersion。该建议涉及冻结归属/结果契约，必须先单独 CR、完整影响/迁移/回滚/安全与验证计划后才能编码，当前尚未实施。

后续要求：受控且 generation 隔离临时文件、bounded 写入/flush/fsync/hash 读回；文件不覆盖旧结果；当前权限/原 acceptance/pair/capture/Lease/取消状态重核；短事务内唯一结果+文件状态+Job终态+Audit 全有或全无。取消/撤权/旧 Worker/数据库失败后的已提升文件仍不可见，恢复按持久根和实际文件证明，不按路径猜成功；实际下载再授权，绝对路径/Locator 不出 HTTP。

本核查未证明目标账户 ACL/停写/恢复、磁盘不足、128MiB性能或 Server2025/Debian 行为。正式信任来源与 Gate3 阻塞仍保留。下一任务 P03：记录专项 CR 与实现前契约，随后空/有数据 Schema 与真实文件恢复验证；导出 POST 仍关闭。

## 验证结果

Windows11/Python3.13执行 `validation/aud-03-a06-a04-p02-storage-precheck/verify.py`，4项PASS；直接调用真实locators和发布校验，不替代其实现。没有文件或数据库写入，不涉及Migration/API/生产代码，未重跑后端全集；P01已有880项/2环境跳过结果保持历史证据而非本项新执行结果。
