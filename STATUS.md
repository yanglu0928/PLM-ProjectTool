# 项目状态

|字段|当前值|
|---|---|
|Current Phase|Phase 2：Platform Core|
|Current WBS|`PLT-MAINT-01-A03-P03-P01` PostgreSQL18 排他转换事务内 Admin 认证 PASS；OS 受控入口/生产 API/双 Worker 尚未接线，P05 正式账户、跨 Job retry 与 P08-A02 浏览器文件验收仍 INCOMPLETE|
|Current Status|PHASE_1_COMPLETE / DOC_03_A03_P04_P04_PRECONDITION_BLOCKED / DOC_02_A02_P01_INTERNAL_PASS / DOC_02_A02_P02_PRECONDITION_BLOCKED / DOC_03_A04_A03_P04_P03_CONTENT_HTTP_PASS / DOC_03_A04_A04_P01_JOB_SCHEMA_PASS / DOC_03_A04_A04_P02_JOB_LEASE_PASS / DOC_03_A04_A04_P03_OUTBOX_PASS / DOC_03_A04_A04_P04_P01_PARSE_QUEUE_PASS / DOC_03_A04_A04_P04_P02_COMMIT_INTERNAL_PASS / DOC_03_A04_A04_P04_P03_P01_ABORT_STATE_PASS / DOC_03_A04_A04_P04_P03_P02_PRECONDITION_BLOCKED / DOC_03_A04_A04_P04_P04_A01_FINALIZE_HTTP_PASS / DOC_03_A04_A04_P04_P04_A02_WINDOWS_COMPOSITION_PASS / DOC_03_A04_A04_P04_COMMIT_ABORT_IN_PROGRESS / DOC_01_A02_INTERNAL_PASS / DOC_01_A03_P01_CURSOR_PASS / DOC_01_A03_P02_HTTP_CONTRACT_PASS / DOC_01_A03_P03_HTTP_DB_PASS / DOC_01_A03_P04_WINDOWS_COMPOSITION_PASS / DOC_01_A04_P01_VERSION_INTERNAL_PASS / DOC_01_A04_P02_VERSION_CURSOR_PASS / DOC_01_A04_P03_VERSION_HTTP_CONTRACT_PASS / DOC_01_A04_P04_VERSION_HTTP_DB_PASS / DOC_01_A04_P05_WINDOWS_COMPOSITION_PASS / DOC_01_A05_P01_VERIFIED_SNAPSHOT_PASS / DOC_01_A05_P02_DOWNLOAD_SOURCE_PASS / DOC_01_A05_P03_PREPARE_DOWNLOAD_PASS / DOC_01_A05_P04_DOWNLOAD_HTTP_PASS / DOC_01_A05_P05_WINDOWS_COMPOSITION_PASS / DOC_01_A05_P06_DISCONNECT_CAPACITY_BOUNDED_PASS / DOC_03_A04_A04_P04_P03_P02_A01_GATE_ADAPTER_PASS / DOC_03_A04_A04_P04_P03_P02_A02_P01_CONTENT_GATE_PASS / DOC_03_A04_A04_P04_P03_P02_A02_P02_COMMIT_GATE_PASS / DOC_03_A04_A04_P04_P03_P02_A02_P03_ABORT_GATE_PASS / DOC_03_A04_A04_P04_P03_P02_A03_P01_READONLY_INSPECTION_PASS / DOC_03_A04_A04_P04_P03_P02_A03_P02_A01_STORAGE_STEP_PASS / DOC_03_A04_A04_P04_P03_P02_A03_P02_A02_INTERNAL_CLEANUP_PASS / PLT_02_A07_P05_A09_CEREMONY_PENDING / PHASE_2_IN_PROGRESS|
|Completed Phases|Phase 0 技术验证（`COMPLETE_WITH_APPROVED_ALTERNATIVES`）；Architecture / Data Model / DB Schema / API Contract Freeze；Gate 2 `APPROVED`；Phase 1 基础工程|
|Completed WBS|POC-01、POC-02、POC-04、POC-05、POC-06、POC-08、POC-09 已按验证或批准例外收口；POC-03 以批准替代方案收口；Gate 1 已通过；AF-01～AF-05、DM-01～DM-06、SC-01～SC-05、API-01～API-05 PASS；Gate 2 已批准并冻结四份基线；1.01～1.09、PLT-01-A01～A03、PLT-02-A01～A06、API-RUNTIME-01（仅 Win11）、PRJ-03-A01～A04、AUD-01-A01～A03、AUT-01-A01～A03、AUT-02-A01～A05、AUT-03-A01～A06、AUT-03-A07-P01～P03（P02/P03 仅 Win11）、AUT-03-A08～A10（仅 Win11）、PRJ-01-A01～A06、PRJ-02-A01～A04、LIC-01-A01～A04、LIC-02-A01～A05、LIC-03-A01～A03、DOC-03-A01、DOC-03-A02（限定范围）、DOC-03-A03-P01～P03（P03 内部合成验证）、DOC-03-A03-P04-P01～P03（内部合成验证）、DOC-03-A04-A01（Schema 验证）、DOC-03-A04-A02（内部合成验证）、DOC-01-A01、DOC-02-A01、DOC-02-A02-P01（内部合成验证） PASS|
|Blockers|DOC-03-A04-A04-P04-P03-P02 内部清理/崩溃对账已在隔离库/临时文件验证；A03-P03 证实 Server 2025 VM 可启动但远程管理/桌面端口未连通，正式旧版进程停写、目标账户 ACL 与恢复演练未完成，生产物理删除入口仍关闭；AUT-03-A07 Windows 11 合成端到端已通过，Server 2025 目标运行账户/HTTPS 代理与 Debian 安全凭据来源未验证；PLT-02-A07 显式生产写组合已合成验证，正式发行公钥、目标账户可信时间/游标/Secret 主密钥供给、Server 2025 恢复演练仍待；POC-03 质量失败继续阻塞 Gate 3/UAT，Server Office、Debian 未验证和 Ghostscript 发行合规继续作为 Release 约束|
|Pending User Decisions|LIC-03-A03 方案 A 已确定；P08-A02 本机浏览器将两份纯合成 PDF 上传至 127.0.0.1 隔离服务的 UI 文件操作确认待回复（非项目技术方案选择）。客户数据外发、付款/额度重置和不可恢复生产操作不在持续授权内|
|Architecture Version|`ARCH-CANDIDATE-V1`；Gate 2 原冻结内容 `64cdf09`，License ADR-006 经用户批准 CR-LIC-001 修订|
|Data Model Version|`DATA-MODEL-CANDIDATE-V1`；Gate 2 原冻结内容 `64cdf09`，DM-02 License 授权粒度经用户批准 CR-LIC-001 修订|
|DB Schema Version|`DB-SCHEMA-CANDIDATE-V1`；原冻结64cdf09保留；增量至`20260930_0051` Platform 维护状态（CR-PLT-004），原0050 Parser 取消快照保留；无生产迁移|
|API Contract Version|`API-CONTRACT-CANDIDATE-V1`；API-01～API-05 PASS，Gate 2 已冻结（内容提交 `64cdf09`）|
|Test Summary|DOC05A05-P07 三视图定向26、前端全量970项/typecheck/build PASS；DOC05A05-P06 定向44、前端全量960项/typecheck/build PASS；DOC05A05-P05 定向149、前端全量916项/typecheck/build PASS；DOC05A05-P04 定向30、前端全量910项/typecheck/build PASS；DOC05A05-P03 定向143、前端全量880项/typecheck/build PASS；DOC05A05-P02 定向31、前端全量876项/typecheck/build PASS；DOC05A05-P01 SessionClient 定向139、前端全量845项/typecheck/build PASS；A05真实浏览器/PG审计、A06 Auth UTC-Z真实网络与后端1558无失败/2跳过、A07导航浏览器；A08-P02前端85及真实PG改密HTTP内部链通过、浏览器最终提交待人工；A09前端86跨路由合同；PRJ05A01客户端123、A02列表131、A03详情139；A04真实浏览器及独立HTTP/PG合成读链通过；PRJ05A05-P01前端147桥接、P02前端173创建客户端、P03-A01候选读取205、P03-A02创建页面212/typecheck/build合同；P04真实IAB/PG创建通过。AUT05A10-P01前端219私有User写桥接、P02前端249安全客户端、P03前端258页面合同；P04-A01隔离ASGI/PG写链通过。AUT05A11-P01前端265/typecheck/build用户只读页合同通过，P02 Windows11本机合成浏览器/PG匿名/普通用户拦截、Admin两用户列表/刷新及临时资源清理通过。AUT05A12-P01前端271状态传输合同，P02前端292状态响应合同，P03前端309详情强ETag合同，P04前端320/typecheck/build启停页面合同通过；P05-A01实际Windows11隔离ASGI/PG User启停/会话/历史重放和临时源清理exit0（首轮PG服务停止，恢复后重跑）。AUT05A13-P01～P03前端362/typecheck/build，P04隔离浏览器同用户改名v0→v1、旧名拒绝/新名登录及SQL一审计、临时清理和原只读API回归exit0（首轮PG服务停止，恢复后重跑）。新凭据浏览器提交待人工，正式HTTPS/信任/性能/三平台/全UAT仍未验，CR008 FAIL/Gate/包待|
|Next WBS|`PLT-MAINT-01-A03-P03-P02` 受控 OS 部署入口/状态恢复流程；随后生产 API/双 Worker 全覆盖及 OS 进程退出证明。P05 正式账户/Server2025、终态前无 ParseRecord、跨 Job retry、EVD 定位、正式 trust/TLS/CR008性能FAIL、POC-03质量FAIL/Gate3/完整包仍待|

## 自动执行策略

- 模式：按 `AI自主执行与最小人工确认规则 V1.1.md` 持续自主执行至可用程序包；偏差先建立 Change Request，再实施、验证并同步 GitHub；Gate 按实际证据关闭，不虚报。
- 代决策授权：用户 2026-09-24 明确授权原方案不兼容时自主分析并执行解决方案，默认接受，不再逐项询问；范围和安全边界见 `docs/changes/CR-EXEC-001-continuous-delivery.md`。客户数据外发、付款/额度重置、不可恢复生产操作和伪造客户确认不在授权内。
- 周额度规则：用户已于 2026-09-23 取消自动检查和 20% 停止线；后续仅在用户明确要求时查询。额度重置或购买仍需逐次明确确认。
- GitHub：允许在当前 Scope 和正确分支内自动 fetch、commit、push；禁止 force push、直接提交 main、覆盖未知远端修改或提交 Secret/客户数据。

## 最近检查点

- 2026-09-30/PLT-MAINT-01-A03-P03-P01 排他转换改为同事务复用 Auth 当前 Session+CSRF+DeploymentAdmin 权限，操作员 UUID 不再由调用方自称；PG18 合成管理员正例与错误凭据/非管理员/停用/撤销负例及 Audit 回滚 PASS，后端1661（3跳过）、wheel PASS。OS 部署入口和全生产停写未完成，维护模式/Gate3/包仍待。

- 2026-09-30/PLT-MAINT-01-A03-P02 PostgreSQL18 内部排他状态 Port 限时等待、状态/Audit USER 同事务、旧版本拒绝及 Audit 故障回滚；隔离双连接三次 PASS，单元2、后端1661（3既有跳过）、wheel PASS。Port 不验证传入操作员 UUID 的认证/授权，尚未接生产 CLI/API、双 Worker 或 OS 退出证明；维护模式/Gate3/包仍待。

- 2026-09-30/PLT-MAINT-01-A03-P01 PostgreSQL18 专用会话共享准入 Port 在双连接下验证并行共享/排他竞争、无长事务、状态拒绝及无连接池残留；持锁 backend 被终止后调用者报错且排他方可获锁，实证连接释放非静止证明。单元2、后端1659（3既有跳过）、wheel PASS；排他命令/生产接线/进程退出未完成，维护模式/Gate3/包仍待。

- 2026-09-30/PLT-MAINT-01-A02 DB0051 `plm.plt_maintenance_state` 单行 RUNNING/v0 Schema/ORM/触发器在隔离 PG18 空/有数据 up/down/up、版本转换/非法修改/含历史 down 拒绝 PASS；后端1657（3既有跳过）、wheel含 Migration/ORM PASS。无生产迁移；状态表不构成准入栅栏，DOC-03 前置/Gate3/包仍未通过。

- 2026-09-30/PLT-MAINT-01-A01 `CR-PLT-004` 记录 ADR007/008 停写要求与现有 UploadId 锁/进程停止不足，选择 PG 会话级共享/排他栅栏+持久状态，并列明 Schema/API/双 Worker/旧版进程并发验收与回滚。仅设计登记，无代码/并发 PASS；DOC-03 前置、Gate3及可用包仍阻塞。

- 2026-09-30/PAR01-A05-P01-P05-A02-P03-A03 Windows11 独立 spawn OS 进程与隔离 PG18/已提交合成扫描 PDF：错误 OCR 指纹拒绝且 Job PENDING；正确本地 PP-OCRv5 模型发布唯一 OCR_LINE/ResultRef、Job SUCCEEDED，父进程重开结果文件核 Hash/Size/模型指纹 PASS。PoC PG 恢复停止；正式 Vault License/SystemActor 用测试替身、物理断网/维护模式/Server2025/Debian未验，P05/Gate3/发行包仍待。

- 2026-09-30/CR-PAR-004 Windows11 隔离 OCR 环境发现 PaddleX3.7.2 精确要求 PyYAML6.0.2，与项目6.0.3冲突；登记 CR 后对齐并固定传递依赖。`pip check` 无冲突，真实 PP-OCRv5 离线显式模型合成 PNG/混合PDF PASS；后端全量1657（3既有跳过）、wheel 元数据 PASS。物理断网 wheelhouse/独立正式进程/三平台未验，CR 发行结论仍待。

- 2026-09-30/PAR01-A05-P01-P05-A02-P03-A02 Windows Parser CLI 接当前账户 DB/License/SystemActor、显式离线 OCR 模型路径及指纹、SIGINT/SIGTERM/SIGBREAK 协作停止；6项定向、后端全量1657（3既有跳过）、wheel PASS。真实独立进程/正式账户与维护模式未验证，P03/P05/Gate3/包仍待。

- 2026-09-30/PAR01-A05-P01-P05-A02-P03-A01 显式 Parser Worker 组合根接 Auth/Project/License/SystemActor、Document/Audit/Jobs 与离线 OCR 引擎 Port；真实隔离 PostgreSQL18/已提交合成文本 PDF 领 Job→唯一 ParseResultRef/Job成功 PASS。首轮假 PDF 按预期解析失败，换真实合成文件后重跑；单元2、后端全量1651（3既有跳过）、wheel PASS。正式 OCR 模型断网、目标账户、维护模式及进程信号未验证，Gate3/可用包仍待。

- 2026-09-30/PAR01-A05-P01-P05-A02-P02 Parser 调度层每轮至多一条过期取消与一个 Job；停止后不新领，待当前单步自然收敛才允许资源释放。定向15、Python3.13 后端全量1649（3既有跳过）、wheel PASS。仅内部循环，未接真实进程/正式信任及 OCR 模型；P05/Gate3/程序包仍未通过。

- 2026-09-30/PAR01-A05-P01-P05-A02-P01 CR-PAR-003 原用户现时授权：Parser 每次准备/启动/最终发布从 Auth 当前 User、Project 上传同角色、License 复核，并先验源后锁 Job。Windows11 隔离 PG18/真实合成上传停用 User、暂停项目成员、失效 License 后零结果，恢复后唯一发布；后端1646（3既有跳过）、wheel PASS。清理性取消/失败可继续，独立进程/正式账户/Gate3仍待。

- 2026-09-30/PAR01-A05-P01-P05-A01 Parser 五处关键状态/审计事务改为受控 SystemActor 动态身份捕获与提交前复核，保留内部固定 UUID 夹具兼容；Windows11 隔离 PG18/真实合成上传/HTTP 取消在 Audit 后身份变化时 Document/Audit/Jobs 全回滚、恢复源后成功，后端1642（3既有跳过）、wheel PASS。P05 进程入口/正式账户未完成。

