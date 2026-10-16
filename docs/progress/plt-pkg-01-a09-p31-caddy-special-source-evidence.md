# PLT-PKG-01-A09-P31：Caddy 四项非vendor组件出处核查

日期：2026-10-01；状态：`NON_RELEASE_CADDY_SPECIAL_SOURCE_EVIDENCE / LEGAL_REVIEW_OPEN`。输入P22固定ZIP SHA-256 `2ac746411ff68cfd3f9fa08a2483ca3473c2c83d3d65531f5e8d21f40a6ac6a5`、P29/P30固定CSV及官方SBOM/源码包。只做字节与元数据对照，不解释法律义务。

编码前检查：Phase2/Gate3开放；本任务仅对P30排除的四个非vendor组件做来源核查，不改实体/API/权限/Schema/打包内容/服务。验收先全量验证ZIP和既有CSV Hash，再核源码根目录、随包许可证、SBOM二进制Hash及Go版本；未能从本候选证明的关系必须明确为未证。风险是SBOM字段和源文件存在仍不足以放行最终NOTICE或对应源码义务。

`tools/audit_caddy_special_sbom_components.py`真实固定包运行exit0、定向单元1/1。四项结果：

|SBOM条目|本候选可证明|未证明|
|---|---|---|
|`Caddy`应用|根源码`LICENSE`与随包文本字节一致（SHA-256 `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`）；根`go.mod`要求`github.com/caddyserver/caddy/v2 v2.11.4`，与应用SBOM版本一致|法律适用及完整下游NOTICE|
|`caddy`主模块|根`go.mod`声明`module caddy`|SBOM伪版本`v0.0.0-20260601193502-e2eee6a7fce3`不能由根源码单独证明|
|`stdlib`|根`go.mod`声明Go `1.26.3`，与SBOM `go1.26.3`相符；SBOM自身声明`BSD-3-Clause`|Go标准库源码与独立许可原文未在本候选定位；该声明未经过适用性复核|
|构建二进制文件|SBOM的SHA-256与随包`payload/web/caddy.exe`精确一致：`5cb9ab71e5756ce72840b8234177a2f40c8b4ab47a806b8e841e2b784e9df62b`|仅Hash相同不说明全部第三方声明已履行|

根`go.mod` SHA-256 `a86f6e0f999248b6b12db7a3a9a7ea57eb45c382e8b2f00a60d2a69b3e90ddc5`。下一项P32调查并固定Go 1.26.3官方源码/许可来源，再决定是否补入**新非发行候选**；不得静默改P22历史或把来源可获得性写成法律批准。其余产品LICENSE/NOTICE、Ghostscript和全部Gate继续开放；`legal_clearance=false`、`release_eligible=false`。回滚弃用本只读核查工具和报告即可。
