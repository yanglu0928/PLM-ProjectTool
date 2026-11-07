# CR-OUT-035：Output下载同进程 HTTP/PG18/Edge 纵向验收

- 日期：2026-11-06
- 状态：编码前检查通过，Hosted验收器实施中
- 阶段/WBS：Phase 2 Platform Core / OUT-01-A01-P40
- 来源：CR-EXEC-002（Windows 11 Pilot优先，保持验收标准）；P38真实FastAPI/PG18/Storage下载route验证；P39 Hosted Edge附件实际保存；P25真实Edge经loopback访问显式Windows API的失败关闭验证。
- 基线：冻结API Contract V1、Document附件下载合同、CR-OUT-021、CR-OUT-033、CR-OUT-034。无基线Breaking Change。

## 问题与决定

P38和P39分别通过了服务端持久层/内容流与浏览器下载保存，但运行在分层验收器中。P25的真实TCP/Edge路径验证了Output Create拒绝路径，不覆盖Artifact→Document下载成功路径。为尽快形成纵向交付证据，新增P40 hosted-only组合验收：同一Hosted Windows Server 2025 runner、同一隔离PG18/合成File Storage、同一FastAPI loopback服务和Edge production dist完成已授权合成Artifact下载。

继续沿用失败关闭边界。正式Publisher/License信任尚未提供，因此不创建真实输出、不执行插件、不把合成Session/License写成生产信任，也不声称Pilot/Gate/Release通过。

## 范围与影响

- 新增：P40验证脚本/测试、Cloud workflow job接线、CR/编码前检查/结果/STATUS/CHANGELOG。
- 不改：生产API、ORM/Migration、默认Router挂载、认证/授权策略、正式License和Publisher Trust、插件执行、业务数据。
- 合成数据只写入当前Hosted run在D盘的临时PG与Storage根目录；不调用外部AI/API，不读取客户材料。
- 测试必须核验浏览器单次Artifact引用读取及Document内容下载、授权范围、HTTP/保存文件Hash与长度、非授权失败关闭以及locator/正文保护。
- 需要提高依赖或修改生产逻辑时，先追加本CR的差异/风险/回滚/验收，再实施；不以更宽信任配置规避缺陷。

## 风险、验证与回滚

- 风险：Hosted Windows Server 2025结果不能推定Windows 11实机，也不能代表正式服务账号ACL或正式Publisher信任。
- 验证：Windows Hosted D盘运行隔离PG18/pgvector及ASGI loopback+Edge；全链后端/前端/wheel/父包及A17/A34/A35/P24/P39/A50回归，Secret扫描。失败时逐项保留证据，P40不标通过。
- 回滚：移除P40专属验收脚本与workflow接线，恢复前一状态；生产接口、迁移、业务事实不受影响。
- 客观缺项继续记录：Windows 11设备实测、正式Publisher/License trust、真实生成/插件执行、离线安装与升级、Gate 3/UAT/Release仍未完成。


## P39 hosted regression found during P40 implementation (run 42232610178, fix not yet applied)

- The full frontend tests/build and P39 harness syntax check succeeded. Real Edge then completed the valid row's Artifact GET, Document content GET and exact saved-file byte/hash assertions. The Harness subsequently threw `ReferenceError: Cannot access 'summary' before initialization` when adding a diagnostic flag before the summary object was declared; the cross-project negative assertion did not finish, so this run is a P39 regression and P40 is not accepted.
- Evidence points to the new Harness summary assignment order only; no backend route or product code failure is indicated. Before changing code, record the minimal correction: move the two P40 summary booleans into the final summary object, leave the request/UI/data assertions unchanged, then rerun the Hosted workflow. No product/API/Schema/Trust changes.


## P40 second Hosted attempt blocked before route execution (run 42233843515; fix not yet applied)