- 2026-09-30/PAR01-A05-P01-P04-P03-P04 Parser 取消到期候选只读扫描/单步恢复调度在 Windows11 隔离 PG18/真实合成上传/HTTP 用户取消中，活租约无候选、两条到期有序恢复、身份失效零写、丢回执只读核验/唯一审计 PASS；竞争/身份变化单元测试，后端1638（3既有跳过）、wheel PASS。尚非独立进程或正式账户验收，Gate3不变。

- 2026-09-30/PAR01-A05-P01-P04-P03-P03 Parser 取消后的真实 PostgreSQL18 租约到期恢复：同事务 Document 记录/唯一 SYSTEM Audit/Jobs EXPIRED+CANCELLED；无记录/有 RUNNING 记录、活租约及错误代数拒绝、Audit/末端 Job 故障全回滚、只读提交复验 PASS。后端1635（3既有跳过）、wheel PASS；仅内部步骤，正式调度/SystemActor/Server2025/Debian及 Gate3 未通过。

- 2026-09-30/PAR01-A05-P01-P04-P03-P02 当前用户 Parser 取消 Owner 已接冻结 Job Cancel API/Windows 显式写组合；真实上传/PG18/HTTP 创建者或PM、PENDING/RETRY_WAIT/RUNNING、并发原 ETag、撤权/跨项目/License/CSRF拒绝及末端收据故障回滚 PASS。后端1635（3跳过）、wheel PASS；随机库清理/PoC PG恢复停止。合成信任源非正式发行，过期恢复/独立进程/Gate3仍待。

- 2026-09-30/PAR01-A05-P01-P04-P03-P01 CR-PAR-002/DB0050 Parser 取消首响应版本快照在隔离 PG18 空/有数据升降级、来源/不可变/非空降级拒绝 PASS；后端1632（3跳过）、wheel PASS，原0049保持；无生产迁移，正式信任/发行/Gate仍待。

- 2026-09-30/PAR01-A05-P01-P04-P02 Worker 长抽取中协作取消并停止发布；Document 当前 Job/代数记录（含启动回执不确定）与 Audit/Jobs 同事务确认。Worker定向12、Python3.13后端全量1631（3既有跳过）、Windows11隔离PG18/真实文件取消无新增结果及独立PG18未启动/晚期失败回滚、wheel PASS；随机库清理/PoC PG恢复停止。用户请求 Owner/过期恢复/独立进程、Gate3仍待。

- 2026-09-30/PAR01-A05-P01-P04-P01 Jobs 自有 Parser `pulse_parse` 在 RUNNING 续租、CANCEL_REQUESTED 不续租；仅活当前代可确认。定向5、Python3.13后端全量1628（3既有跳过）、Windows11隔离PG18 旧/过期/其他 Owner 拒绝与 wheel PASS；随机库清理/PoC PG恢复停止。尚未装配 Worker/Document/Audit 或用户请求 Owner，P04整体/Gate3仍待。

- 2026-09-30/PAR01-A05-P01-P03 已启动 ParseRecord 的失败与 Audit/Job 仅在当前租约同事务关闭，未启动不伪造运行历史；固定脱敏错误码与5/15秒有界重试。定向9、Python3.13后端全量1626（3既有跳过）、Windows11隔离PG18真实文件Worker失败、独立PG18致命/重试/未启动/旧租约及两类晚期回滚、wheel PASS；随机库清理/PoC PG恢复停止。取消/崩溃恢复/正式进程/Gate3仍待。

- 2026-09-30/PAR01-A05-P01-P02 Parser Worker 单步成功链含长解析独立短事务心跳、最终续租与 fenced 发布；定向4、Python3.13后端全量1621（3既有跳过）、Windows11隔离PG18/真实本地文件合成慢解析→ResultRef/ParseRecord/Audit/Job成功及空队列、wheel PASS；随机库清理/PoC PG恢复停止。Queue/Document 源在隔离夹具中为内部桩；正式进程、失败/取消/崩溃恢复、Gate3仍待。

- 2026-09-30/PAR01-A05-P01-P01 Jobs Parser 专用 `claim_next_parse` 仅筛 document/DOCUMENT_PARSE，沿用原 SQL 锁与接管；隔离 PG18 高优先级 Audit 混合队列非 Parse 行/Lease/Attempt 零写、Parse 到期接管与原通用领取 PASS。定向3、Python3.13后端全量1617（3既有跳过）、wheel PASS；随机库清理、PoC PG恢复停止。未装配正式 Worker，Gate3不变。

- 2026-09-30/PAR01-A04-P02-P03-P03 同一 Job 第2/3代当前租约的真实私有文件→ResultRef→ParseRecord→Audit→Job 成功发布及旧代拒绝，隔离 PostgreSQL18 两种后代、唯一结果引用/时间顺序 PASS。定向5、Python3.13后端全量1616（3既有跳过）、wheel PASS；随机库清理、PoC PG恢复停止。跨 Job 用户主动重试、正式 Worker/崩溃恢复、Evidence/Gate3仍待。

- 2026-09-30/PAR01-A04-P02-P03-P02 同一 DOCUMENT_PARSE Job 第2/3代以 Jobs 旧代证明对账旧 RUNNING→FAILED、未启动代补记 PENDING→CANCELLED，并启动当前 PENDING→RUNNING；真实 Audit 同事务。定向3、Python3.13后端全量1614（3既有跳过）、Windows11隔离 PG18 真实触发器/第三代/幂等/旧代拒绝/Audit失败回滚及wheel PASS；随机库清理、PoC PG恢复停止。仅同一 Job，后代成功发布/用户主动新 Job 重试/Worker/Gate3仍待。

- 2026-09-30/PAR01-A04-P02-P03-P01 当前 DOCUMENT_PARSE 活租约的 Jobs 旧代 Attempt 证明已实现；第1→2→3代过期接管、旧 token 与被篡改错误码拒绝经隔离 PostgreSQL18 验证。定向2、Python3.13后端全量1611（3既有跳过）、wheel PASS；随机库清理、PoC PG恢复停止。此项不写 Document ParseRecord，不宣称解析重试已可用或 Gate3通过。

- 2026-09-30/PAR01-A04-P02-P02 首次 Attempt 的受控结果文件实读、固定来源及当前 Job lease 重核后，ResultRef→ParseRecord→真实 Audit→Job 在同一事务成功发布；隔离 PostgreSQL18 真实触发器和审计/最终 lease 晚期失败回滚 PASS。定向3、Python3.13后端全量1609（3既有跳过）、wheel PASS。PoC 55432 端口被本机代理占用，仅验证临时使用55434；随机库清理并恢复PG原停止状态。仅首次 Attempt，正式 Worker/重试历史/Evidence/Gate3仍待。

- 2026-09-30/PAR01-A04-P02-P01 首次当前 Job lease/Outbox/固定 Document 来源重核后，Document 自有 ParseRecord 触发器合法 PENDING→RUNNING；同 Job 同代幂等、其他 Job 冲突。定向3、后端全量1606（3既有跳过）、Windows11隔离PG18真实1行/冲突、wheel PASS；随机库清理且PoC PG恢复停止。仅首次Attempt，尚无结果/Job成功发布与重试历史处理、Worker/Gate3。

- 2026-09-30/PAR01-A04-P01 Document私有ParseResult相对命名空间、真实临时磁盘同卷无覆盖写/Hash重开/Scope隔离、重复UUID与篡改拒绝；定向4（目录符号链接本机权限跳过1）、后端全量1603（3跳过）、wheel PASS。首轮跨Scope夹具误断言失败修正后重跑。文件未发布到DB，孤儿保留不可见；当前租约/ParseRecord/Job原子发布、崩溃对账/目标账户ACL、Gate3仍待。

- 2026-09-30/PAR01-A03-P04-P02 固定版本图片/混合 PDF OCR 候选结果：多帧 TIFF、PDF 原生+扫描分路、PAGE bbox/置信度/模型Hash；MIME/EXIF/摘要/无文字失败关闭。定向4、Python3.13后端全量1599（2既有跳过）、wheel PASS；本机 PoC 离线真实模型的无落盘合成 PNG1 与混合PDF原生1/OCR1 复跑脚本 exit0。未验证客户扫描件质量、Worker/ParseResult发布、受权Evidence/Viewer、目标账户和Gate3。

- 2026-09-30/PAR01-A03-P04-P01 本机 PoC Windows11 Python3.13/PaddleOCR3.7.0/PaddlePaddle3.3.1/PP-OCRv5 mobile det+rec 离线显式目录真实合成图片识别一行及归一化 bbox PASS；要求预期模型复合Hash吻合，不经网络模型源检查。首次 WindowsPath 类型误拒绝修后重跑；定向4、后端全量1595（2既有跳过）、wheel包含及依赖元数据PASS。模型和图片未入Git；实际扫描PDF/图片ParseResult、目标账户/物理断网/发行许可、Worker/Evidence/Gate3仍待。

- 2026-09-30/PAR01-A03-P03 PyMuPDF1.28.2 原生 PDF 逐页 `get_text(text,sort=True)`，NFC/LF 后逐行 TEXT_RANGE 页号/字符区间/SHA256；合成双页重放、混合无文本页OCR_REQUIRED、损坏/篡改拒绝。定向3、后端全量1591（2既有跳过）、wheel PASS。任何空白页目前也要求OCR；bbox高亮、表格/OCR、实际客户PDF、发行许可复核/Worker/Evidence/Gate3均待。

- 2026-09-30/PAR01-A03-P02 沿用 POC-01 Python3.13 已验证的 python-docx1.2.0/python-pptx1.0.2/openpyxl3.1.5 纳入后端；DOCX 段落/表格格、PPTX shape/表格格、XLSX 公式原文/工作表格抽取及四种类型化定位。定向6、后端全量1588（2既有跳过）、wheel依赖元数据PASS；损坏/恶意ZIP、篡改Hash、稀疏巨量表格拒绝，合并格左上去重。仅合成真Office文件，不证明自动页码/客户文件/正式Evidence/Worker/Gate3。

- 2026-09-30/PAR01-A03-P01 受控固定版本快照上的 UTF-8-SIG 纯文本/逗号 CSV 实际抽取，TEXT_RANGE 规范化字符区间+指纹及逻辑 CSV SHEET_RANGE A1 单元格均通过定向源位置复验；损坏摘要/编码/CSV/profile/超限失败关闭。定向4、Python3.13后端全量1582（2既有跳过）、wheel包含和diff检查PASS。3200万字符/10万节点上限显式失败；本项未执行 Worker/ParseRecord发布、Office/PDF/OCR或受权Evidence定位，Gate3不变。

- 2026-09-30/PAR01-A02-P02 当前 DOCUMENT_PARSE Job 租约+Outbox+Document 来源双短事务、私有文件快照 Hash/长度验收 PASS；真实隔离 PG/文件正常字节、错误 fencing 拒绝、合成篡改拒绝及一条无路径 Audit exit0。定向6、后端全量1578（2既有跳过）、wheel PASS；随机资源清理/PG 恢复停止。未启动正式 Worker/解析/OCR或发布结果。

- 2026-09-30/PAR01-A02-P01 Document 内部 Parser 输入元数据 Port 与真实 PG 上传后固定版本/Audit 证明通过；修复旧来源 SQL 把合法 `purpose_code` 误固定为 `SOURCE_UPLOAD` 的缺陷。首轮 PG 因此失败，修后完整重跑 exit0；定向7、后端全量1572（2既有跳过）、wheel PASS，随机库清理/PoC PG 恢复停止。当前无 Worker lease/物理字节快照结论。

- 2026-09-30/PAR01-A01 按 CR-PAR-001 将生产 Parser 基础合同作为 Phase2 Evidence 依赖前置，未提前关闭 Gate3。固定版本 UUID/Hash/大小/MIME 与九种 MIME 解析策略定向 3、Python3.13 后端全量 1569 项（2 跳过）、隔离 wheel 构建/包含检查 PASS；默认3.14缺依赖与非隔离构建缺 setuptools 的失败已在正确环境重跑。尚无 Worker/真实解析/精确定位证据。

- 2026-09-30/DOC05A06-P03 Windows 11 真实 IAB/HTTP/PG 只读 ParseRecord 面板：匿名401、非成员/跨项目404、2+1游标、固定版本三次合成 PENDING 与刷新、SQL 同 Job/外项目0及随机资源清理 exit0。首轮 Job refs 约束失败、第二轮会话断言错误，修复后完整重跑。无 Worker/解析成功结论；P08-A02 浏览器文件上传仍 INCOMPLETE。

- 2026-09-30/DOC05A06-P02 项目文档详情按需单版本 Parse 状态面板、续页/刷新、切版本/路由迟到阻断与 401/404 清旧；前端全量 1012 项/typecheck/build PASS。实际浏览器/PG 未跑，P08-A02 上传仍 INCOMPLETE。

- 2026-09-30/DOC05A06-P01 固定版本 ParseRecord PROJECT/GLOBAL 只读客户端、最长1024游标与安全状态/时间投影；首轮全量测试通过但测试类型声明失败，修正后前端全量 1006 项/typecheck/build PASS。没有页面或真实浏览器PG/Worker证据，P08-A02 仍 INCOMPLETE。

- 2026-09-30/DOC05A05-P08-A02 浏览器夹具与两份纯合成 PDF 已准备，`py_compile`/diff 检查及原网络模式回归通过；第三次实际 IAB 合成登录/项目→上传表单导航可见，未选文件，随后界面操作中断。精确清理本轮残留随机库/角色、合成 Vault 凭据和空临时根，PoC PG 恢复停止。文件 UI 上传确认未收到，实际上传/SQL 出口未跑，INCOMPLETE。

- 2026-09-30/DOC05A05-P08-A01 Windows11 隔离真实 HTTP/PG/文件上传新建/升版/Abort exit0：Content-Length/Hash/MIME、受权下载字节、2 Parse Job 入队、2 Commit/1 Abort Audit/幂等/跨项目拒绝、随机库/角色/Vault/文件根清理及事后库0通过。PoC PG 恢复原停止。实际浏览器/Worker处理、正式信任/Gate3/可用包待。

- 2026-09-30/DOC05A05-P07 PROJECT 新建/升版上传页与入口：Create→Content→Commit 状态机、原文件/Key 内存恢复、显式 Abort、首次回执非当前状态、401/跨项目迟到阻断；三视图定向 26、前端全量 970 项/typecheck/build PASS。无后端 API/Schema/Migration/权限/依赖变化；真实浏览器/PG 文件字节/Content-Length/Parse 队列及正式信任/Gate3/包待。

- 2026-09-30/DOC05A05-P06 PROJECT 上传 Commit/Abort 安全回执：新建/升版父 ETag、201 版本/Parse Job/Location、200 cleanup_pending、首次结果非当前状态证明；定向 44、前端全量 960 项/typecheck/build PASS。首轮 UUID 正则漏分组致 31 失败，修正/补测后完整重跑。无后端 API/Schema/Migration/权限/依赖变化；UI/实际文件/PG/浏览器/Parse、正式信任/Gate3/包待。

- 2026-09-29/DOC05A05-P05 PROJECT 上传 Commit/Abort 固定空体私有 Session/CSRF/原 Key，Commit 可选强父 ETag，Abort 不带版本；坏输入/401/互斥/60 秒中止不重传。定向 149、全量 916 项/typecheck/build PASS。无后端 API/Schema/Migration/权限/依赖变化；安全回执/UI/实际文件/Parse、正式信任/Gate3/包待。

- 2026-09-29/DOC05A05-P04 PROJECT 内容 Web Crypto SHA-256/短时令牌复核/200 大小与摘要安全回执、已知/未知分离且不重传；定向 30、前端全量 910 项/typecheck/build PASS。首轮测试类型构建失败修复后全量重跑。无后端 API/Schema/Migration/权限/依赖变化；真实浏览器 Content-Length/文件字节/内存性能、Commit/Abort/UI/Parse、正式信任/Gate3/包待。

