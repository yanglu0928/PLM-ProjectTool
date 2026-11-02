# PLT-PKG-01-A09-P51-A46：控制台可读就绪报告（编码前检查）

- 日期：2026-11-02
- 状态：编码前检查完成；本检查提交后方可编码。

## 任务定位

A45 已将逐缺项的静态中文指导纳入父包 readiness JSON，但默认 PowerShell 入口直接打印紧凑 JSON；内部操作者不便逐项浏览。当前 Pilot 和正式 Release 仍 NOT_READY，A46 仅改善包内只读诊断的呈现方式，不接入安装或启动。

## 单一目标

为父包 readiness PowerShell 入口增加一个可选 `-Readable` 输出模式，将固定诊断状态、阻断代码及9项内静态字段指引渲染为清晰中文文本；默认 JSON 模式保持现有字节结构、stdout/stderr 与 exit code 行为。文本模式只用静态字段和reason codes，不输出登记表的值、路径、未知键、客户资料或秘密。

## 输入/输出与安全边界

- 输入仍由现有显式 RegisterPath 指定；不自动搜索凭据或其他用户文件。
- Readable 模式只能显示 status/固定 blocker/reason code，以及从 A45 静态字典返回的 label、maintain、source、never。
- 完整合成登记依然显示“需要独立核验”，绝不显示“可启动/可发行”；launch_authorized、pilot_ready、release_eligible、legal_clearance 保持 false。
- JSON 默认调用方保持兼容。PowerShell 5.1/7 中文输出以 UTF-8 控制台为目标；不在报告中显示绝对路径或输入值。
- 无数据库、HTTP、服务、License材料、证书私钥或进程提权；不写文件，不调用外网。
- 仅在 GitHub hosted Windows Server 2025 的D盘 runner temp完成 PowerShell 模式和全量组合验收；不在用户本机运行，不推定 Windows 11 新兼容性。

## 验收标准

1. JSON默认模式与现有契约保持相同退出码：完整/incomplete/invalid分别维持已有行为；JSON保持machine-readable。
2. `-Readable` 对9个缺项输出所有固定字段标题和提示；完整输入输出独立核验状态，不授权；无效输入输出固定错误摘要且不泄漏注入值。
3. 测试至少覆盖 PowerShell 5.1、stdout/stderr/exit code、中文文本、未知键和秘密哨兵值。
4. A45现有 Python 单测、父包报告集成 smoke、A17/A34/PG18组合 workflow 全通过；候选manifest不因展示模式变化而变更。
5. 不安装、不启动应用/API/服务/数据库，不触碰用户数据/C盘。

## 兼容、风险与回滚

新增可选开关，不改变默认输出、不更改输入登记schema。控制台代码页可能出现中文呈现差异，需在 hosted runner 验证捕获的UTF-8字符。回滚为移除 Readable 开关、呈现函数和对应测试；manifest/provenance可随新候选重建，无数据迁移。没有正式基线、API、DB或License变化，无需新CR。

## 编码前检查结论

WBS单一聚焦于诊断结果可读性；依赖A45静态指导和既有只读报告，不扩展信任边界。依赖已满足，先提交本前置检查，然后编码；结果写入STATUS、CHANGELOG、CR-PKG-012/CR-EXEC-005并保留CI偏差历史。


## 编码后静态复核偏差（2026-11-02）

首次代码提交 `f2641dd92d1b954e2fef048f5bd46c74d83505d2` 后、云端 A46 验收前的静态复核发现，文本渲染函数使用了双重转义换行，输出会显示字面字符 `\\n` 而不能分行。未进行本机运行；JSON默认分支和安全边界未受影响。先记录该偏差，再修正为真实换行，并将分行断言纳入 hosted PowerShell smoke。回滚方式不变；本次不保留该坏输出作为通过证据。
