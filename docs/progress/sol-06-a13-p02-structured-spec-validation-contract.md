# SOL-06-A13-P02：结构化专项类型化验证报告合同

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`STRUCTURED_SPEC_VALIDATION_CONTRACT_PASS`；仅完成纯应用合同，不表示现时事实 Owner、HTTP、Windows 装配或送审已实现。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `SOL-06-A13-P02`|
|输入基线|Gate 2 冻结 `SOL_SPEC_VALIDATE`、0161～0164 不可变完整专项、A13-P01 八维事实与四类检查边界、既有 SectionVersion VALIDATE 首次观察先例|
|前置任务|A13-P01 已明确 VALIDATE、Review 与批准边界；本项可在不接数据库/HTTP 的条件下先固定纯值对象|
|涉及模块/实体|Solution / StructuredSolutionSpec；新增命令、固定快照、观察、类型检查和报告值对象|
|涉及 API / 权限|保留冻结路径与未来 `SOL_STRUCTURED_SPEC_VALIDATE` 策略；本项未注册 Router、未开放权限或生产入口|
|验收标准|严格身份与幂等指纹；八维事实和四类精确有序检查；确定性 issue、valid/ready；首次观察可由有界 Audit reason 无损重建；伪造报告失败关闭|
|风险|把未知 Owner 折算为 PASS；历史/非 DRAFT 版本误报 ready；类型检查缺项或重排；正文指纹、结论或 issue 被伪造；Secret 出现在 repr|

## 实施结果

- 新增 `ValidateStructuredSpec`：Session/CSRF/原始操作号不出现在 `repr`，请求指纹只绑定项目与固定 SpecVersion；独立操作名为 `V1_SOL_STRUCTURED_SPEC_VALIDATE`。
- 固定快照绑定项目、SpecVersion、系列、四类专项类型、版本号/状态、content/payload 指纹和四类引用计数；畸形 UUID、状态、指纹或计数直接拒绝，不生成业务 FAIL。
- 八维事实仅接受 `PASS`、`FAIL`、`UNAVAILABLE`；四类专项分别要求精确有序的 3/3/5/3 项类型检查，缺项、多项、错序或未知类型均失败关闭。
- `valid` 只由不可变完整性、payload、Requirement、Section、Evidence 五项现时事实派生；`ready_for_review` 另要求系列最新 DRAFT、Artifact、Trace 及全部类型检查通过。报告不创建 Review、不推进状态，也不把 Audit 成功解释为业务通过。
- `issue_codes` 由版本状态、八维事实及类型检查确定性生成；报告构造时重算并拒绝伪造结论或 issue。Audit reason 使用版本化类型码和状态字母，可精确还原首次观察，未知/截断/多余编码一律拒绝。

## 验证证据

- 定向合同：`33 passed in 0.13s`，覆盖命令身份/Secret、非法输入、四类精确检查集、Audit 编解码、八维 FAIL/UNAVAILABLE、类型 Owner 缺口、全通过、非 DRAFT/非当前和伪造报告。
- 后端全量：`3694 passed, 3 skipped, 5791 subtests passed in 94.51s`。
- Python compileall：新增生产模块通过。
- 使用项目既有离线 Python 3.13.15 构建环境生成开发 wheel；1402 个条目，新模块恰好入包 1 份，SHA-256 `b274b3f6e58af2abe74a1b50ee6fb46f1314c5067eb3981e1d9c4a5b9b210db2`。测试 venv 无 pip/build、系统 Python 无 setuptools，未改生产依赖，转用已验证构建环境后通过。
- 无数据库连接、Migration、真实 AI/外部网络、客户数据或 Secret 外发。

## 兼容、升级、回滚与遗留

本项仅新增未装配的纯应用模块和单元测试，无 Schema、冻结 API 字段/路径/角色、License、依赖、旧数据或运行模式变化；升级无需数据动作，未公开前可直接撤回模块。wheel 仅为开发入包证据，不是 Pilot 或正式发行包。

现时事实 Owner、受权 Repository/Service、持久收据/Audit 读回、HTTP、Windows 11 真实链、前端与 Edge 仍未实现。SOL-06 Trace/Artifact 及多类业务检查缺正式 Owner 时必须保持 `UNAVAILABLE`；正式信任、Windows Server 2025、Debian 13、性能、Gate 3、Pilot 与正式发行状态不变。

Next：`SOL-06-A13-P03` 实现固定 SpecVersion 验证读取与系列最新版本判定 Repository；只解决同项目不可变快照重建和 current-version 身份，不在该项推断业务检查或开放 HTTP。