- 2026-09-29/DOC05A05-P03 PROJECT 内容 PUT 前端私有 Session/CSRF/Blob/token/SHA 通道、固定路径/大小/401/互斥/5 分钟中止与不自动重传；定向 143、全量 880 项/typecheck/build PASS。无后端 API/Schema/Migration/权限/依赖变化；浏览器实际 Content-Length/文件字节与 Hash、业务回执、Commit/Abort/UI/Parse、正式信任/Gate3/包待。

- 2026-09-29/DOC05A05-P02 PROJECT UploadIntent 新建/升版安全客户端：输入/UUID/Key/201 JSON/trace/token/UTC 到期/Location/no-store、确定性拒绝/未知结果分离；定向 31、全量 876 项/typecheck/build PASS。首轮 11 个错误映射用例夹具结构错误修正后完整重跑。无后端 API/Schema/Migration/权限/依赖变化；真实内容/Commit/Abort、UI/PG/浏览器/Parse、正式信任/Gate3/包待。

- 2026-09-29/DOC05A05-P01 PROJECT UploadIntent 前端私有 Session/CSRF/原 Key 桥接，固定同源路径/坏输入/401/互斥/超时不重试；定向 139、前端全量 845 项/typecheck/build PASS。无后端 API/Schema/Migration/权限/依赖变化；响应校验、内容/Commit/Abort、UI、真实解析、正式信任/Gate3/包待。

- 2026-09-29/DOC05A04-P03 Windows11 隔离真实 50 字节合成文件的 HTTP/PG 与 IAB 下载 SHA-256 一致，附件头/匿名401/外项目404/Range400、随机库/角色/Vault/临时文件根清理 exit0；前端 841 项/typecheck/build PASS。首轮新标签事件不可观测，改同标签重跑；两份下载已送回收站，IAB 临时标签关闭未证实。PoC PG 恢复停止；正式信任/三平台/Gate3/包待。

- 2026-09-29/DOC05A04-P02 受权版本行原生附件下载链接与未加载/空态隐藏，保留当前页且不在前端缓存正文；定向视图 10、全量 841 项/typecheck/build PASS。无后端/Schema/Migration/权限变化；实际文件/浏览器下载待验。

- 2026-09-29/DOC05A04-P01 DocumentVersion 固定同源附件地址，严格项目/GLOBAL 与 UUID 校验；定向 69、前端全量 841 项/typecheck/build PASS。无后端/Schema/Migration/权限变化；尚无 UI/真实文件下载证据。

- 2026-09-29/DOC05A03-P03 Windows11 合成版本 API/PG 与实际 IAB 完整 exit0：成员按需看到版本 1/MIME/大小/哈希、详情刷新清旧重读，匿名401/外项目404；SQL 51 匹配 AVAILABLE 元数据、随机库/角色/Vault 清理，PoC PG 恢复原停止。首两轮 SHA 入库类型/Session 断言失败修复后完整重跑。仅合成元数据，无真实文件/下载/正式信任结论。

- 2026-09-29/DOC05A03-P02 项目 Document 详情按需可用版本历史、续页/空态及刷新/跨路由隔离；视图定向 10、前端全量 839 项/typecheck/build PASS。无后端/Schema/Migration/权限变化；实际浏览器/PG 与正式信任待。

- 2026-09-29/DOC05A03-P01 DocumentVersion 安全只读客户端与 50 条签名游标/固定路径；定向 67、前端全量 835 项/typecheck/build PASS。无后端/Schema/Migration/权限变更，实际版本 UI/浏览器/PG 与正式信任待。

- 2026-09-29/DOC05A02-P02 Windows11 隔离 IAB/PG 完整 exit0：合成成员项目列表→Document 历史→首条详情，安全元数据/`"v0"`/刷新重读通过；SQL 51 ACTIVE+1 RESTRICTED/FOREIGN1，随机库/角色/Vault 清理，PoC PG 恢复原停止。仅合成信任，正式信任/其他平台/Gate3/包待。

- 2026-09-29/DOC05A02-P01 项目 Document 列表行安全详情入口/直达受权 GET、强 ETag、刷新失败清旧及跨路由迟到结果隔离；定向 12、前端全量 814 项/typecheck/build PASS。无后端 API/Schema/Migration/权限/依赖变化；实际浏览器/PG、正式信任/其他平台/Gate3/包待。

- 2026-09-29/DOC05A01-P03-A02 Windows11 隔离 IAB/PG 第二轮完整 exit0：合成成员由项目详情进 Document 历史，50→51 续页且受限/外项目不可见，刷新回 50；SQL 51 ACTIVE+1 RESTRICTED/FOREIGN1、随机库/角色/Vault 清理，PoC PG 恢复原停止。首轮会话中断遗留已精确清理，PG crash recovery 原因未证实。仅合成信任，正式信任/其他平台/Gate3/包待。

- 2026-09-29/DOC05A01-P03-A01 Windows11 临时随机库真实 Session/API Document 列表 50+1、签名游标跨会话拒绝、匿名/非成员/跨项目拒绝、详情强 ETag/安全投影及 SQL 51 ACTIVE+1 RESTRICTED/FOREIGN1，完整夹具 exit0、库/角色/Vault 清理，PoC PG 恢复原停止。浏览器工具无法确认 Chrome URL，A02 未验证；正式信任/其他平台/Gate3/包待。

- 2026-09-29/DOC05A01-P02 项目 Document 历史页/项目详情入口、50 条分页/刷新、拒绝清旧、跨页去重与切项目迟到结果隔离；定向 6 项、前端全量 808 项/typecheck/build PASS。无后端 API/Schema/Migration/权限/依赖变化；实际浏览器/PG、正式信任/其他平台/Gate3/程序包仍待。

- 2026-09-29/DOC05A01-P01 PROJECT/GLOBAL Document 元数据只读客户端 46 定向、802 全量前端测试/typecheck/build PASS；固定双 Scope 路径、50 条游标、Scope/ID/强 ETag 与安全元数据投影。首轮 UUID 正则和类型问题修正后完整重跑。无后端 API/Schema/Migration/权限/依赖变化；页面及实际浏览器/PG、正式信任/其他平台/Gate3/程序包仍待。

- 2026-09-29/PRJ05A15-P04 Windows11 隔离 API-only/实际 IAB 项目名称 PATCH 两轮 exit0：权限/CSRF/跨项目/版本拒绝、首次 v1/同名 v2 与独立 GET；SQL OWNED 新名 v2 或 v1、FOREIGN 未变、对应 2 或 1 Audit、无 PATCH 收据，随机库/角色/Vault 清理通过。PoC PG 验收后无进程，停机原因未证实。无生产 API/Schema/Migration/权限/依赖变化；正式信任/Gate/完整包仍待。

- 2026-09-29/PRJ05A15-P03 项目名称修改仅负责人/ACTIVE且显式确认，与归档互斥；成功/未知清旧详情、回执与独立 GET 分离、跨项目迟到结果丢弃；前端 756 项/typecheck/build 通过，首轮测试样本类型错误修正后完整重跑。无后端 API/Schema/Migration/权限/依赖变化；实际浏览器PG及正式信任/Gate/包待。

- 2026-09-29/PRJ05A15-P02 名称 NFKC 与 200 回执绑定原项目 ID/编号/创建时间、ACTIVE/目标名、`v+1` 和头 ETag；已知拒绝与伪成功/断线未知分离，前端 751 项/typecheck/build 通过。无后端 API/Schema/Migration/权限/依赖变化；确认页/浏览器PG及正式信任/Gate/包待。

- 2026-09-29/PRJ05A15-P01 项目名称更新固定 Project ID/强 If-Match/私有 CSRF 同源单次 PATCH，401 清证明，超时不重试且互斥；前端 724 项/typecheck/build 通过。无后端 API/Schema/Migration/权限/依赖变化；业务回执/页面/浏览器PG及正式信任/Gate/包待。

- 2026-09-29/PRJ05A14-P04 Windows11 隔离 API-only/实际 IAB 浏览器归档两轮 exit0：权限/CSRF/跨项目/版本/Key 重放与冲突、显式确认后独立已归档重读；SQL OWNED ARCHIVED/v1、FOREIGN ACTIVE/v0、负责人保留及单 Audit/收据、随机资源清理通过。PoC PG 恢复原停止，启动旧 PID 提示原因未证实。无生产 API/Schema/Migration/权限/依赖变化；正式信任/Gate/完整包仍待。

- 2026-09-29/PRJ05A14-P03项目归档仅当前ACTIVE项目负责人显式确认，首次回执与独立详情分离，未知原Key恢复需成功重读原ACTIVE/同版本，冲突锁页及迟到结果丢弃；前端720项/typecheck/build通过。无后端API/Schema/Migration/权限/依赖变化；实际浏览器PG和正式信任/Gate/包待。

- 2026-09-29/PRJ05A14-P02归档首回执绑定原Project ID/编号/名称/创建时间、ARCHIVED/v+1与响应ETag，同Key重放不冒充当前状态，已知拒绝/伪成功/断线分离；前端715项/typecheck/build通过。无后端API/Schema/Migration/权限/依赖变化；确认页/实际浏览器PG及正式信任/Gate/包待。

- 2026-09-29/PRJ05A14-P01项目归档固定 Project ID/强版本/原幂等Key/空Body私有CSRF同源单次POST，401清证明、超时不重试且互斥；前端687项/typecheck/build通过。无后端API/Schema/Migration/权限/依赖变化；业务回执/确认页/浏览器PG及正式信任/Gate/包待。

- 2026-09-29/PRJ05A13-P04隔离API-only匿名/权限/CSRF/缺版本/在用拒绝、FREE首次/重放/Key冲突/独立历史及SQL一审计/结果/收据通过；实际Windows11 IAB选FREE/v0显式确认、首回执后独立刷新为已停用。两轮随机库/角色/Vault清理exit0；首轮SQL收据关联断言错误修正后全新重跑。原PoC PG开始和结束均停止，结束时尝试正常stop已无进程，停机原因未证实。仅合成信任，正式信任/Gate/包待。

- 2026-09-29/PRJ05A13-P03部门停用仅负责人/ACTIVE显式确认、首次回执与当前历史分离、未知原Key/原版恢复须成功重读且原行未变、幂等冲突锁页及迟到结果丢弃；前端683项/typecheck/build通过。无后端API/Schema/Migration/权限/依赖变化；实际浏览器PG及正式信任/Gate/包待。

- 2026-09-29/PRJ05A13-P02部门停用200首次回执绑定原ID/编号/名称/创建时间、INACTIVE/v+1/强ETag，原Key重放不冒充当前状态，明确在用409等拒绝与未知/断线分离；前端679项/typecheck/build通过。无后端API/Schema/Migration/权限/依赖变化；页面/浏览器PG及正式信任/Gate/包待。

- 2026-09-29/PRJ05A13-P01部门停用固定双ID/强If-Match/原幂等Key/空Body私有CSRF同源单次POST，401清证明、超时不重试且互斥；前端652项/typecheck/build通过。无后端API/Schema/Migration/权限/依赖变化；业务回执/页面/浏览器PG及正式信任/Gate/包待。

- 2026-09-29/PRJ05A12-P04隔离API-only HTTP/PG部门PATCH匿名401、非负责人404、CSRF403、外项目404、缺If-Match428、变更v1/旧版409/无变化保持v1、历史重读通过；实际Windows11 IAB由历史选择ACTIVE、明确确认、回执后独立刷新通过。SQL NEW/v1、单Audit/无PATCH收据，随机库/角色/Vault清理exit0，PoC PG恢复原停止。无生产API/Schema/Migration/权限/依赖变化；正式信任/其他平台/性能质量/Gate/可用包待。

- 2026-09-29/PRJ05A12-P03部门历史行内ACTIVE负责人更新、改字段撤确认、原快照版本提交、成功/未知均清旧列表，独立成功刷新才恢复写入口；跨项目迟到结果丢弃。首轮测试夹具复用已消费Response失败，修正后前端648项/typecheck/build通过。无后端API/Schema/Migration/权限/依赖变化；实际浏览器PG及正式信任/Gate/包待。

- 2026-09-29/PRJ05A12-P02部门PATCH安全客户端规范字段并绑定原ID/创建时间/ACTIVE/目标及未改字段/强ETag/v0→v1或无变化原版，明确拒绝与未知分离、断线不重试；前端644项/typecheck/build通过。无后端API/Schema/Migration/权限/依赖变化；页面/浏览器PG及正式信任/Gate/包待。

- 2026-09-29/PRJ05A12-P01部门PATCH固定双ID/强ETag/私有CSRF/同源单次请求通道，401清证明、超时不重试且互斥；前端617项/typecheck/build通过。无后端API/Schema/Migration/权限/依赖变化；业务响应/页面/浏览器PG及正式信任/Gate/包待。

- 2026-09-29/PRJ05A11-P04部门创建隔离API-only HTTP/PG匿名401、非负责人404、CSRF403、外项目404、201原Key重放/v0、异载荷409、历史重读通过；实际Windows11 IAB从历史进入创建、明确勾选、首次回执及历史NEW重读通过。SQL一新增ACTIVE/v0部门、单Audit/完成收据，随机库/角色/Vault清理exit0，PoC PG恢复原停止。无生产API/Schema/Migration/权限/依赖变化；正式信任/其他平台/性能质量/Gate/可用包待。

- 2026-09-29/PRJ05A11-P03部门创建负责人入口/显式确认页面、未知原Key恢复、冲突锁页、first/current分离及切项目迟到丢弃；前端613项/typecheck通过，首次合并build进程异常退出、单独完整build重跑通过。无后端API/Schema/Migration/权限/依赖变化；真实浏览器PG与正式信任/Gate/包待。

- 2026-09-29/PRJ05A11-P02部门创建NFKC二字段、201首次回执与原输入/ACTIVE/v0/ETag/Location绑定、重放非当前状态证明、伪成功/未知不自动重发；前端604项/typecheck/build通过。无后端API/Schema/Migration/权限/依赖变更，页面/浏览器PG与正式信任/Gate/包待。

- 2026-09-29/PRJ05A11-P01部门创建固定前端POST、规范Project路径/原Key/私有CSRF/同源Cookie、401清证明/超时一次，前端575项/typecheck/build通过。无后端API/Schema/Migration/权限/依赖变化；业务响应/页面/实际PG浏览器与正式信任/Gate/包待。

- 2026-09-29/PRJ05A10-P03 Windows11合成隔离HTTP/浏览器/PG部门历史50+2、一条停用、匿名/非成员/跨项目拒绝、SQL52/1/零部门写及随机资源清理exit0，PoC PG恢复原停止。首轮两处fixture断言错误修复后完整重跑；无生产程序/API/Schema/Migration/权限/依赖变更，正式信任/其他平台/性能/质量/Gate/包待。

- 2026-09-29/PRJ05A10-P02部门历史只读页面/项目详情入口，ACTIVE/INACTIVE、固定50条续页/刷新，拒绝/跨页重复/切项目迟到清旧；前端563项/typecheck/build通过。无后端API/Schema/Migration/权限/依赖变化；实际浏览器PG、正式信任/其他平台/性能/质量/Gate/包待。

- 2026-09-29/PRJ05A10-P01部门历史只读客户端固定50条、ACTIVE/INACTIVE安全投影、项目/游标/错误/超时失败关闭；前端557项/typecheck/build通过。无后端API/Schema/Migration/权限/依赖变化；页面/浏览器PG、正式信任/其他平台/性能/质量/Gate/包待。

- 2026-09-29/PRJ05A09-P04 Windows11隔离合成 HTTP/浏览器/PG 成员暂停→恢复→移除通过，原 Key 重放/冲突、权限/CSRF/跨项目边界和每次 first/current 分离；SQL 最终 REMOVED/v3、三条 Audit 与三份收据，随机资源清理 exit0，PoC PG 恢复原停止。无生产程序/Migration/API/权限/依赖变化；正式信任/其他平台/性能/质量/Gate/包待。

