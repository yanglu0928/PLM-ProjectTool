# CR-HND-009：交接待办固定来源导航

- 日期：2026-11-02
- 状态：已登记，按既有持续授权执行；不改变 Gate 结论
- 关联 WBS：PLT-PKG-01-A09-P51-A50
- 来源：A50 前置审查发现 Action GET 只返回不可变来源版本 ID 与问题 ID，但没有父 Analysis ID；现有详情页面因此不能构造精确、可授权的来源路由。Survey 的来源定位和 Handover 的 Evidence Viewer 已证明按项目权限读取固定来源可行。
- 冲突/证据：冻结的 HND Action GET 投影没有 parent analysis identity；前端严格校验 DTO；HandOver 详情路由需要 Project + Analysis ID，固定版本只能通过 `fixedVersionId` 查询选择。不能从 action 的两个 ID 猜测父分析，也不能遍历项目分析列表或拼接本地路径。
- 方案：
  1. 改数据库/API Action GET 已有 DTO，增加父 Analysis ID：改动少，但会改变冻结响应形状并要求旧严格客户端兼容处理。
  2. 新增只读 Action 来源子资源，按当前已授权 Action 解析不可变来源链，返回受控的 Analysis/Version/Item ID；现有读权限重新验证，不写 DB、不改旧 Operation/投影。
  3. 不提供跳转，只展示来源 ID：安全但不满足用户已确认的待办直达原文位置诉求。
- 选择：方案 2。新增可选只读子资源 `GET /api/v1/projects/{project_id}/handover-action-items/{action_item_id}/source-location`，要求 Action GET 同等 Session、License、Project/member 读取授权；服务端从同 Project 的 Action → Version → Analysis Item 关系解析，禁止客户端传入/覆盖目标 ID。HUMAN 来源返回受控 UNAVAILABLE，不推造文档锚点。前端导航只使用返回的固定版本与问题 ID；目标页面对 Project/Analysis/Version/Item 再授权和严格核对。
- 差异与影响：新增一个可选、只读 V1 子资源及客户端交互；既有 Operation 和数据库 Schema 不变，无 Migration、依赖或配置变化。普通应用仍不挂载，只有显式 Handover Action read router 组合可用。
- 安全风险与控制：越权/跨项目/已失效来源泄漏；通过同等现有 Project 权限、项目条件 SQL、固定父版本一致性检查、统一隐藏 404、no-store 和后续目标 GET 复核降低风险。不返回正文、Evidence Locator、文件路径或下载 URL。
- 回滚：移除该只读子路由/客户端按钮和目标页的可选 source item 导航参数；既有 Action GET、业务记录和历史确认保持不变。
- 验证计划：云端 Hosted Windows runner 上运行后端读 Owner/API/Windows Composition 定向与全量测试；前端客户端/Action 工作台/HandOver 详情定向与全量 typecheck/build；托管 Edge 合成测试验证同项目跳转、跨项目拒绝、HUMAN 安全退化、失效版本/不存在 item 错误、列表翻页定位和动作后状态不丢。无客户数据；不进行本机代码运行、正式安装、服务启动、外部数据发送或 Gate 推定。
- 本次变更不替代真实 Windows 11 设备验收，不关闭 Gate 3、Pilot 或 Release。

## 云端验证偏差记录（修复前）

- 2026-11-02 hosted run 41390769460：前端 Vitest 200 个文件/2,075 项通过；TypeScript 检查发现新增 Handover 目标锚点测试在 `DOMWrapper` 上调用类型不提供的 `.exists()`，造成构建失败。这是验证断言与组件测试库 API 的不兼容，不是运行时产品功能缺陷。
- 影响：仅阻断该提交的前端 typecheck/build；当前证据不能标记 A50 通过。后端全量验证仍进行中。
- 修复：只改测试断言为读取定位元素的 `id` 属性并与合成来源 Item ID 比对；不改产品逻辑、API、Schema、权限或用户数据。回滚可恢复原测试文本；无需迁移。
- 复验：记录此偏差后，提交测试修正，重跑 GitHub hosted Windows PR 完整流水线，要求全量前端 tests/typecheck/build 与后端全量测试/wheel 成功；保留失败 run 和修复后 run 链接。

## 云端验证偏差记录（二）：后端组合路由清单

