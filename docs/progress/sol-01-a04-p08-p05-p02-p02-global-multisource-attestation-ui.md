# SOL-01-A04-P08-P05-P02-P02：GLOBAL 多来源集合人工核查前端

日期：2026-10-09；结果：`MULTISOURCE_ATTESTATION_UI_CONTRACT_PASS`，限前端合成合同；真实 Windows 11 Edge/隔离 PG 多来源链和真人业务判断未验。

编码前检查：Phase 2；前置 P05-P02-P01 有序候选选择/固定身份读取通过，CR-SOL-009/010 的 Preview/Confirm/Revoke/原 Key 回查已在单来源链验证。输入为冻结 API-04、现有多来源 Owner 与前端严格客户端；只修改 Solution 前端页面/测试，不动后端、Schema、公开 API 或权限。验收为集合前复核、响应身份/顺序绑定、逐文档/逐证据打开和勾选、显式本人声明、变化清空、未知结果锁定和同 Key 回查。

实现：至少两条 GLOBAL Evidence 才构造请求；DocumentVersion 按候选顺序首见去重。Preview 前逐条重新读取 Viewer/当前资格，身份、固定原文 URL 与 ELIGIBLE 必须一致；服务端返回的 Document 根/版本及 Evidence 顺序必须与本次集合完全相同。只有 Preview 成功后，才显示每个固定文档版本与每条证据的原文链接；各自打开后各自可勾选，全部完成并单独勾选本人声明后允许 Confirm。分类/行业或候选变化立即清空 Preview/勾选，服务端漂移 409 亦清空。Confirm/Revoke 不确定时保存当前管理员原操作号并禁止新写；只有同 actor/操作种类的服务端 `COMPLETED` 收据且展示当前状态、本人再勾选核对后解除本地锁；`UNCONFIRMED` 保持锁定。成功确认不创建 GLOBAL Reference，撤回保留历史。

验证：定向 7 项（包括集合顺序、文档去重、预览响应错配、逐项打开前不得提交、分类漂移清空、未知结果原 Key 回查及非管理员拒绝）；前端全量 `106 files / 1632 tests`、typecheck/build 通过。此为模拟客户端合同，脚本勾选不构成真实管理员资料脱敏确认。后端生产代码未变，前序全量 `3337 passed / 3 skipped / 4930 subtests` 不作为本项重新执行证据。

兼容/升级/回滚：原只读候选页兼容增量加入 Preview/Confirm/Revoke 操作，均复用既有 API/私有 CSRF；无 Schema、依赖或数据迁移。可关闭该页面入口回滚，但已提交的确认/Audit/收据不得删除。风险为跨页候选变化、文件/资格变化和超时不确定；前端失效清空/原 Key 锁定与服务端写时来源指纹重验同时保持。P05-P03 必须再用两个不同固定 DocumentVersion 的真实 Edge/PG 合成链检验；正式 License/目标账户、Server 2025、20 并发、Gate 3/UAT/发行及真人业务确认未验；Debian 13 按用户指令跳过。

TraceLink：CR-SOL-009/010 → P04-P03 单来源 Edge → P05-P01 → P05-P02-P01 → 本 P05-P02-P02 → P05-P03。