- 2026-09-29/PRJ05A09-P03项目成员暂停/恢复/移除显式确认页、首次回执与当前历史分离、未知原Key恢复、冲突锁写和迟到回执丢弃；前端520项/typecheck/build通过。无Migration/API/权限/依赖变，真实浏览器PG/正式信任/Gate/包待，下一P04。

- 2026-09-29/PRJ05A09-P02三状态首次回执客户端，严格绑定原成员/User/角色/部门/生效时间、目标状态和强ETag，重放回执明确非当前状态证明；已知拒绝/未知结果分离，前端515项/typecheck/build通过。无Migration/API/权限/依赖变，页面/真实浏览器PG/正式信任/Gate/包待，下一P03。

- 2026-09-29/PRJ05A09-P01成员暂停/恢复/移除固定空Body POST、双UUID/强ETag/原Key/私有CSRF、互斥及未知结果不自动重发，前端496项/typecheck/build通过；无Migration/API/权限/依赖变化，业务响应/页面/真实浏览器PG待，下一P02。

- 2026-09-29/PRJ05A08-P04真实Windows11浏览器成员PATCH v0→v1及重读角色/部门通过，独立HTTP匿名/非负责人/CSRF/跨项目/旧版本/同值验证与SQL一次变更一审计通过；fixture最终exit0、随机库/角色/Vault清理，PoC PG恢复原停止。首轮旧Session断言失败修正，会话中断残留测试资源精确清理后重跑；仅合成信任，无程序/Migration/API变更，正式信任/Gate/包待。

- 2026-09-28/PRJ05A08-P03项目成员历史内修改角色/部门，强版本/目标用户/ACTIVE部门显式确认，已知拒绝刷新与未知锁写，迟到回执丢弃；前端490项/typecheck/build通过。无Migration/API/权限/依赖变，真实浏览器PG/正式信任/Gate/包待，下一P04。

- 2026-09-28/PRJ05A08-P02成员PATCH安全业务客户端绑定原成员/User/状态/起止时间、期望角色/部门与强ETag，未知结果不自动重试；前端485项/typecheck/build通过。首轮UUID及类型检查问题修正后全量复验；无Migration/API/权限/依赖变化，页面/真实浏览器PG/正式信任/Gate/包待，下一P03。

- 2026-09-28/PRJ05A08-P01成员PATCH固定前端传输双UUID/强v0 If-Match/私有CSRF/互斥、未知结果不自动重试，前端479项/typecheck/build通过。仅传输合同、无Migration/API/权限/依赖变；业务响应/浏览器PG、正式信任/Gate/包待，下一P02。

- 2026-09-28/PRJ05A07-P03-A05实际Windows11浏览器/隔离PG成员创建成功，精确候选/ACTIVE部门/角色确认/成员Audit收据各一；API重放201/冲突409，旧项目读/成员历史/项目创建三模式回归，前端475项/typecheck/build通过。首轮API-only会话断言修正、浏览器揭示A03原生fetch receiver并修复补测试后重跑。每轮资源清理，PoC PG恢复原停止状态；正式信任/其他平台/性能/质量/Gate3/包待。

- 2026-09-28/PRJ05A07-P03-A04成员创建页面、路由与入口，用户名变化清候选、明确角色/部门确认、未知结果原输入原Key恢复；前端474测试/typecheck/build通过。首轮3测试选择器定位问题修正重跑。仅页面合同，无实际浏览器PG，正式信任/Gate/包待；下一A05。

- 2026-09-28/PRJ05A07-P03-A03前端私有CSRF单次候选POST与ACTIVE部门分页安全客户端，全量468测试/typecheck/build通过；首轮1测试队列设置问题修正重跑。无Migration/后端API/权限/依赖变化，页面/浏览器PG、正式信任/Gate/包待；下一A04。

- 2026-09-28/PRJ05A07-P03-A02两种Windows显式平台模式装配候选API，默认/login404，隔离PG18真实Session/负责人/跨项目/Origin/CSRF/License/缺信任源关闭且无成员/Audit写；全后端1566 OK/2既有跳过、开发wheel通过。仅合成信任源，正式目标账户/Server2025/Debian/浏览器/性能/Gate3/可用包待；下一A03前端选择。

- 2026-09-28/PRJ05A07-P03-A01新增精确用户名成员候选可选POST，当前ACTIVE项目负责人/Session/CSRF/License、统一空候选、摘要持久限流；5Unit+3合同，全后端1566 OK/2既有跳过，隔离PG18 head0049真实权限/撤会话/限流/零成员Audit写与临时清理、开发wheel通过。初拟GET经安全复核改POST，默认/Windows生产组合未挂，下一A02；正式信任/Gate/包待。

- 2026-09-28/PRJ05A07-P03前置核查：冻结成员POST需目标User UUID，但唯一User候选列表属DeploymentAdmin，当前ProjectManager不可用；无技术ID手填方案，页面按Skill停止，登记CR-PRJ-006非破坏性精确候选端点方案。仅文档/无程序API运行变更，不标PASS；下一A01受权候选解析。

- 2026-09-28/PRJ05A07-P02成员创建安全响应客户端以201/初始状态/强ETag/Location/请求身份绑定认定成功，已知拒绝与未知结果分离、微秒生效时间核验；前端462/462、typecheck/build通过。无Migration/API/权限/依赖变；页面/实际浏览器PG/正式信任/Gate/包待。

- 2026-09-28/PRJ05A07-P01固定成员POST传输、规范Project路径/原Key/私有CSRF、401清证明/超时单次；前端430/430、typecheck/build通过。响应/页面/实际PG/正式信任/Gate/包待。

- 2026-09-28/PRJ05A06-P03 Windows11隔离浏览器实施成员历史拒绝、负责人50+2含移除记录；HTTP管理员/外项目404与游标绑定400，SQL52历史/51有效、临时清理和旧API回归exit0。首轮PG未运行，WAL恢复后执行，原因未证实。正式信任/Gate/包待。

- 2026-09-28/PRJ05A06-P02成员历史页面、项目详情入口、固定50条续页、安全拒绝清旧/跨项目迟到丢弃；前端418/418、typecheck/build通过。实际浏览器/PG/正式信任/Gate/包待。

- 2026-09-28/PRJ05A06-P01项目成员历史分页客户端固定50条/安全投影/同源Cookie/游标形状与超时单次；前端410/410、typecheck/build通过。页面/实际浏览器/正式信任/Gate/包待。

- 2026-09-28/AUT05A13-P04 Windows11隔离浏览器同一合成用户改名v0→v1、旧名登录被拒/新名成功、SQL一条改名审计、临时资源清理和原API回归exit0；首轮本机PG服务停机，核无临时库后WAL恢复，原因未证实。正式信任/Gate/包待。

- 2026-09-28/AUT05A13-P03独立改名页面/入口、强版本确认、first/当前分离、未知封锁与路由迟到回执丢弃，前端362/362、typecheck/build通过；实际浏览器/PG/正式信任/Gate/包待。

- 2026-09-28/AUT05A13-P02安全改名响应客户端及26场景，首轮UUID正则少段导致18失败，修复后前端353/353、typecheck/build通过；页面/实际PG浏览器/正式信任/Gate/包待。

- 2026-09-28/AUT05A13-P01管理员User改名固定前端PATCH传输桥、强版本`"v0"`/私有CSRF/401清证明/超时单次及互斥，前端327/327、typecheck/build通过；响应客户端/UI/实际浏览器/正式信任/Gate/包待。

- 2026-09-28/AUT05A12-P05-A02-A02真实浏览器合成Member受限、Admin详情`"v0"`→停用first/current`"v1"`→启用first/current`"v2"`，SQL终态ENABLED/v2、旧Member Session撤销与2不可变结果。夹具3Session、库/角色/Vault清理及原只读API回归exit0；正式trust/TLS/Server2025/Debian/性能/质量/Gate3/包仍待。

- 2026-09-28/AUT05A12-P05-A02-A01实际Windows11隔离浏览器发现新User合法`"v0"`被前端详情/状态传输拒绝；DEC-425记录后修三处客户端，323/323测试/typecheck/build、管理员详情/刷新及普通用户拦截通过。夹具2项目/4Session/1成员、自有库/角色/Vault清理exit0；状态按钮未提交，正式信任/Gate/包待。

- 2026-09-28/AUT05A12-P05-A01首轮本机PG连接超时，证实服务停；原目录WAL恢复后真Factory/ASGI/PG启停及旧/新Session、原Key重放、关闭模式/故障注入exit0，publication临时库0。停机原因未知，浏览器和正式信任未验。

- 2026-09-28/AUT05A12-P04用户详情/启停页面、强版本显式确认、未知原Key恢复及历史first/当前分离，前端320/typecheck/build通过；真实浏览器/PG另验，正式信任/Gate/包待。

- 2026-09-28/AUT05A12-P03详情GET八字段安全投影/目标强ETag/UTC核验，前端309/typecheck/build通过；首轮ETag类型错误已修复重测。页面/实际浏览器另验，正式信任/Gate/包待。

- 2026-09-28/AUT05A12-P02启停八字段安全响应/强ETag与状态绑定、确定拒绝和结果未知分流，前端292/typecheck/build通过；首轮UUID/类型错误已修复重测。真实浏览器/PG与UI另验，正式信任/Gate/包待。

- 2026-09-28/AUT05A12-P01前端User启停固定POST桥接/强版本原Key/私有CSRF/空body及超时不重发，271测试/typecheck/build通过；响应解析与UI/真实浏览器另验，正式信任/Gate/包待。

- 2026-09-28/AUT05A11-P02 Windows11隔离浏览器匿名/普通用户只见权限提示，合成Admin用户列表2条及刷新；实库2项目/2 Session/1成员、夹具库/角色/Vault删除通过。50+分页浏览器和正式信任未验；标签关闭中断但服务已停。

- 2026-09-28/AUT05A11-P01管理员用户只读列表/显式分页/安全投影，前端265/typecheck/build通过；真实浏览器另验，下一A11-P02。无Migration/API/权限/依赖变，正式信任/Gate/包待。

- 2026-09-28/AUT05A10-P04-A01原Windows显式User创建ASGI/PG链增201八字段/ETag/Location/UTC/密码不回显断言、重放/新账户登录/权限/只读关闭exit0，外部临时库0。浏览器新凭据提交未由AI代办；下一独立只读管理UI，正式信任/Gate/包待。

- 2026-09-28/AUT05A10-P03管理员创建账户UI，普通/受限/只读零创建、密码即时清空、未知同Key重输原密码恢复；前端258/typecheck/build通过。真实User创建链下一P04，正式信任/Gate/包待。

- 2026-09-28/AUT05A10-P02创建客户端NFC用户名/密码字节校验、201八字段/头/初态和确定/未知分流；前端249/typecheck/build通过。页面与真实写未验，下一P03。无Migration/API/权限/依赖变，正式信任/Gate/包待。

- 2026-09-28/AUT05A10-P01固定User创建同源CSRF单次POST、原Key/互斥/401清状态、前端219/typecheck/build通过；无DTO/UI/真实User写，本项不称完整管理可用，下一P02。无Migration/API/权限/依赖变，正式信任/Gate/包待。

- 2026-09-28/PRJ05A05-P04-A02真实IAB合成管理员登录/候选选择/点击创建并见确认回执；fixture SQL 3项目/1会话/2有效成员及新负责人/审计/收据各1、exit0清自有源。关页中断后PG异常停机恢复，外部前缀库/角色0、旧只读回归exit0；异常保留，正式信任/Gate/包待。

- 2026-09-28/PRJ05A05-P04-A01新隔离真实HTTP/PG管理员候选200/创建201/原Key重放201/冲突409、匿名401/成员404，SQL新项目/负责人/审计/收据各1，进程清库/角色/Vault和外部前缀0；旧只读回归通过。合成License范围，不等于浏览器/正式信任；下一P04-A02，Gate/包待。

- 2026-09-28/PRJ05A05-P03-A02管理员创建项目页面/启用负责人选择/原Key恢复合同，前端212/typecheck/build通过；初轮3测试问题修复重跑。无真实PG/browser写验，下一P04。无Migration/API/权限/依赖变，正式信任/Gate/包待。

- 2026-09-28/PRJ05A05-P03-A01管理员用户候选列表客户端，50条显式分页/白名单/安全拒绝；前端205/typecheck/build通过。初次build仅测试类型错误，修复重跑。未接页面或真实写链；下一P03-A02。无Migration/API/权限/依赖变，正式信任/Gate/包待。

- 2026-09-28/PRJ05A05-P02项目创建DTO/NFKC/首负责人UUID、201 Location/ETag强校验与确定/未知结果分流，前端173/typecheck/build通过；无UI/真实写，下一P03。无Migration/API/权限/依赖变，正式信任/Gate/包待。

- 2026-09-28/PRJ05A05-P01仅冻结项目创建路径的私有CSRF单次同源写桥接，401清本地证明/未知结果不自动重试；前端147/typecheck/build通过。Project DTO/UI/真实写未接，无Migration/API/权限/依赖变；下一P02，正式信任/Gate/包待。

- 2026-09-28/PRJ05A04-P02独立新库真实HTTP成员列表/详情200、外项目404、管理员空列表200/详情404，2项目/2Session/1有效成员、自动清理及外部库/角色/Vault 0；与原实际浏览器证据分别记录，Windows11合成A04收口PASS，首轮中断保留。无生产/API/Schema/权限/依赖变，下一管理员创建项目UI链；正式信任/Gate/包待。

- 2026-09-28/PRJ05A04-P01 Windows11真实浏览器成员项目/详情、外项目统一拒绝、管理员0项目及退出已观察；fixture在浏览器关闭时中断，终态SQL未执行，原隔离PG恢复后自有临时库/角色/Vault精确清零。只记PARTIAL，下一P02补终态SQL/HTTP；正式信任/Gate/完整包仍待。

- 2026-09-28/PRJ05A03 详情页直接URL服务端重核、统一404与路由换ID清旧内容，前端139/typecheck/build通过；实际浏览器/PG未验，下一Windows11隔离联调。无Migration/API/权限/依赖变，改密浏览器提交、正式信任/Gate/完整包待。

- 2026-09-28/PRJ05A02 我的项目入口/页面列表仅消费实时服务端返回；无身份/改密受限不请求，管理员空列表和错误清旧内容，Auth摘要非授权。前端131/typecheck/build与跨路由反例通过；本项真实浏览器/PG尚未跑，下一详情页。无Migration/API/权限/依赖变，改密浏览器提交、正式信任/Gate/完整包待。

- 2026-09-28/PRJ05A01 项目只读客户端37新测试，前端123/typecheck/build通过；服务端实时授权、当前单项目分页合同、详情ID/ETag严格核验，无浏览器/真实网络验收。无Migration/API/权限/依赖变，下一项目入口页面。改密浏览器提交、正式信任/Gate/完整包仍待。

- 2026-09-28/AUT05A09 AppShell实例级SessionClient内存共享，导航往返保原客户端，刷新/新实例无写权与自动GET；前端86/typecheck/build通过。Auth浏览器改密提交待人工/正式信任/Gate/包不变，下一PRJ-05只读项目入口。

- 2026-09-28/AUT05A08-P02普通/受限本人改密UI、密码确认/清除及503同Key恢复安全交互实现；前端85/typecheck/build通过，原Windows真实PG写工厂改密正常/旧Cookie401/新密码200/提交后503同Key恢复exit0，临时publication库count0。computer-use Skill禁止代理最终改密提交，真实浏览器端到端留人工验收；不冒充Gate3或可用包完成，下一转独立Phase2任务。

- 2026-09-28/AUT05A08-P01前端改密Client普通/受限同源单次POST/CSRF/原Key、输入和响应严格校验、未知结果清本地状态不自动重试；80测试/typecheck/build通过。首次类型检查失败已修复重跑；尚无页面或真实浏览器改密链，下一P02。

