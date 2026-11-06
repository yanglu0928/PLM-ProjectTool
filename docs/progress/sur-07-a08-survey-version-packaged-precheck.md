# SUR-07-A08：固定候选调研问题版本包内验收编码前检查

日期：2026-11-07；状态：首次 Hosted 运行失败，待安全诊断后复验。

## WBS 与基线

- 当前阶段：Phase 2 / CR-EXEC-002 Windows 11 Pilot 关键路径；下一 WBS 为 SUR-07-A08。
- 输入基线：Gate 2 冻结的 /api/v1、CR-EXEC-002、CR-SUR-013、SUR-07-A05/A06/A07 和当前 Windows 非发行候选组装流程。
- 前置任务：SUR-07-A07 已完成 Survey version create 页面与前端回归；Hosted run 42248236859 的 A17 packaged PlanVersion/HTTPS/PG、P40 live download及父包完整构建通过。P40 startup preflight 同时确认正式公钥/License trust、DB credential reference、service ACL、TLS 尚未验证，正式 Pilot 仍受阻。
- 输入文件：既有 validation/sur-07-a08-survey-version-packaged/verify.py 与 run-survey-version-edge.mjs，已有但尚未接入本分支 Hosted job；候选来源为同 run assemble-a17-current-app-candidate。

## 编码前检查

|项目|结论|
|---|---|
|涉及模块/实体|仅新增 Hosted 验收工作流接线和受限证据归档；运行既有页面。测试实体为 Project/Document/HandoverAnalysis/Survey/SurveyVersion/Review/Audit/幂等 Receipt，全部合成、一次性。|
|API|仅使用已有 Survey Handover Source GET、SurveyVersion Create/Validate/Submit Review 和 Review read/decision API；不更改冻结 API、业务逻辑或 schema。|
|权限|合成 ProjectManager 创建 DRAFT；合成受指派 Reviewer 审查；非指派项目成员只读并无决定控件；匿名、错误项目、错误角色、过期 License 均应拒绝。服务端仍是最终授权与来源重证方。|
|验收标准|从同 run 的当前非发行包中，在 Hosted Windows Server 2025 D:\ 临时目录使用真实 Edge + HTTPS + 隔离 PG18 执行：批准交接固定来源 + 实际面对面访谈注释的 MANUAL 来源生成 DRAFT；问题/目标部门/来源快照一致；同操作号重放仅一版本/Audit/Receipt；版本校验、提交评审和固定版本导航通过；未授权和 License 过期拒绝且无额外写入；进程/Vault/临时根清理。只可标 PASS_LIMITED。|
|风险|既有 verifier 复用较早交接/调研夹具，集成失败可能来自 stale UI selectors 或 fixture，而非产品。需按安全摘要定位，不能以单元测试代替 Edge，也不能将合成客户 Reviewer 决策写为真人客户确认。|
|本次变更范围|仅把已存在 A08 verifier 接到新的独立 Hosted job，下载同 run A17 candidate；原始日志/凭据/客户数据不上传，summary 仅固定结果标记/IDs/布尔值。无 Migration、API 或产品代码变化。|
|回滚|移除该 Hosted job 与证据进度；保留旧源码、既有 A07 页面/客户端和 A17 结果，不改变父包或生产系统。|
|数据边界|只用新建一次性 Hosted D:\ temp、合成用户/项目/文档/交接/调查内容；不外发客户数据、不调用外部AI、不执行插件。|

编码前结论：PASS_WITH_LIMITATION。持续授权允许在现有 scope 内将 verifier 接入 Hosted workflow；无须等待人工确认。实施前先提交本检查与 STATUS/CHANGELOG，再接线并由 GitHub Hosted Windows runner 验证。


## Hosted 首轮结果（2026-11-07）

Hosted run [42254166208](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42254166208) 中，A08 job 已完成候选获取、D盘边界/Node/Python语法检查并启动 packaged verifier；验收器以 ValueError 退出，退出前没有输出任何 A08 成功标记。该 workflow 其余 jobs（含 A17、P40、P25、A34、前后端/PG18/父包）均成功；整体因 A08 失败标为 failure。

首次失败摘要按预设策略仅报告 exit=1、无标记、ValueError；owned 原始输出留在 D盘临时根并随清理移除，没有上传。当前证据不能判断 ValueError 来自候选/夹具、临时根、Caddy/API启动还是业务断言；不构成产品缺陷定位，也不构成 SUR-07-A08 通过。

## 下一步单变量调整

按 CR-EXEC-002/测试约束，仅增强失败摘要：从已捕获 traceback 提取异常类、源码 basename:line 以及最后通过的固定阶段标记；不提取消息正文、路径、请求/响应正文、凭据或原始stderr。保留 D盘清理和标记验收，再由 Hosted runner重跑。根因仍须来自新证据，不能凭猜测更改产品代码。


## Hosted 第二轮根因定位（2026-11-07）

Hosted run [42257007756](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42257007756) 的失败摘要在不回显原始日志的前提下给出 ValueError 来源 basename:line 为 rehearse_windows_unified_pg18_layout.py:64。只读核对该行确认既有隔离安装工具要求 stage、pristine、target 三个输出根均为 RUNNER_TEMP 直属、名称匹配 plm-install-rehearsal-[A-Za-z0-9_-]{8,64} 且目录事先不存在。本轮工作流传入 candidate-stage/install-pristine/install-target，违反其现有命名契约，因此在业务验证开始前被拒绝。此为 Hosted Harness 输入偏差，不是产品/业务 API 故障，PG/Edge 调研版本断言尚未执行。

修正范围：仅将三个 owned 临时目录命名为合规且互异的 plm-install-rehearsal-stage-a08-<run id>、plm-install-rehearsal-pristine-a08-<run id>、plm-install-rehearsal-target-a08-<run id>；继续确保它们均在 PLMToolTemp 直属、每次全新、结尾只清理本 job 私有根。然后完整 Hosted 复验。


## Hosted 第三轮结果（2026-11-07）

run [42259742947](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42259742947) 中 A08 job 已完成候选下载与身份摘要校验、D盘边界及 Python/Node 语法检查，并启动包内流程。验收器 exit=1、无成功标记；包装层安全摘要为 WinError、最后帧 <frozen ntpath>:709，stage 未输出。未上传原始 verifier 输出，临时 owned 根按流程清理。该证据不足以判断是临时路径、Caddy/服务进程或业务步骤问题，不证明产品故障或通过。

## 下一步单变量诊断（CR-EXEC-032）

仅增强测试验收器诊断：失败时输出异常类、可用的数值型 WinError、最多 8 个调用栈文件 basename:line（不包含路径/异常消息），并在验收器入口、包内 smoke、浏览器回调与关键回调边界输出固定枚举阶段。Workflow 仅从受限白名单读取诊断字段；保留现有D盘隔离、owned 清理、合成数据与严格验收标记。此轮不修改产品业务代码、API、Schema、权限或正式信任；由 Hosted Windows runner 复验后再判断根因。


## CR-EXEC-032 实施状态（2026-11-07）

已修改 A08 测试验收器和 Hosted Workflow：验收器在 smoke、浏览器回调、审批/Edge/过期License边界输出固定阶段枚举；异常时以固定格式给出异常类型、整数 WinError（若有）、最多 8 个清洗后 basename:line。Workflow 只从该格式提取受限字符白名单。A08成功标记、业务断言、同run候选身份校验、D盘边界和owned清理均保留。只改测试设施，不改产品逻辑。静态差异与Secret模式检查已完成；最终 Python/Workflow运行验收由新 GitHub Hosted run 执行，尚待结果。