- Backend full suite/wheel, frontend full suite/build, P39 Edge regression and parent assembly succeeded. The parent PG18 smoke reached P33 but Python failed importing the new P40 verifier: its directory used hyphens while the import path used underscores. Therefore P40's FastAPI/Edge verification function never executed; this is an acceptance harness wiring error, not a route verdict.
- Before code changes, record the minimal fix: move the verifier to the repository's underscore package naming convention, align workflow syntax-check path/import, delete the unused hyphen-path copy, then rerun Hosted. No production code/API/Schema changes.


## P40 Hosted Edge process reached but harness hid failure stage (run 42236302466; diagnostic fix not yet applied)

- The underscore import is fixed. The parent PG18 smoke successfully reached P33; P33 invoked the new P40 verifier, which started the real FastAPI/PG18 setup and launched the Edge Harness. Node returned exit 1, but P40 converted its captured output to the generic message `P40 hosted Edge validation failed; exit=1`, so the failing browser/API assertion cannot be distinguished from runner launch/transport.
- This run does not establish P40 pass or product failure. Before another code change, record the narrow fix: on failure, parse the Harness JSON and report only a bounded allowlist of stage, synthetic API method/path/status, network error category, and exception class; never output cookies, headers, bodies, exception message or file contents. Then rerun Hosted and make the next correction from evidence.


## P40 reached live routes and saved bytes; negative UI assertion mismatched (run 42238876643; correction not yet applied)

- Safe Hosted summary shows synthetic login/history 200, the actual PostgreSQL-backed Artifact reference 200 exactly once, the actual Document content route 200 exactly once, and Edge saved the binary attachment (the only browser network failure was `net::ERR_ABORTED` with type `Document`, consistent with download navigation cancellation). The negative unknown OutputRequest reached the live Artifact route and returned 404; no Document content request followed.
- The harness then timed out waiting for P39's exact simulation-specific alert text during this live 404 path. Because the positive live download and backend negative 404 were observed and no content leakage occurred, this is a P40 test expectation mismatch, not evidence that route security failed. Before implementation, record the narrow fix: in live-backend mode wait for any non-empty role=alert and assert the actual unknown reference is HTTP 404; preserve P39's exact fixed-message assertion for its synthetic fixture and retain no-content/no-extra-download checks. No product behavior/API/Schema change.


## P39 regression from P40 summary flag placement (run 42242042216; correction not yet applied)

- The live 404 assertion change passed Node syntax but regressed the standalone P39 Edge fixture. Hosted Edge completed the same successful download path, then failed with `ReferenceError: Cannot access 'summary' before initialization` in the new negative-result flag assignment. This is a verifier-only TDZ error; no production/API behavior is implicated and P39 is not considered passing for this run.
- Before code modification, record the narrow correction: remove the pre-declaration `summary` write and place both negative-result flags in the final summary object literal; retain the live 404/alert checks and the P39 fixed-message assertion. Then run a source-level check confirming no `summary` reference precedes its declaration, followed by full Hosted validation.


## Hosted run 42243433283：P40 实时下载通过，A17 打包服务启动仍阻塞（2026-11-06）

- 来源提交：a279a56fc1eb3652bea2aa7bc82b545cd8ec7f4e；[完整 Hosted run](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42243433283)。所有项目运行均在 GitHub Hosted Windows Server 2025 的 D:\ runner/temp 完成，本机未运行项目代码。
- P39 独立合成 Edge 下载、前端测试/构建、后端测试/wheel、PG18/pgvector sidecar 重建、P24、A50、P25，以及 A34 离线替换/人工恢复演练均通过各自的 limited scope 检查。
- P40 job 为 success，生成并上传 plm-out-p40-live-edge-summary-42243433283.json 与 PG smoke 摘要。验收器执行内容是同一 Hosted 进程中的 FastAPI loopback + 临时 PG18 + Storage 与 Edge 浏览器下载链；结论仅限该隔离验证。不会据此声明 Windows 11 本机、正式信任、Pilot、Gate 或 Release 通过。
- 独立 A17 packaged PlanVersion/HTTPS/PG job 失败：包装服务在 /health/ready 前退出，现有日志只给出 stderr unavailable，未获得安全、可诊断的子进程退出原因。A17 不通过；这不是 P40 失败，也没有证据能推断产品具体启动根因。
- 下一项单一问题：为 A17 Hosted harness 安全捕获并输出子进程退出码及有界、脱敏 stderr 诊断，然后重跑当前独立 A17 流程。不得输出凭据、请求头、正文、客户数据或私钥；若发现真实产品问题再单独记录并修复。
- A34 limited 结果维持其边界：只验证合成包的替换、隔离/恢复标记保全和显式人工恢复；验证期间没有启动服务，legal_clearance=false，不代表生产升级/回滚获准。