- 2026-09-28/AUT05A07只修页头导航专属Flex间距/换行，Windows11实际浏览器桌面与360px无水平溢出、两个链接Tab可见焦点；前端66/typecheck/build通过，自有Vite/tab关闭。未运行后端的静态布局检验不冒充登录功能或正式发行；下一A08受限改密界面前置。

- 2026-09-28/AUT05A06 按CR-AUT-009修Auth登录/GET/续期三响应UTC-Z，原冻结API字段/存储/权限不变；正负offset、UTC与naive拒绝及三合同测试关联15项PASS，后端全量1558无失败/2跳过，实际PG/Uvicorn/Vite原9GET/12POST加三UTC断言PASS，开发wheel与自有源清理通过。无Migration/依赖升级，正式HTTPS/Server2025/Debian/CR008性能FAIL/Gate3/包待，下一A07独立UI排版验收。

- 2026-09-28/AUT05A05 首轮真实浏览器暴露native fetch receiver与PG偏移时间解析，修复并增加回归测试。新独立fixture经实际浏览器错密码/三登录/续期/两退出/刷新只读重登通过；PG精确4/3/1/2/2及服务/库/角色/Vault清理PASS，前端66/typecheck/build PASS。超时及运行器错误再启、首轮失败如实留档；仅Windows11 loopback合成，服务端UTC合同、正式HTTPS/信任/Server2025/Debian/Gate3/包待，下一A06先核服务端时区输出。

- 2026-09-27/AUD-03-A07-P02仅Windows写模式装配导出POST，默认/login/readonly404；1155无失败/2跳过、实际Factory提交→任务GET→generic Worker/心跳/发布→结果下载摘要与size一致，重放/冲突/拒绝无写/单Attempt、构造故障/实际缺正式信任拒绝半启动、旧下载/原发布/wheel通过。无新Migration/依赖/权限，正向合成信任/后台在验证进程，非正式服务/UI/全Scope/完整包/GatePASS；下一取消expected_version前置。

- 2026-09-27/AUD-03-A07-P01可选项目/admin提交POST、严格输入/浏览器安全/原同事务幂等与202固定受理地址，1155无失败/2跳过，真实PG-CSRF/权限/重放冲突/失败十表回滚、原Worker发布/GET成功v2/终态重放不复活及原发布/wheel通过。无Migration/权限/依赖变；当前Windows尚未挂提交，正式材料/全Owner/写If-Match/浏览器/完整包/Gate待；下一仅写模式装配。

- 2026-09-27/JOB-01-A03任务详情接Windows两显式platform工厂，原License/Auth/Project/Audit Owner，不加测试回退；1150无失败/2跳过、真实PG-ASGI状态版本/结果/安全隔离/读不写/默认login关闭、构造错误和实际缺正式信任拒绝半启动，旧导出下载/原发布/wheel通过。无本轮Migration/依赖/权限变，非正式供给/监听进程/浏览器/全Owner/完整发行证明；下一公开Audit提交。

- 2026-09-27/JOB-01-A02-P02可选项目/admin GET、安全JobView及实际强vN/no-store，默认404/未知进度错误null；1150无失败/2跳过，真实隔离PG-ASGI原链8成功/13拒绝/六业务表无写，状态版本/结果引用/条件请求不绕撤权及原发布/wheel通过。无本轮Migration/依赖，未接Windows运行组合/其他Owner/写If-Match/浏览器/完整包/Gate；下一A03装配。

- 2026-09-27/JOB-01-A02-P01核对冻结强v<version>要求，先CR-JOB-002再0043/ORM/DTO；数据库统一业务变化加版本、心跳稳定、手改/溢出拒绝。1145无失败/2跳过，真实空/有数据up/down/up旧业务保留、领取/续租/发布及读取/提交确认/混排/耗尽安全收尾回归/wheel通过。无生产迁移/公开GET/If-Match/完整发行证明；升级备份停机、离线降级回旧代码并使旧ETag失效，下一完整JobView/GET。

- 2026-09-27/JOB-01-A01按CR-JOB-001新增只读事实/Service/显式Owner原源绑定与Project GET策略，11新unit/1143无失败/2跳过；真实双Scope任务待执行/运行中/成功原结果与角色/actor/项目/停用/来源错误拒绝六业务表无写，原发布回归通过。仅内部Audit Owner，HTTP/完整JobView/ETag/其他Owner/正式包未完成；无Migration/API/依赖，回滚撤新只读接线保旧路径。下一A02合同前置。

- 2026-09-27/P06-P13-P08核对真实证据与当前源码，有限调度隔离验收矩阵收口，更新CR/运行说明但整体CR/Gate不关闭。本轮仅文档不重跑代码测试；发现通用JobView/GET未实现、Audit内部submit尚无POST、Job无用户资源版本，先任务详情与显式Owner安全策略，写If-Match另追溯设计，不以fencing冒充。无Schema/API/代码/依赖变化，完整交付仍待。

- 2026-09-27/P06-P13-P07保留最近坏源cursor、末尾/32动作回绕，1132无失败/2跳过；真实双Scope新优先队首在31原任务完成后领取，各41健康完成/坏技术全行不变/STOPPED；混排91→25步、78→12拒绝，旧末尾回绕/发布与开发wheel通过。仅固定数据调度改善，非吞吐/无限公平/正式License/完整包PASS，无Migration/API/依赖；CR/Gate保留，下一验收收口后HTTP前置。

- 2026-09-27/P06-P13-P06两轮真实混合持续Loop各12健康任务+4坏priority+1到期第三代坏source，健康全发布/坏技术行不动/true STOPPED，原source恢复后可发布/安全收尾/lost-ack/字节/旧发布通过。Audit UPDATE实际P0001/六表无写，未证明真实源损坏修复。每轮91steps/78拒绝暴露正常claim清cursor的重扫，性能未验，下一优化回绕；仅验证/文档，无生产/API/Migration变化，完整包/Gate待。

- 2026-09-27/P06-P13-P05新增只读耗尽expiry游标/旧入口保留、Owner原源预检不授终态权，后台明确source拒绝后让Claim优先；1130通过/2跳过、真实双Scope第三代到期坏ref/缺Root/错pair精确reason六表无写拒绝，健康后续发布/坏技术原行不动，恢复合成源后原安全失败/actual lost-ack/旧字节及CLI停止/旧发布/wheel通过。无Migration/API/依赖，长期混排/Acceptance实际矩阵/复杂Lease/完整包/Gate待。

- 2026-09-27/P06-P13-P04真实PG双Scope反向锁序8实际40P01，单次有界重试成功/连续3次上限失败且六表无写，同Loop竞争释放后单Attempt/RELEASED/结果；2实际55P03非死锁/非坏源失败无写后恢复。原发布回归通过，仅验证脚本/文档，unit1125历史保留未重跑，无生产/API/Migration变化。耗尽坏源/Acceptance实际故障/复杂Lease/长期公平/完整包/Gate待。

- 2026-09-27/P06-P13-P03-A02显式后台坏来源隔离，常数cursor/实例互斥/只读拒绝后推进，原入口与对外错误码保留；1125通过/2跳过、真实双Scope坏引用/缺Root/错pair六表无写且后续正常发布/恢复来源后原任务可发布，原确认恢复/Windows真实子进程停止/wheel通过。Acceptance真实矩阵/耗尽坏源/Lease/deadlock/全局公平待，CR-AUD-005/完整包/Gate不关闭，无Migration/API/依赖。

- 2026-09-27/P06-P13-P03-A01先记录后新增scan_next严格技术游标/只锁reservation，3新unit/1119通过（2既有跳过），实际双Scope格式错/零UUID两坏ref跨到正常候选/末尾六表无写，旧admission仍关闭，恢复合成来源后发布/原回归与wheel通过。未接后台，不冒充坏源整体修复；Root/pair/诊断/真实deadlock/完整包/Gate待，无Migration/API/依赖。

- 2026-09-27/P06-P13-P02先登记后增加独立只锁reserve_next/保原无锁peek，Root前SKIP LOCKED；1116通过/2跳过、双Scope实际锁队首后续发布/首无Attempt、两个UOW不同候选六表无写，旧P03竞争/回滚/代际及P06确认恢复/wheel通过。坏来源仍FAIL、新版反向锁序40P01待，CR-AUD-005/完整包/Gate不关闭，无Migration/API/依赖变化。

- 2026-09-27/P06-P13-P01实际PG证明队首竞争55P03及坏payload阻塞正常后续，两失败六表无写，恢复本轮合成来源后双方真实发布/原发布回归通过。功能公平隔离FAIL，CR-AUD-005先登记，下一候选reservation及坏源分类隔离修复，无生产/API/Migration变化，完整包/Gate待。

- 2026-09-27/P06-P12-B02实际CLI/PG18临时Credential/Vault identity六个独立隐藏Windows子进程通过：明确测试License下双Scope发布/文件摘要/AVAILABLE/单Attempt/RELEASED/实际SYSTEM identity；缺真实公钥和idle外部CTRL_BREAK六表无写，active只完成第一任务/第二未领取、下一once完成。原发布回归/1113后端无失败（2既有跳过），临时来源清理，无生产/API/Migration变化，SCM/正式材料/无限阻塞/完整包/Gate待。

- 2026-09-27/P06-P12-B01修复停止桥接竞态：每Step前显式只读Probe正常栈stop，最小handler/原pending排空保留；禁桥线程unit及Probe异常无claim、1113通过/2跳过、恢复长等待外部CTRL_BREAK单次排空与开发wheel通过。无Migration/API/依赖，真实PG子进程/无限阻塞/SCM/完整包/Gate待。

- 2026-09-27/P06-P12-A外部Console可响应合成路径内部通过：严格隔离隐藏Console/限定目标+发送器CTRL_BREAK，idle60停止、active单次排空及handler恢复；1111通过/2既有跳过。首次长阻塞再次领取失败保留，真实PG/文件子进程及停止桥接竞态待P12-B核查，无生产/API/Migration变化，完整包/Gate待。

- 2026-09-27/P06-P11内部通过：保旧License入口、新Worker有界runtime固定信任装配；Windows CLI无秘密参数、--once LIMIT非就绪，Loop/Step/Supervisor全静止锁保护DB关闭，活线程拒绝关闭。1111无失败（2跳过）、临时Credential/真实Vault+PG两Scope合成Window组合发布及缺正式公钥失败关闭/六表无写、CLI边界/wheel通过。正式来源/外部Console/服务/完整包/Gate待，无Migration/API/依赖。

- 2026-09-27/P06-P10内部通过：主线程注册/全局互斥，signal只置标志、桥线程正常Event stop，handler全恢复/失败poison；记录Windows长等待延迟偏差后保poll截止以50ms小段等待。7新unit/1106无失败（2跳过）、独立合成进程SIGINT idle与已知任务排空、PG组合发布回归/wheel通过。外部Console/服务/正式来源/其他平台/完整包/Gate待，无Migration/API/依赖。

- 2026-09-27/P06-P09内部通过：显式有界PG18/current完整Migration head/受控identity启动核验，固定Audit/Jobs实际Repo及同Supervisor，原Project/License/Document owned Port，无自动密钥或资源所有权。1099无失败（2跳过）、真实两Scope完整组合Loop发布/撤权安全失败/stop不写、旧发布/wheel通过；首次连接超时后原PG仍活/ready再验通过，非性能证明。正式来源/CLI信号/服务/完整包/Gate待，无Migration/API/依赖。

- 2026-09-27/P06-P08内部通过：原Step有界/持续run，实例互斥，空闲Event等待可中断，只有actual STOPPED才报停止、上限仅LIMIT；错误不自旋、不清pending/强杀，计数不缓存业务正文。1095无失败（2跳过）、实际双ScopeLoop领取/周期heartbeat/发布/撤权拒绝与原发布回归/wheel通过。实际进程信号/服务组合/未知恢复/完整包/Gate待，无Migration/API/依赖。

- 2026-09-27/P06-P07内部通过：单步实例互斥/交替尝试优先/stop仅停新准入，异常保已知pending，真实静止Reader仅按绑定旧代/前两次期限释放本机pending，不改DB或猜成功。真实双Scope领取/周期heartbeat/发布、空及stop不写与撤权安全FAILED；6新unit/1090无失败（2跳过）及wheel。全局公平/实际timeout综合/loop/完整包/Gate仍待，无Migration/API/依赖。

- 2026-09-27/P06-P06内部通过：commit异常只保本次实际命令/Claim/identity，退出原UOW后新UOW核完整Root/pair/同Worker-fence活代与实际Claim；不走deadlock盲重领、不猜STALE。真实双Scope提交前回滚和commit后故障恢复、六表无写/错Worker期限代际终态拒绝、正文仍实时授权，1084无失败（2跳过）/wheel通过。跨进程未知命令/后台loop/完整包/Gate待，无Migration/API/依赖。

- 2026-09-27/P06-P05内部通过：固定Owner/type/current第三代到期一致技术事实无锁只取一个hint，前后identity；候选不授修改权，原安全Owner最终重验。真实两Scope六表只读/收尾/commit后确认故障核源恢复，1081无失败（2跳过）及wheel通过。扫描公平性/并发/坏源隔离/领取确认/循环/完整包/Gate待，无Migration/API/依赖。

- 2026-09-27/P06-P04内部通过：当前第三代真实过期才同UOW最小SYSTEM审计/FAILED Job/EXPIRED Lease/固定Attempt码；真实两Scope故障回滚、撤权仍正文拒绝、commit后确认故障核源恢复及旧字节保留。1075无失败（2跳过）、旧执行器/发布/wheel通过；无Migration/API/依赖，扫描/领取确认恢复/循环/完整包/Gate待。

- 2026-09-27/P06-P03专属领取准入内部通过：无锁hint→原Root/pair→actual eligible/current lease/identity/静止锁，专属Owner不混领；真实两Scope发布、retry到期、过期三代/第4次无写、独立Supervisor并发与故障回滚。1067无失败（2环境跳过）、旧发布/wheel通过；无Migration/API/依赖，耗尽审计/确认恢复/主循环/整体包/Gate待。

- 2026-09-27/P06-P02单命令执行器内部通过：同真实Supervisor/current identity/原facts，成功-终止-取消-retry及真实原源确认，四类commit后确认故障和六表无写重放、执行中真实取消/撤权不回写成功。1060无失败（2环境跳过）、旧发布/wheel通过；无Migration/API/依赖，claim/主循环/CLI/整体包/Gate待。

- 2026-09-27/P06-P01执行器状态事实前置内部通过：实际原pair/Worker-fence/Attempt-Lease/current Job与DB clock、当前/历史明确，内部Reader前后identity/同Supervisor静止，六表无写；真实状态与撤权仍业务拒绝、错绑定拒绝。1047无失败（2环境跳过）、旧发布/wheel通过；无Migration/API/依赖，hint不是终态receipt，执行器接线/整体包/Gate待。

- 2026-09-27/P05-P02重试提交确认丢失核验内部通过：实际历史Worker/fence/RELEASED Lease/Attempt/期限和唯一执行窗口SYSTEM源、当前权限/identity，只读八表无写；真实下一代claim及最终FAILED旧收据相同，缺重复源/错绑定/权限拒绝。1042无失败（2环境跳过）、旧发布/wheel通过；无Migration/API/依赖，主执行接线/整体包/Gate待。

- 2026-09-27/P04-P03-P05固定重试Owner内部通过：当前业务权限前后有效、同Supervisor静止、受控identity与实际pair/活代，最小SYSTEM Audit同事务；真实5/15秒两Scope、新代重capture/render三新fileId旧字节保留、第三次FAILED与故障回滚。1037无失败（2环境跳过）、旧发布/wheel通过；无Migration/API/依赖，确认丢失/主循环/整体包/Gate待。

- 2026-09-27/P04-P04-P05取消确认丢失只读核验内部通过：实际PG双Scope活期ack与过期恢复真正commit后故障，完整首USER源/当前Job-Lease-Attempt/唯一SYSTEM完成源和identity，不猜STALE；多次八表无写、错绑定/类型/缺重复源拒绝。1031无失败（2环境跳过）、旧发布/wheel通过；无Migration/API/依赖，retry/主循环/整体包/Gate待。

