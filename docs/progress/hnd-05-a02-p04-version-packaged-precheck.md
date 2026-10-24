# HND-05-A02-P04：交接问题卡片版本 Windows 11 非发行包验收

日期：2026-10-25；状态：`PRECHECK_PASS / VALIDATION_PENDING / PILOT_NOT_READY`。

|编码前检查|结论|
|---|---|
|Phase/WBS|Phase 2 / `HND-05-A02-P04`；仅验证 P03 页面在固定包内创建有来源的 DRAFT 版本，不变更 API/Schema/权限。|
|输入基线|CR-EXEC-002、HND-05-A02-P01～P03；干净已同步提交 `9d73c4a5`；父 ZIP SHA `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98`；pgvector wheel SHA `fedc9800894e6da2be51358d7b7c574bf34f247ca741a5a09513622135f5964f`；复用未变后端 wheel SHA `ecbed9b6118c01a6617a1bc68ebfb1fa50ef5dc984951eaf0f162d8817e4e6ef`。|
|前置|P03 定向5、前端全量1974/typecheck/build PASS；包内前置已有合成项目固定文档/交接分析、GLOBAL Capability APPROVED 和 PROJECT Evidence ELIGIBLE 的独立证据；新页面必须进入新候选，旧 ZIP 不代表本轮。|
|模块/实体/API|HandoverAnalysis/Version/Item、DocumentVersion、CapabilityBaselineVersion、Evidence、Audit/幂等收据；既有冻结 `/api/v1`。|
|权限|Windows 11 一次性合成 ProjectManager/ImplementationMember/CustomerManager、部署 Admin、License/TLS；创建版本服务端复验同项目、能力当前批准和证据资格；真实客户确认另行验收。|
|验收|固定父包/轮子重算 SHA；新候选全件哈希/清洁解包；Edge 在打包页面完成固定来源重选、能力与证据选择、两张问题卡片（含 NEED_CONFIRM 提示）并收到 DRAFT；PG 验版本/条目/引用/Audit/回执、同 Key 重放和匿名/无项目权限/错误来源拒绝；临时进程/布局/隔离库清理。|
|风险|非发行合成信任，不等于人工客户批准、正式 License 公钥/服务账户/法律放行、离线安装升级、三平台发行或 Gate 3～7；大 ZIP 留本机 Git 忽略区。|

前置已满足。结果只按实际命令退出、浏览器网络响应与数据库记录填写，不预填 PASS。