## PLG-03-A06 编码前检查（2026-11-07）

```text
当前Phase：Phase 2 Platform Core
当前WBS：PLG-03-A06 PluginExecution PENDING→RUNNING transition Owner
输入基线：冻结 PluginExecution ORM/Migration 20261105_0231；PLG-03-A05 admission Owner/CR-EXEC-052；JobLeaseService.check_output_claim_in_transaction；AuditService 与 append-only state event。
前置任务：PLG-03-A05 Hosted PG18 专项 PASS_SCOPE_LIMITED（run 42344966652）；jobs、Output admission与PluginExecution持久化前置已完成。
涉及模块：Plugin application/infrastructure；Jobs/Audit仅复用同一调用方UoW。
涉及实体：Job/Lease claim、PluginExecution root、PluginExecutionStateEvent、Audit。
涉及API：无，不改冻结API Contract。
涉及权限：仅当前 OUTPUT_GENERATE、PROJECT、attempt 1 且项目/Job/claim完全匹配的有效worker fencing claim；Actor保持UNRESOLVED，不伪造服务账号。
验收标准：同一事务先校验当前lease，再锁定Execution；PENDING可原子转RUNNING并写started_at/lock_version、RUNNING事件与Audit；事务失败整体回滚。有效重放返回 changed=false 且不重复事件/Audit；过期/错误fencing、Job/项目/attempt不匹配和非PENDING终态拒绝且零写。Hosted PG18合成验收、后端全量测试与wheel通过。
风险：Schema不持久化Worker fencing token；Owner仅返回是否由本调用实际改态，调用方只有changed=true才能继续后续动作。当前无调用方/Worker接线，A06绝不启动ProcessHost或插件，也不视为执行成功；如Hosted证明该契约不足，先记录再停止本WBS，不擅改Schema。
```

### 决策、边界与回滚

- 锁顺序为 Jobs lease proof → PluginExecution root，避免在本WBS中反向取得Jobs锁；不调用Output Owner，也不增加跨模块Repository直调。
- 首次 transition 使用当前 claim 的 job_id/project_id/attempt_no校验Execution归属；DB owner GUC仅在全部事实核对后、同一事务中短暂开启。state event与Audit同UoW提交。
- RUNNING精确重放只报告changed=false，不写任何状态、事件或审计；任何终态均不在A06处理。结果完成/失败/取消、retry、worker认证/身份映射、API与ProcessHost均留待后续独立WBS。
- 风险：任何调度层若忽略changed=false可能重复执行。因此当前无production consumer；未来接线前必须有单独WBS和验收证明消费规则。
- 回滚：仅移除A06 Owner/repository/tests/verifier及其workflow步骤；无Schema/Migration/API/生产接线与业务数据变更。
- 验证：GitHub Hosted Windows Server 2025 D盘合成PG18；先新增单元测试与专项PG18事务/回滚/owner-guard verifier，再跑现有全量Hosted链。Secret扫描必须0命中；不在用户本机/C盘运行代码。

### 前置链状态修正（2026-11-07）

run [42344966652](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42344966652)中P40 live Edge下载与PG18父包smoke、A05 Admission Owner、A34包替换/人工恢复演练成功；整run仅A08失败。上一轮P40在`history-ready`阶段无summary，随后相同代码/流程在本run成功，按单次Hosted失败作为间歇性Harness/Edge事件保留，不据此改生产逻辑。A08 0xC0000135状态及 Pilot 限制保持原样。