- 2026-09-27/P04-P04-P04严格当前代到期取消恢复内部通过：实际DB期限、首USER源、受控SystemActor与同事务SYSTEM恢复Audit+Job CANCELLED/Lease EXPIRED/Attempt JOB_CANCELLED，写后故障回滚，首历史/字节/结果保留。1025无失败（2环境跳过）、旧发布/wheel通过；无Schema/API/依赖，不断言OS强杀，确认丢失/主循环/整体包/Gate仍待。

- P04-P04-P03活代取消安全Owner通过：实际首申请USER来源、当前SystemActor、同UOW最小取消SYSTEM Audit+Job/Lease/Attempt，撤User与License仍不允业务；首历史/字节保留，所有写后/identity故障回滚，错绑定/成功/已取消/缺来源/实际到期拒绝。1021无失败（2环境跳过）、旧发布/wheel成功；无Schema/API/依赖，到期恢复/确认丢失/接线待，整体包/Gate未完成。

- P04-P04-P02已验证实际Root/当前权限、首申请USER Audit与Job/收据原子、同key并发和后续状态漂移不改变首次响应，新key检查不覆盖首历史；裸技术取消拒绝。1017无失败（2环境跳过）、旧发布/wheel成功；无Schema/API/依赖，后台系统确认/到期恢复/HTTP未接线，整体包/Gate未完成。

- P04-P04-P01按冻结API03补创建者或当前PM取消权限；真实Session/CSRF/当前member-role/License两Scope矩阵通过，Admin无Project旁路，归档只停止权限，九表无写。1012无失败（2环境跳过）、原发布/wheel成功；没有取消状态/Audit写或HTTP，Owner首申请来源/幂等仍待，无Schema/API/依赖，整体包/Gate未完成。

- P04-P03-P03完整失败原源只读证明通过：真正commit后确认丢失按当前Job/RELEASED Lease/Attempt与唯一SYSTEM Audit返回；八表反复无写，单一FAILED/错缺重复审计/错代绑定/成功拒绝。1008无失败（2环境跳过）、原终止/发布/wheel成功；无Migration/API/依赖，取消/retry/执行器仍待，整体包/Gate未完成。

- P04-P03-P02 CR-AUD-004/ADR011安全终止Owner已内部验证；真实撤权仍禁业务但允许当前活代最小SYSTEM失败审计同事务，Audit/技术转换写后及后验identity故障回滚，活心跳/旧代/成功/取消/过期拒改。1004无失败（2环境跳过）、wheel成功；无Schema/API/依赖，未接执行器/取消/retry/确认丢失，正式包/Gate待。

- P04-P03-P01 Jobs caller-UOW失败技术Port通过；真实PG双Scope失败/限次retry/接管拒旧代、终态取消过期拒改与真实Audit后置故障整体回滚。998无失败（2环境跳过）、开发wheel成功；CR-AUD-004已先登记，安全终止Owner政策尚未实施，无Schema/API/依赖，正式包/Gate待。

- P03-A07-P04-P02 actual bounded UOW/受权周期/单次原源分类与完整流程通过，双Scope新command空/260成功、原结果13表重放无写、stage-only同file恢复/未登记旧字节拒绝保原/真实commit确认丢失原源返回。993无失败（2环境跳过），旧发布/wheel成功；无Schema/API/依赖，失败Owner/主循环/重启/正式材料/整体包未完成，下一项失败取消政策前置核查。

- P03-A07-P04-P01新增opt-in Worker专用PG18 LOCAL/池连接限制，普通API默认保持。实际慢SQL前Audit回滚、总事务终止/恢复连接、池满超时及真User锁下周期心跳退出实际释放槽PASS；982无失败（2环境跳过），原发布/wheel成功。无Schema/API/依赖，不声称全网络截止/生产停机；下一项单次Worker协调，正式包/Gate待。

- P03-A07-P03进程内有界周期协调真线程/停止超时保容量/故障传播PASS，真实PG两Scope短租约跨人为物理返回延迟成功、成功后心跳STALE不改结果、撤权取消周期停止。978无失败（2环境跳过），原发布/wheel成功；无Schema/API/依赖，不宣称性能或Worker主循环。下一项单次生命周期/DB有界等待核查，正式包/Gate仍待。

- P03-A07-P02 Audit原源/当前权限同UOW心跳与续租后授权/期限重核PASS；真实User/PM/部署角色/许可撤权、误绑/终态取消到期/接管拒旧代、renew写后故障与后验License回滚，13表源历史无写。973无失败（2环境跳过），原发布/wheel通过；无Migration/API/依赖，仅短事务不冒充周期运行。下一项P03有界心跳协调，正式包/Gate仍待。

- P03-A07-P01补独立Jobs caller-UOW续租，原checkpoint只读/通用Service不改；真实PG两Scope一致期限/并发/后置失败回滚、取消/实际到期与真实接管旧代拒绝新代续期PASS。968无失败（2环境跳过），原发布/wheel成功；无Schema/API/依赖，不宣称业务授权或调度完成。下一项P02 Audit原源/当前权限短事务心跳，正式包/Gate仍待。

- P03-A06-P03将四GET装入Windows两显式平台模式，实际PG已发布来源/完整文件/当前Session与Scope/许可/坏文件验证、三装配故障不发布dispose通过；963无失败（2环境跳过），旧WindowsAudit/上传Finalize和原子发布/wheel成功。default/login-only/POST404；正式材料/账户/三平台/代理/性能与完整包待，下一项Worker协调/心跳核查。

- P03-A06-P02两个opt-in内容GET真实当前Session/完整快照/二次授权、安全附件、有界名额与Response/线程资源Owner通过；prepare/read取消不提前释放活跃工作，start/body失败/未启动生成器取消close复用实测。962无失败（2环境跳过）、实际PG/文件双Scope空/260及撤权/坏文件Audit/旧发布/wheelPASS。无Migration/依赖，默认404，生产组合/代理/性能与正式包仍待。

- P03-A06-P01实施前CR-AUD-003/增量契约保原冻结，两可选结果GET真实当前Session/实际成功源/Scope安全投影PASS；955项无失败（2环境跳过），真实PG双Scope/权限/无写与原子发布回归/wheel成功。无Migration/依赖，默认404，内容响应/断连取消/P03生产组合尚待，不宣称完整包或Gate通过。

- P03-A05实际当前Session/Scope访问成功来源与UOW外完整私有快照、二次授权、坏文件受权最小Audit通过；951项无失败，Storage128MiB物理边界/普通100MB保持与旧下载/恢复发布回归PASS。无HTTP/Migration/依赖，下一项增量结果/下载HTTP契约与生命周期；正式材料/三平台/Gate/完整包未完成。

- P03-A04-P04真实来源command-only恢复/内部成功重放，当前权限/原代Lease或真实Job成功来源→全Hash→再次授权；三形状恢复、并发重放无写、确认丢失/坏缺来源/撤权取消过期拒绝与接管原capture新file保旧final通过。945项无失败，完整发布/旧Jobs/File回归及wheel成功。中断模拟、HTTP/当前Session内容访问/心跳/正式账户/三平台及完整包仍待；下一项P03-A05。

- P03-A04-P03实际原子发布成功，元数据/发布审计/结果/Job单UOW及四写后故障回滚、撤权取消到期/失身份/实际取消两锁顺序通过；939项无失败、三真实回归/开发wheel成功。文件Hash/提升不持DB事务，失败final仍私有/STAGED，尚无受控恢复/授权成功重放/HTTP/心跳；下一项P04，不标可用完整包/Gate。

- 原子发布核查受控SystemActor实际来源缺失，按Skill停止受影响编码，实施前登记CR-AUT-004并完成独立AUT-04-A01只读来源/临时Vault恢复；无User/角色/Schema/HTTP改变。934项无失败；下一项恢复实际原子发布并使用公开SystemActorPort，正式账户供给仍属Release材料，不把临时身份当生产验收。

- P03-A04-P02真实受理/固定capture/当前权限/Lease/plan到128页源与私有暂存文件，所有write/fsync/hash不持UOW，完整尾验及页间撤权/取消/到期/故障私有、新代独立file通过；930项无失败。尚无metadata/final/结果/Job成功/发布Audit，下一项全链路原子发布，不能宣称交付。

- P03-A04-P01 Jobs caller-UOW完成原pair/完整当前Lease→技术终态、真实双Scope/并发/取消两锁顺序/检查后到期与接管/不自提交及caller真实Audit后故障回滚通过；926项无失败。Export/权限/成果File/SystemActor未接，合成marker不能证明发布；下一项实际有界文件Worker渲染。

- P03-A03-P04 own结果record/get实际来源/规范bytes重核、原结果重放/真并发单次变化/后置Audit+结果整UOW回滚通过；919项无失败，0042/实际Worker计划/renderer/文件元数据回归PASS。跨Owner Job/File/Lease/SystemActor仍合成，不冒充真正发布，下一项Jobs caller-UOW完成Port。

- P03-A03-P03/0042不可变唯一结果，own计划/发布Audit绑定、完整规范manifest重建字节/SHA256、空与非空规则及真实历史down写锁通过；914项无失败，计划/旧文件元数据回归PASS。Job/File/SystemActor合成，内存清单不是正式Worker/物理文件/原子发布证明，下一项own结果Repository。

- P03-A03-P02在真实受理/claim/固定capture/当前权限/Lease下登记或读回原代计划；双Scope/真并发、新代独立file、实际撤权/取消/到期/写后故障和40P01限次整UOW恢复通过；912项无失败。无文件/成功状态，下一项不可变结果Schema，完整交付仍待。

- P03-A03-P01/0041不可变渲染计划源绑定、单Job/token单file、新代次独立文件及真并发/历史down写锁拒绝通过；904项无失败。合成Job/Lease refs不能证明真正Worker，下一项P02实际公共Port/当前权限登记。

- P03-A02-P02完成Document owned caller-UOW元数据，原内容/归属/首次事件重核、并发单次变化及共享锁、caller真实Audit故障全回滚；902项通过。合成Export不冒充真Root/权限/Lease，AVAILABLE不是成功结果，下一项持久尝试/结果Schema。

- P03-A02-P01完成独立generated/audit存储，bounded sink/private partial/flush/fsync/Hash读回/不覆盖及真实linked/final恢复、普通扫描隔离；14项新增/897后端通过。只有物理原语，元数据/真正Worker权限与Lease/发布/下载待，不宣称文件提升即交付。

- P03-A01/0040完成内部FileObject用途/归属，旧DOCUMENT完整保留；同PROJECT普通Version/Upload误绑与旧通用状态/发布拒绝，专用身份/内容/状态和delete/truncate历史保护，实际down竞争表锁/历史拒绝通过。合成owner不冒充真实Export/Lease/文件，P03-A02公共Port/存储待。

- P03先记录CR-AUD-002/ADR010：内部FileObject用途/DEPLOYMENT归属、Audit自有尝试与唯一结果，普通文档/业务Output范围不改；文件I/O与短事务数据库发布分开，权限/Lease/取消重核，按实际来源恢复。仅变更设计，无Schema/生产代码/HTTP验收，下一项P03-A01。

- A04-P02真实入口探测确认DEPLOYMENT locators/PublishFile拒绝，FileObject ORM仅GLOBAL/PROJECT；普通OutputArtifact依赖PROJECT/Plugin/DocumentVersion不可伪造。核查完成不代表发布可用，下一项先CR。不改Schema/API/生产数据，4项只读探测通过；详见对应进度记录。

- A04-P01固定member源显式安全列接canonical JSONL/独立manifest，逐条Scope/全筛选/位置/完整成员hash重核，写入大小/短写/源失败不返回成功；source关闭、sink由Owner管理。真实两Scope内存字节/新事件排除/无hint与数据库无写通过，未宣称落盘/Artifact/权限发布或空间性能。既有发布仅GLOBAL/PROJECT，DEPLOYMENT归属留P02核查不重标绕过。

- A06-A03将实际提交/原acceptance/Queue pair/claim及当前权限/Lease接真实capture；User-first锁序与无锁peek后Root精确重核，结束前再授权/验期限。故障/真实取消/到期接管全回滚、真并发单seal/新事件及generation原集合、PG40P01限次恢复通过。License合成，文件/公开HTTP尚待，不宣称完整Worker交付。

- A02-P02-A02接实际Jobs取消/当前Worker协作确认/到期恢复，原pair与首信息固定、真并发单次变化/故障回滚/取消与finish两个锁竞争顺序PASS。合成发布marker仅数据库证明，Owner授权/receipt/Audit/Artifact尚未接入，完整Worker/公开取消待。

- 核查取消申请人/原因在Job实现缺失，先登记CR-JOB-002，0039恢复首次申请人/原因/时点元数据；旧NULL无回填、首信息与技术身份固定、不可删除/复活/含历史down拒绝及实际表锁PASS。合成转换不冒充真正取消，A02命令/确认/恢复仍待，POST关闭。

- A06-A02-P01新增Jobs caller-UOW只检查租约公共入口，实际Job→Lease→Attempt锁及一致性/未到期核验，不续租、不完成或commit。真实接管/旧Worker及三事实锁/业务无写通过；取消状态仅合成拒绝，真实取消流程留P02，完整Worker/交付待。

- A06-A01新增Auth owned当前enabled User/部署角色锁及Audit每stage当前许可/PM成员部门权限Port，实际撤权/范围/归档维护/锁持有与业务无写PASS。注销Session不伪装异步取消；坐标不是Root/Lease证明。现有Job无capture/render只检查Lease公共Port或取消行为，留A02，不声明完整Worker或文件发布通过。

- A05-A03-P02 完整内部原子受理与真实 Job/Audit 引用通过；新 trace 重放保持首次结果，缺失/替换/旧无受理历史拒绝且不修复。真实死锁整 UOW 最多三次、每次重新授权，耗尽无残留。License合成，Worker/HTTP/文件交付仍待；详见对应进度记录。

- A03核查当前Job不能独立证明首次响应，先修订CR-AUD-001并实施0038受理历史；固定Job/Event/Audit Ref，精确Root源绑定、不可变/唯一/旧行无回填/down保护实测PASS。合成Job refs未冒充实际关联，完整原子命令留P02，POST仍关闭。

- AUD-03-A05-A02新增Jobs owned Audit专用最小ExportRef/政策enqueue公共Port，真实同Export并发首次pair/原Ref、双Scope/故障回滚/终态不复活/缺边篡改拒绝PASS。Queue不读Audit内部表、不自鉴权或commit；合成ExportRef不冒充根存在，A03完整受权原子仍待，POST关闭。

- AUD-03-A05-A01接实际Session/CSRF/License与PM/Admin提交授权，仅AUDIT_PROJECT_EXPORT write归档维护例外。真实五事实锁/撤权/范围/显式PM管理员与业务无写实测PASS（License合成）。结果metadata不是跨事务凭据，Job公共Port/receipt/Audit/Worker仍待，POST关闭。

- AUD-03-A04-P03已用真实单statement固定原Scope/Spec完整集合，同capture时点记录并封口；迟提交/回填/新事件不进入旧集合，真实等待重试返回同seal，故障/小上限超限整UOW回滚实测PASS。存储入口不自鉴权/commit/授予权限，POST未开放，A05/A06真实权限/Job/Lease及交付待。

- AUD-03-A04-P02/CR-AUD-001新增0037三表，实际源Scope/筛选、根锁/同事务封口、数量/顺序/摘要、并发等待后拒追加及历史down保护实测PASS；旧Audit/Job不变。Schema不能证明选全合法事件，P03单statement完整capture仍待，POST保持关闭。

- AUD-03-A04-P01已在实施前登记CR-AUD-001，固定CAPTURE-MEMBERSHIP-V1域分隔/UTC微秒/降序/空集合规范及纯领域摘要，拒绝重复/逆序/腐损/源失败截断；O(n)UUID去重内存未作性能承诺。0037尚未实施，摘要不是权限/实际来源/封口证明，POST仍关闭。