- 2026-11-02 hosted run 41391080344：前端全量 2,075 项、TypeScript 检查和生产构建通过；后端全量 3,850 项中 3,849 项通过，唯一失败为 `test_composes_two_read_routes_with_dedicated_key` 仍将 Windows 显式组合根的预期路由固定为两个，未包含本次新增的只读 `/source-location` 路由。
- 影响：这是既有组合根清单测试未随新增可选 Operation 更新；不表示运行时授权或业务逻辑失败。后端全量不能标 PASS，后续依赖包任务被工作流跳过。
- 修复：仅更新该测试预期路由列表，纳入 `/api/v1/projects/{project_id}/handover-action-items/{action_item_id}/source-location`；产品代码、Schema、权限合同和数据均不变。无迁移；回滚仅恢复旧断言。
- 复验：本条先于测试代码修复写入；随后重新运行 GitHub Hosted PR 全量流水线。要求后端全量、wheel、前端全量/typecheck/build以及工作流适用的云端检查通过后才能关闭 A50。该 Windows runner 是托管 Server 2025，不构成真实 Windows 11 设备验收。

## 2026-11-02 云端复验结果与剩余证据

- 修正提交 `ae1c0455f0fdb7c54d4f9fe6b7364c8a5ae37c12` 的 GitHub hosted run [41391544470](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41391544470) 全12 jobs成功。后端全量3,850项、前端2,075项（200文件）、前端 typecheck/build 成功；PG18.6/pgvector0.8.6临时生命周期、父包离线替换/手动恢复及既有 A17 Packaged PlanVersion Edge/HTTPS/PG（29次 API调用）通过。
- 父候选包摘要 `24f37f60eb1f95a893af829b796926873c02b55e4f0b7d4762486f8dc6db3eda`，payload 20,122项。PG/安装演练仅用本轮临时数据，产品 API/services 均未启动；正式 License trust未使用，legal_clearance/release_eligible均false。
- 范围边界：A17仅为PlanVersion浏览器流程，不构成待办来源导航的专项 Edge 证据；因此A50记录为PASS_LIMITED，下一WBS A50-E01为 hosted Windows Edge 合成来源导航验收。该补充任务完成前不把A50提升为完整PASS。
- 本轮没有在用户本机或其C盘运行程序；hosted验收runner将仓库/临时数据放在D盘runner temp。托管Windows Server 2025不推定Windows11实机兼容；Gate 3、Pilot、正式Release不变。

## A50-E01 工作流表达式偏差记录（修复前）

- 2026-11-02 提交 `b175d799d207dd36163c9e49dfe9313f3e3b3600` 的只读复核发现，新增 GitHub Actions job 的 `${{ runner.temp }}`/`${{ github.sha }}` 模板表达式保留了转义反斜杠，产物路径和 Artifact 名称可能不符合 Actions 求值语法。
- 影响：仅影响新加 A50-E01 hosted Edge job 的 YAML表达式；产品代码和既有 workflow jobs 未变。尚未把 E01 标记为通过。
- 修复：先记录后将表达式恢复为标准 Actions token，补上云端 Node 语法检查步骤；不改产品行为、API或数据库，无迁移。
- 验证：由随后 GitHub hosted PR workflow 在 Windows runner 执行 harness；若 job 未触发或YAML校验失败，继续按日志记录和修复。

### A50-E01 工作流上下文偏差（二，修复前）

- 2026-11-02 hosted run 41393864311 因新增job的 `env` 在job层引用仅适用于step层的 `runner.temp`，GitHub未创建任何job，不能记为代码验收失败或通过。
- 修复：先记录后移除job级TEMP/TMP，把 `TEMP`/`TMP` 限定到启动Edge harness的step级 `env`；Artifact/下载路径仍用允许的 `runner.temp` 表达式。工作流不接触客户数据、生产信任或用户设备。
- 复验：提交后从 Actions API 确认新run实际生成A50专用job，再依据该job及前端构建结果验收。


### A50-E01 合成待办排序偏差（三，修复前）

- 2026-11-02 hosted run 41394132945 的 A50 Edge 专项 job 已在 GitHub 托管 Windows Server 2025 上启动；前端构建产物来源校验和 Node harness 语法检查均通过。浏览器加载“交接待办”列表时，因严格 DTO 客户端拒绝合成列表，超时后展示受控不可用状态；请求未进入待办详情与来源定位步骤。
- 根因：四个合成摘要具有相同 updated_at，fixture 按 Action ID 升序排列，而生产读取客户端在更新时间相同情况下要求 Action ID 严格倒序。它是验收夹具不符合既有只读 API 合同，不是产品运行时故障；本次浏览器结果不能验收 A50-E01。
- 修复计划：本条先登记，然后仅反转合成摘要顺序以满足既有排序合同；不修改产品代码、API、数据库、权限或客户数据，无迁移。回滚仅恢复原 fixture 顺序。
- 复验计划：重新运行同一 GitHub hosted PR workflow，确认列表/详情、固定版本跨页定位、HUMAN 安全退化、跨项目拒绝及失效来源状态保留全部通过；保留本失败 run 作为审计记录。
