# HND-05-A02-P04：交接问题卡片版本 Windows 11 非发行包验收

日期：2026-10-25；状态：`SYNTHETIC_PACKAGED_EDGE_PG_PASS / PILOT_NOT_READY`。

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

候选从已同步干净提交 `89bb84d7a6bb028bfe664d54144b34e85b3042ad` 重建，SHA-256
`3e84a42c3c22fd5f02ec5a13a35bc86d28394f9d1cf9b846952bdfa8cf2cb209`，路径
`artifacts/package-prep/windows11/current-app-hnd-a02-p04-20261025/current-app-candidate-297bc4b22eb4/NOT-FOR-RELEASE-windows11-current-app.zip`
仅留本机忽略区。清洁解包逐件校验 22,196 个 payload 文件，状态
`NON_RELEASE_CURRENT_APP_CLEAN_EXTRACT_PASS`；`release_eligible=false`、`legal_clearance=false`。

首次整链退出 1：Workflow、项目固定文档/交接分析、PROJECT Evidence 均通过；验收夹具随后重跑
已经执行过的 GLOBAL 文档创建前置，使旧断言 `DOCUMENT_UPLOAD_CREATE=1` 实际为 2。
未到本轮交接版本页面，不记 P04 通过。夹具改为跳过已完成的 GLOBAL 文档/Capability
前置，仍实际运行 GLOBAL Evidence 与批准链。第二轮整链再次退出 1：既有前置通过，
但跳过旧前置时遗漏其合成部署管理员角色设置，GLOBAL Evidence 页面按权限正确拒绝。
在一次性隔离库补回该角色设置；没有放宽产品权限或改动候选 ZIP。第三轮从同一固定
候选重跑，既有项目链通过，GLOBAL Evidence 已获权限但找不到固定来源：跳过旧复合前置
时也跳过了其创建的首份 GLOBAL 固定文档。再次仅调整夹具：显式运行原 Edge 文档上传/
基线创建脚本，再执行 GLOBAL Evidence、双来源能力批准和本轮交接版本；旧复合脚本中
要求所有文档上传 Audit 总数恰好为 1 的断言不适用于此处已有项目文档的组合。
第三轮亦未到交接版本写入，不记 P04 通过。

第四轮同一 SHA 固定候选完整退出 0：Windows 11 非发行包装 Caddy/后端、一次性
PostgreSQL 18 与合成 License/公钥上，既有项目固定文档→交接分析→PROJECT Evidence
`ELIGIBLE`、GLOBAL 固定文档→GLOBAL Evidence→双来源能力版本及两名 Reviewer 批准
的前置链全部通过。新 Edge 页面显式重选同一固定项目文档版本、引用当前已批准能力与
同项目合格证据、定位原文，保存两张有来源的 DRAFT 问题卡片（其中一张 `NEED_CONFIRM`
含人工填写提示与 A/B 选项）；原正文/原 Key/原 ETag 重放仍返回 201。

隔离 PG 核对只生成 1 个版本、2 条 `CANDIDATE` 卡片，来源/证据/能力引用、人工输入
字段及两个选项完整，分析锁版本变为 1 而批准指针仍为空；`HND_VERSION_CREATED`
Audit 和 `V1_HND_VERSION_CREATE` 完成回执各 1。匿名、未分配项目用户和错误固定来源
写入均被拒绝，最终版本数仍为 1。清洁解包 22,196 payload，固定候选未变，临时布局/
进程/文件清理、合成 Vault 目标事前不存在和不留持久测试信任均由脚本返回 PASS。

本结果只关闭 Windows 11 合成信任下的交接 DRAFT 创建切片；卡片仍是候选，不能称客户
确认、Review 批准或业务正式事实。未完成的完整纵向链、正式公钥/服务账户装配、法律
放行、真实离线安装/升级、自然到期与撤销负例、UAT/Gate 3～7、Windows Server 2025/
Debian 13 正式实测保持未通过，Pilot/Release 仍 `NOT_READY`。Next：`HND-05-A03-P01`
核查版本校验/送审用户入口与现有冻结合同，单独处理后续评审链。