- AUD-03-A03 固定内部导出Scope/明确窗口/筛选/用途code和版本化JSONL投影指纹，不接受cursor/路径/Secret；Worker坐标不是权限证明，实际当前Actor事实/归档维护策略仍待。纯合同unit PASS，无新增真实权限或持久化，POST未开放。

- AUD-03-A02 已按实施前CR-JOB-001补齐0036 Job/Outbox DEPLOYMENT范围，旧GLOBAL/PROJECT保留，down先双表锁并拒绝任何部署历史，离线down关闭。真实空/有数据与并发/租约/投递/Parse范围回归PASS，无生产迁移，不代表导出或Gate完成。

- AUD-03-A01 真实head0035临时库证实DEPLOYMENT Job/Outbox被当前scope CHECK拒绝，与冻结DM-04/API-03不一致；不重标GLOBAL绕过。记录导出当前受权、真正seal snapshot、幂等/Job/fencing、Artifact安全交付/再授权和迁移验收分项；POST保持关闭，下一项先CR-JOB-001。

- AUD-02-A05 将四个审计GET装入Windows两种显式平台，独立Audit key缺失拒启且dispose；default/login-only404。真实数据库Session/PM/Admin/Scope双页、许可拒绝与14项受影响集成回归PASS。正式账户及发行信任锚未供给，非生产/Gate验收。

- AUD-02-A04 新增audit-list-cursor-v1独立Windows当前账户只读入口，缺失/长度错误/provider异常统一失败关闭，不自动生成或复用其他key。唯一临时Vault引用丢失/恢复旧游标实测PASS并清理；正式账户供给/离线保管/平台组合待完成。

- AUD-02-A03-P02 新增四个冻结审计GET的可选Router、安全筛选/默认24h或显式最大31天/同事务签名分页/投影/no-store；真实PostgreSQL Scope/无Admin项目旁路/撤销Session/License拒绝与读无写PASS。普通默认404，正式专用key与Windows组合、导出仍待。

- AUD-02-A03-P01 接入受权同事务搜索解析Port，真实Session/Scope授权后才使用实际Actor解码；错误或改变筛选/page_size不触发查询，有效签名窗口供查询和响应复用。内部/隔离数据库PASS，默认生产仍无审计HTTP，专用密钥来源/导出未完成。

- AUD-02-A02 新增独立 HMAC 审计游标，绑定实际 Actor/Session/Scope/全查询/UTC窗口与稳定位置；明确日期严格匹配，仅未显式日期可恢复原窗口。真实数据库双页和当前撤权拒绝PASS。签名不是授权/加密/MVCC快照；公开GET、正式专用密钥来源与导出未完成。

- RVW-02-A10核查Review仍只有Owner协议、无真实固定版本/身份锁/消费实现，公开前置BLOCKED；转Phase2独立AUD-02-A01。已接审计当前Session/PM或Admin实际授权、同事务private能力与Scope/安全投影/范围/排序/分页/筛选核对。项目归档可读历史，撤权/Session失效拒绝；五类授权事实锁与读无写实测PASS，暂无HTTP/导出。

- RVW-02-A09-P02 已接当前Session/CSRF/Project角色、assigned reviewer或PM、不可变事件receipt与当前历史版本Owner重放权限；新命令完整结构/Audit/receipt同事务，消费/审计/收据失败全回滚；真实40P01整UOW限次恢复。无实际业务Owner/客户资格或正式License信任源，不挂HTTP、不标Gate通过。

- RVW-02-A09-P01 已加入不可变命令事件Ref，用历史决定前缀/完整集合与前轮封口计数还原首次响应，不拿当前终态或根版本替代旧响应；后续新Round不改变旧结果，Scope/非STARTED或COMPLETED命令引用明确。查询不写库；权限/receipt入口与实际Owner仍待。

- RVW-02-A08 新增可信调用方事务决定/撤回完整 owned 写与真实 Audit，前后 Owner 锁核验、终态同事务消费与消费后独立重核；首 RETURN 不释放，撤回保留旧决定和 pending/原因，决定与撤回竞争单终态。故障全回滚含合成消费记录；不自建 UOW/commit/鉴权/receipt，不挂 HTTP。真实 Owner/跨模块锁序/客户批准仍待。

- RVW-02-A07/CR-RVW-002 新增0035事件原因和固定读回，旧NULL保留、中文原因完整、其他事件/空白拒绝、历史不可变；downgrade表排他锁防并发丢失，含原因拒绝down。隔离Schema/关联回归PASS，无实际Owner/受权撤回/公开API。

- RVW-02-A06 已核对冻结 decide 不增加 If-Match 必填、withdraw 保持根 ETag/PM；新增不可变单步交接合同，禁止代理/替换历史/跨轮次/终态再写。Owner 同事务消费才能正式化/解锁，APPROVED 必须重验当前 Sources 和资格。发现 AF-02 reason 在 0034 无持久字段，先登记 CR-RVW-002；迁移/真正业务 Owner/受权命令尚未完成。

- RVW-02-A05-P02 已接真实 Session/CSRF/PM/基础资格与幂等送审内部入口，账户预锁/PM 后才报资格、同事务完整结构/Audit/receipt；原始 Ref 重放不重复送审，当前权限仍重验。实际 40P01 整 UOW 回滚后限次重试成功；不声明所有旧命令无死锁。Owner/License 合成、无公开 HTTP 或实际客户批准。

- RVW-02-A05-P01 已完成可信调用方事务完整 Round owned 持久化与真实 Audit，Owner 准备/两次锁重核、Source 错版本/绑定/审计故障全回滚。服务不创建 UOW/commit/授权/收据；完整受权 start/P02 与实际 Owner 仍待，禁止直接公开。

- RVW-02-A04 已固定送审请求与 Prepared 的 Actor/Project/Review/逻辑主题/policy/Version/Round/完整确认人绑定，来源 Scope/唯一/UTC/时序校验；Owner prepare 和实际身份锁 assert 独立，禁止 DTO/UUID/True 代替事实。无真实 Owner 实现，完整 start 尚未完成。

- RVW-02-A02/A03 已完成送审前置及真实账户/项目基础资格服务，先 Auth 共享锁再当前成员/部门锁读，暂停/移除/未来生效/停用/跨项目/角色不符拒绝。返回必要事实不授予具体 Subject 评审权；完整 Session/CSRF/start/Owner 身份锁/政策和跨模块并发仍待。

- RVW-01-A06/A07 已完成创建前置和内部 PM 命令：DRAFT 根/同事务 Audit/收据，重放不可变原始创建 Ref，未知 Owner 拒绝、归档/撤权不旁路、审计和收据失败全回滚；没有 Round/真实送审锁/客户批准或 HTTP。输入固定版本仅参加创建校验/指纹，实际送审仍需独立 Snapshot/Owner 重验。

- RVW-01-A04/A05 已记录两层授权设计并实现内部 PROJECT 读服务，真实 Session/Project 锁读和四角色矩阵通过；固定旧版独立 Owner 权限必须通过后才加载意见/依据，缺 Owner 默认拒绝。Subject/License 协议合成、无公开接口/实际客户批准/Gate 证明；真实 Owner 和跨模块身份锁仍待。

- RVW-01-A03 已提供内部调用方事务 Scope 查询和固定 Round/Subject Snapshot，返回当前身份与独立历史进度，保持 Review→Round 共享锁，拒绝缺子记录/版本异常；后续来源变更不改历史观测。无公开接口/授权服务/新迁移，不能将 APPROVED 或观测 ELIGIBLE 当实际批准/Gate 证明。

- RVW-01-A02/0034 已落地八表、非空 Global Scope 父键、完整集合汇总/锁与事件原子、不可变/封口、Sources 当时事实与并发保护，隔离 Schema PASS。没有真实 Subject Owner/客户资格/审批命令；历史来源观测和合成 APPROVED 不能冒充现在批准或真实业务锁。

- RVW-01-A01/CR-RVW-001 已登记 Review 历史/身份锁八表设计；RVW-02-A01 已实现所有处理人完成才汇总的不可变多人进度，首条 RETURN 不提前终结/释放锁，撤回保留旧决定和 pending。仅纯领域，Review Schema/实际 Owner/客户批准和公开接口尚未完成。

- WFL-02-A01-P04/P05 已记录关联设计并实施 0033，旧 Gate 原值保持、新行必须关联已提交当前 Checklist 记录，固定 typed refs 精确一致且重观测不回退，隔离 Schema PASS。真实 Review/例外/Owner 与受权 Gate 命令仍缺，先进入统一 Review 前置，不以合成 APPROVED 放行业务。

- WFL-01-A05-P04 已实现内部事务当前记录/固定依据查询，核对完整历史链与当前 Item 结果/版本，缺链旧 PASS 和过时值拒绝，保持 Workflow→Item 锁至调用方结束。后续 Evidence 变化不重写历史；查询结果仍需真实受权 Owner 重验，未开放 Checklist 写/Gate 路由。

- WFL-01-A05-P03/CR-WFL-004 已新增两表/0032 与初次/更正可信链、同事务两个版本/当前投影、BLOCKED 保持、观测与不可改写保护，隔离合成 Schema PASS。实际 Review/Owner/受权写命令/Gate 固定记录关联尚缺，不把旧无链 PASS 或合成 APPROVED 当业务事实。

- WFL-01-A05-P02 已实现不可变首次/更正纯 Domain 快照，保留原结果及依据，两个版本序列分离；FAIL 可表示资料不足，正向结果需依据形状。无数据库/公开写路径，UUID 或构造成功不等于真实 Scope/批准/Gate；CR-WFL-004 持久层与 Owner 前置仍待。

- WFL-01-A05-P01 登记 CR-WFL-004：新增 Checklist owned 记录/依据链，不覆盖旧结果或 Gate 快照；首次与更正受控、Item/Workflow 版本分离、旧非初态无链不回填。尚无记录 Schema/命令，真实 Owner/Gate 未验。

- WFL-02-A01-P03/CR-WFL-003 已落地三表历史/0031 和提交完整性、当前状态原子核对、不可变及提交后封口、Evidence 观测事实保护，隔离结构验收 PASS。真实 Review/例外/Checklist 历史与写服务未具备，Schema 可存合成 APPROVED 不等于客户批准，不作为 Gate/发行通过。

- WFL-02-A01-P02 记录 CR-WFL-003/三表设计：Evidence 可变 eligibility 要保存观测事实，Review Schema 当前缺失不能伪造 FK/批准。新增 owned typed refs 与事务内子项追加方案，0031 尚未实施；实际迁移、Checklist/START/完成与 Gate/写服务仍待，不宣称 Workflow 完成。

- WFL-02-A01-P01 已完成不可变成功相邻迁移/完整 GateItemSnapshot 形状与纯领域测试，WAIVED 独立依据不改写 PASS；构造成功不是 Gate 证明。历史数据库/Owner 同事务事实/START/完成/写 API 未实现，不凭 UUID 认定批准。

- WFL-01-A04-P03 已将只读 GET 接入 Windows 两种显式平台模式并验证真实 Session/隔离 PostgreSQL 授权及缺合成信任源失败关闭。默认/仅登录及 Workflow 写路径保持 404；正式信任源/历史/实际 Gate 尚未完成，不代表生产发行通过。

- WFL-01-A04-P02 已提供可选 WORKFLOW_GET，真实 Session/PostgreSQL 合成 HTTP 验证 PASS。默认与 Windows 显式组合仍未挂载；仅状态只读，不等于 Gate/启动/推进完成，错误项目投影不会返回。
- WFL-01-A04-P01 内部读服务从一条 SQL 快照产生完整固定 V1 状态投影，缺实例不写库。WORKFLOW_GET 为四角色只读并保持当前 Project/成员/部门事实锁，撤权并发已验证；HTTP/性能/真实 Gate 未验，不将存储状态当客户确认依据。
- WFL-01-A03-P05 提供内部 PM 受权初始化：使用 WORKFLOW_START 对应管理权限准备 NOT_STARTED 结构，不执行 start 或自动回填。真实 Session/Project/CSRF/角色拒绝、合成 License/并发/审计回滚已验证；无公开 HTTP/CLI，真实发行信任源与完整 Gate 未具备。
- WFL-01-A03-P04 已在 Windows 显式平台新建 Project 事务装配 Workflow 初始化，真实 Session/Admin/CSRF 与合成 License 拒绝、并发幂等、初始化/Audit 故障全链回滚已验证。已有 Project 和不装配 Port 的旧隔离内部调用仍未补齐，不能视为 Workflow 全链 PASS。
- WFL-01-A03-P03 已完成供授权应用调用的内部同事务初始化（NOT_STARTED/PENDING），新实例一次 Audit，重复/并发收敛并不重置已有进度。入口自身不承担用户授权/License，尚未连接 Project 创建或既有项目回填；不能以合成内部调用方验收判真实权限/生产路径 PASS。
- WFL-01-A03-P02 按 CR-WFL-002 落地四表 ORM/0030 及 deferred 结构保护，隔离 PostgreSQL 合成验证 PASS。当前没有生产 Workflow 实例或初始化接线，真实 Gate/历史/Audit/权限未具备；结构可表示通过状态不代表业务已批准，写 API 继续关闭。
- WFL-01-A03-P01 登记 CR-WFL-002：当前阶段可 ACTIVE/BLOCKED 唯一，终态保留最后阶段指针；四表初始化和提交完整性设计已记录，数据库尚未实施。既有项目不自动推定进度，最终完成 HTTP 不猜测；0030 尚不存在，下一任务执行真实 Schema 验收。
- WFL-01-A02-P01 只校验 ACTIVE Workflow 的相邻目标、非归档及乐观锁一致，返回值不是 Gate PASS，也不创建 Transition。状态枚举与冻结模型一致；Gate、授权、同事务历史与失败 Audit 留待应用层，BLOCKED 恢复/最终完成需独立定义，不能引入虚构终点 key。
- WFL-01-A01-P02 按 CR-WFL-001 发布固定六阶段配置 V1 与策略来源文档；十二项均必需，配置不含项目状态或客户确认。尚无 Gate evaluator/Owner Port 接线，不能凭策略引用判实际 PASS，未创建 Workflow 实例。后续修改须发布新定义版本，不覆盖 V1。
- 分支：`feature/license-runtime-guard`
- TRC-01-A05-P02 内部 PROJECT TraceLink 创建已在 Windows 11/隔离 PostgreSQL 通过真实授权、并发去重、持久幂等、环拒绝和 Audit 回滚；仅 DOC-02 Owner 注册，公开 HTTP 与其他 Owner 仍待，不能视为 TRC-01 整体或 Gate 3 PASS。
- TRC-01-A05-P03 前置核查按 CR-TRC-002 保持通用 Trace POST 不挂载；冻结三字段 ResourceVersionRef 缺各 Owner 的可信 Scope/Project 解析，不能猜测或补未冻结必填字段。转 WFL-01 独立任务。
- WFL-01-A01-P01 仅完成不预设业务清单的版本化阶段/Checklist 定义形状与打包验证；API2-R04 的正式 Stage/Gate 配置仍待设计，不能据此启动项目 Workflow 或判 Gate PASS。
- 最近功能检查点：LIC-02-A05 已实现仅内部管理员受控重验证；拒绝状态可在活动安装文档、真实验签、机器/有效期/可信时间全部通过后恢复 VALID，失败则保持拒绝并记录事件/Audit。公开 HTTP 挂载、生产公钥/选定 MAC/可信时间密钥来源与初始化仍未接线，不得对外开放业务。Auth 仍无公开登录或管理 API。
- LIC-03-A03 编码前发现任务名称仅为上一任务暂定，未有批准的验收定义；冻结架构明确把 SecretKeyProvider 的 Windows/Linux 实现与密钥恢复留给 Release 安全设计，当前仅有未落地的 Secret 访问 Port。生产可信来源不能以明文环境变量/普通 YAML/临时文件替代，受影响的装配工作暂停，见 `docs/progress/lic-03-a03-precheck.md`。
- 用户已选择方案 A 并作出持续执行授权：LIC-03-A03 现只做一次性受控初态初始化，生产信任源留待 PLT-02/Release；执行纪律差异见 `CR-EXEC-001`。上条“暂停”记录作为历史检查结论保留，不代表当前仍待用户决定。
- LIC-03-A03 已按方案 A PASS；初始化不包含生产信任源，不能放行业务。下项推进 PLT-02 SecretRecord 数据层；具体跨平台密钥保护与恢复仍待 Release 安全验证。
- PLT-02-A01 已完成密文版本持久层与迁移；生产 Secret Store 仍需写命令、权限/审计、解密适配及跨平台主密钥方案，不能据此配置真实 API Key。
- PLT-02-A02 已完成只读密文信封适配；使用合成解密器验证消费边界，不代表生产加密/解密已可用。管理元数据、正式写命令与跨平台主密钥仍待后续任务。
- PLT-02-A03 已完成管理员元数据内部查询与脱敏投影；公开 GET、生产 License/Secret 装配和写命令未接线。
- PLT-02-A04 已完成版本化 AES-256-GCM 加解密适配和临时库密文写入验证；生产 Key Provider、正式权限写命令和轮换仍未接线。
- PLT-02-A05 已完成仅内部受控创建/轮换与同事务审计；生产 Key Provider、公开管理 API、停用命令及 License 整体接线仍未完成。
- PLT-02-A06 已完成内部停用并验证停用后受控读取拒绝；公开管理 API 因生产身份/许可/密钥装配与 If-Match/幂等缺口拆至 A07，当前不可开放。
- PLT-02-A07 前置核查未通过，见 `docs/progress/plt-02-a07-precheck.md` 与 CR-PLT-003；该单项公开接线停留在 404，项目转先完成 AUT-03 等前置，不将 A07 标为 PASS。
- PLT-02-A07-P04-A01 已完成可选挂载的 Secret 详情只读 HTTP 与安全投影/ETag 合成契约；生产管理路由尚未装配，列表/写接口和真实信任锚仍待完成，A07 整体未 PASS。
- PLT-02-A07-P04-A02 已完成可选 Secret 列表 HTTP/完整性保护游标及 PostgreSQL 同时间戳 keyset 验证；生产游标签名密钥来源/恢复、只读路由装配与写接口仍待完成，A07 整体未 PASS。
- PLT-02-A07-P04-A03 已完成 Windows 独立游标签名密钥安全来源与临时 Vault 备份恢复测试；正式账户供给与生产只读路由装配仍待完成，A07 整体未 PASS。
- PLT-02-A07-P04-A04 已新增 Windows 显式平台组合，仅在正式 License/游标信任源齐备时挂载 Secret 详情/列表；合成失败关闭通过但正式公钥/账户尚缺，不能把 `--platform` 标为生产 PASS，写 API 仍关闭。
- PLT-02-A07-P05-A01 已修正内部轮换版本条件为记录 `lock_version` 并经 PostgreSQL 版本分离/并发验证；公开 If-Match/幂等尚未接线，写路由仍关闭。
- PLT-02-A07-P05-A02 已增加规范强 If-Match 解析并验证 428/400 安全边界；尚无完整写路由或同事务幂等，不能标 Secret 写 API PASS。
- PLT-02-A07-P05-A03 已完成内部 Secret 创建同事务持久幂等，PostgreSQL 顺序/并发/回滚通过；轮换/停用收据与公开 write-only HTTP 仍待完成。
- PLT-02-A07-P05-A04 已完成内部 Secret 轮换/停用持久幂等与 PostgreSQL 同 Key 并发验证；write-only HTTP 和正式生产信任源仍未完成。
- PLT-02-A07-P05-A05 已完成可选 Secret 创建 write-only HTTP 与 PostgreSQL 隔离合成端到端；默认/生产组合仍不挂载写路由，正式信任源和轮换/停用 HTTP 待完成。
- PLT-02-A07-P05-A06 已完成可选 Secret 轮换 write-only HTTP 与 PostgreSQL 隔离合成端到端；默认/生产组合仍不挂载写路由，正式信任源和停用 HTTP 待完成。
- PLT-02-A07-P05-A07 已完成可选 Secret 停用 HTTP 与 PostgreSQL 隔离合成端到端；默认/生产组合仍不挂载写路由，正式信任源待供给，A07 整体未 PASS。
- PLT-02-A07-P05-A08 已新增 Windows 显式写组合，并在 PostgreSQL 临时库完成合成信任源端到端；默认/只读模式保持关闭，正式发行公钥和目标账户密钥尚缺，A07 整体未 PASS。
- PLT-02-A07-P05-A09 正式发行前置核查发现真实签发密钥、口令独立保管/离线备份及目标账户材料缺失；本项保持 BLOCKED_BY_OPERATOR_CEREMONY，不以合成材料替代，转独立 Project 任务。
- PRJ-04-A01 已完成可选 Project 列表/详情 HTTP 的 PostgreSQL 隔离合成端到端；默认/生产组合尚不挂载，PRJ-04 整体未 PASS。
- PRJ-04-A02 已将 Project 列表/详情挂入 Windows 显式平台模式并在 PostgreSQL 临时库完成合成 License/真实 Session 多用户验证；默认模式仍 404，正式信任源与 PRJ-04 整体未 PASS。
- PRJ-04-A03 编码前发现原内部 Project 创建尚无持久幂等，暂停直接开放 POST；已复用 `0015` 收据完成同事务幂等及 PostgreSQL 并发/回滚验证，公开路由与正式信任源仍待。
- PRJ-04-A04 已完成可选 Project 创建 HTTP 与 PostgreSQL 隔离合成端到端；默认/当前生产组合未挂载，正式信任源和 PRJ-04 整体未 PASS。
- PRJ-04-A05 已在 Windows 显式平台组合挂载 Project 创建，并在 PostgreSQL 临时库验证真实 Session/同 Key 重放/管理员与合成 License 拒绝；默认模式仍 404，正式信任源与 PRJ-04 整体未 PASS。
- PRJ-04-A06 已完成可选 Project 名称 PATCH，补齐冻结 ETag 初始版本 `"v0"` 的通用解析；PostgreSQL 临时库验证 HTTP 冲突/隔离/Audit，默认及当前平台组合仍 404，正式信任源与 PRJ-04 整体未 PASS。
- PRJ-04-A07 已在 Windows 显式平台组合挂载 Project 名称 PATCH，并在 PostgreSQL 临时库验证真实 Session/版本冲突/合成 License 拒绝；默认模式仍 404，正式信任源与 PRJ-04 整体未 PASS。
- PRJ-04-A08-P01 已复用 `0015` 收据完成内部归档同事务幂等，临时 PostgreSQL 验证并发同 Key 仅一次状态/Audit/收据及失败回滚；公开归档 HTTP 仍 404。
- PRJ-04-A08-P02 已完成可选归档 POST HTTP，临时 PostgreSQL 验证同 Key 重放仅一次归档/Audit；默认及当前平台组合仍 404，正式信任源未供给。
- PRJ-04-A08-P03 已将归档 POST 挂入 Windows 显式平台并在临时 PostgreSQL 验证真实 Session/重放仅一次 Audit/合成 License 拒绝；默认模式仍 404，正式信任源与 PRJ-04 整体未 PASS。
- PRJ-04-A09-P01 已完成成员列表独立 HMAC cursor 的会话/项目/查询绑定，并修正旧 Secret cursor 测试的随机误报；可选 HTTP 与 Windows 目标账户密钥来源仍待。
- PRJ-04-A09-P02 已完成可选成员历史列表 HTTP 与临时 PostgreSQL 双页/权限/License 验证；默认及当前平台组合仍 404，独立成员 cursor 密钥来源待验。
- PRJ-04-A09-P03 已完成 Windows 当前账户独立成员 cursor 密钥只读入口与测试 Vault 备份恢复；正式账户供给和平台组合仍待。
- PRJ-04-A09-P04 已把成员历史列表挂入 Windows 显式平台，独立密钥缺失拒绝启动；临时 PostgreSQL 真实 Session 双页/权限/License 及既有组合回归通过，正式账户材料未供给。
- PRJ-04-A10-P01 已按 CR-PRJ-002 新增不可变成员创建结果快照和同事务收据，PostgreSQL 并发/回滚/历史响应/迁移验证通过；公开创建 HTTP 尚未接线，下一项 P02。
- PRJ-04-A10-P02 已新增可选成员创建 HTTP，在临时 PostgreSQL 验证真实 Session 同 Key 两次 201 仅一成员/Audit、异载荷/角色/跨项目/License 拒绝；默认与当前 Windows 组合仍 404，下一项 P03。
- PRJ-04-A10-P03 已在 Windows 两种显式平台模式挂载成员创建，临时 PostgreSQL 真实 Session/重放/权限/License 及缺成员 cursor 密钥失败关闭验证通过；默认模式仍 404，正式账户材料未供给。
- PRJ-04-A11-P01 已新增可选成员 PATCH HTTP，在临时 PostgreSQL 验证强 If-Match、ProjectManager/跨项目/最后负责人/License、历史与 Audit 同事务；默认及当前平台模式仍 404，下一项 P02。
- PRJ-04-A11-P02 已在 Windows 两种显式平台模式挂载成员 PATCH，临时 PostgreSQL 真实 Session/版本/权限/License/历史审计及缺成员 cursor 密钥失败关闭验证通过；默认模式仍 404，正式账户材料未供给。
- PRJ-04-A12-P01 已按 CR-PRJ-003 为成员暂停/恢复/移除增加同事务收据与不可变首次结果快照；PostgreSQL 三状态并发/回滚/历史重放/迁移验证通过，公开 HTTP 尚未接线。
- PRJ-04-A12-P02 已增加可选成员暂停/恢复/移除 HTTP，并在 PostgreSQL 临时库验证真实 Session/重放/冲突/跨项目及合成 License 拒绝；默认和当前 Windows 显式平台组合仍 404，正式信任源和 PRJ-04 整体未 PASS。
- PRJ-04-A12-P03 已在 Windows 两种显式平台模式挂载成员状态命令，PostgreSQL 临时库真实 Session/三状态重放/缺信任源失败关闭通过；默认模式仍 404，正式目标账户材料未供给。
- PRJ-04-A13-P01 已增加独立签名部门列表游标，绑定当前 Session/Project/page size/稳定部门位置并拒绝跨资源族；公开 GET 与 Windows 目标账户密钥来源仍待。
- PRJ-04-A13-P02 已新增可选部门列表 GET，PostgreSQL 临时库双页/角色/跨项目/License 拒绝通过，并修正内部许可失败映射；默认与当前 Windows 平台组合仍 404，独立密钥来源待验。
- PRJ-04-A13-P03 已增加 Windows 当前账户独立部门游标 Vault 只读入口，临时引用备份恢复旧游标验证通过；正式目标账户密钥未供给，平台组合仍 404。
- PRJ-04-A13-P04 已把部门列表挂入 Windows 两种显式平台模式，独立密钥缺失拒绝启动；临时 PostgreSQL 双页/跨项目/License 与 8 个受影响集成脚本回归通过，默认模式仍 404，正式账户材料未供给。
- PRJ-04-A14-P01 已按 CR-PRJ-004 增加部门创建不可变首次结果快照和同事务收据，Migration `0018` 及 PostgreSQL 并发/回滚/历史响应/迁移验证通过；公开 POST 尚未接线。
- PRJ-04-A14-P02 已新增可选部门创建 POST，PostgreSQL 临时库真实 Session 同 Key 两次 201 仅一部门/Audit、异载荷/角色/跨项目/License 拒绝；默认与当前 Windows 组合仍 404，下一项 P03。
- PRJ-04-A14-P03 已把部门创建挂入 Windows 两种显式平台模式，临时 PostgreSQL 真实 Session/重放/权限/License 及缺部门 cursor 密钥失败关闭验证通过；默认模式仍 404，正式账户材料未供给。
- AUT-03-A01 仅完成未挂载的可信 Host/Origin 策略；缺失/重复/不匹配失败关闭。限流、凭据、Cookie/CSRF 与公开登录仍待后续任务。
- AUT-03-A02 完成 PostgreSQL 原子登录限流；真实客户端地址可信代理策略和过期桶清理调度未接线，登录仍未公开。
- AUT-03-A03 完成内部登录编排与真实 scrypt/Session 集成；公开 HTTP/Cookie/CSRF、初始管理员和生产装配仍未完成。
- AUT-03-A04 完成可选登录 Router 的 Cookie/CSRF 传输契约；未注入生产依赖时仍 404，不能视作可用登录。
- AUT-03-A05 补齐 SessionView 身份/部署角色并强制显式 Project 授权摘要 Port；项目成员读层未实现，生产 Router 仍未装配。
- AUT-03-A06 提供仅空 User 表的一次性本机初始管理员 CLI；测试库验证成功，但未在真实部署替用户设置密码或创建管理员。
- AUT-03-A07 生产装配前置未满足，按 CR-AUT-002 先建设当前 Phase 2 的 Project 成员事实，未将 A07 记 PASS。
- PRJ-01-A01 三张 Project 表与约束已落地；该任务本身不包含业务命令或授权读取，后者已由 A02 补充只读摘要。
- PRJ-01-A02 建立当前 ProjectMember 事实的只读授权摘要；逐操作授权及生产登录安全配置仍未完成。
- PRJ-01-A03 完成 13 项 Project 路径内逐操作授权与目标归属核查；Project 列表/创建及实际写命令、生产 Auth/License 装配仍未完成。
- PRJ-01-A04 完成仅内部原子创建 Project、首位 Manager 与默认/指定 Department；真实 Auth Session/CSRF 已接，License Guard 在临时库仍为合成依赖，公开路由未开放。
- PRJ-01-A05 完成内部当前 Session/成员驱动的 Project 列表与详情读取；归档受权可读，跨项目隐藏，公开 GET 与生产 License 装配仍未完成。
- PRJ-01-A06 完成内部项目名称修改与单向归档，按当前管理角色和 expected version 串行化并同事务审计；跨模块归档写拦截及公开 API 仍需后续接线。
- PRJ-02-A01 完成内部授权成员历史列表与 keyset 分页；公开 HTTP 的不透明 cursor、生产 License 与安全运行接线仍未完成。
- PRJ-02-A02 完成内部成员创建与单项目并发唯一性验证；正式 POST 幂等、生产 License 与公开 API 仍未接线。
- PRJ-02-A03 按 CR-PRJ-001 完成内部成员角色/部门修改与历史保存；正式 PATCH 的 HTTP If-Match/幂等、生产 License 与公开 API 仍未接线。
- PRJ-02-A04 完成内部成员暂停/恢复/移除与最后负责人保护；正式 POST 幂等/If-Match、生产 License 与公开 API 仍未接线。
- PRJ-03-A01 完成内部授权部门历史列表和稳定分页；正式 GET 不透明 cursor、生产 License 与公开 API 仍未接线。
- PRJ-03-A02 完成内部部门创建、活动编码唯一与并发冲突验证；正式 POST 幂等、生产 License 与公开 API 仍未接线。
- PRJ-03-A03 完成内部部门名称/编码 PATCH、强版本与并发冲突验证；现有 Audit 不保留字段级旧值，正式 PATCH/生产 License 与公开 API 仍未接线。
- PRJ-03-A04 完成内部部门单向停用与 ACTIVE/SUSPENDED 成员引用保护；正式 POST 幂等/If-Match、生产 License 与公开 API 仍未接线。
- LIC-02-A02 冻结冲突已由用户明确批准方案 B；正式差异见 `docs/changes/CR-LIC-001-single-product-full-bundle.md`。V2.1 原文保留历史，专项补充为当前 License 授权粒度基线。
- 远端同步状态必须在每次任务结束前通过 Git 实时检查，不在本文件固化可能过期的 ahead/behind 数值。
- 本地用户文件和 Git 忽略的客户资料保持不变。
