# Changelog
- 2026-10-30 P51-A35：Windows 11 Home 中文版 build 26300 实机 D 盘隔离完成两份父包初装/替换、失败隔离和显式恢复；旧/新20,119项、4类持久标记保留，16/16分块Artifact摘要复核，launcher继续BLOCKED/exit 1且无service/API/listener。hosted run 41026213054全12 jobs success；只PASS_LIMITED，不代表正式安装、其他Windows 11 edition或Pilot/Gate/Release通过。详情见 `docs/progress/plt-pkg-01-a09-p51-a35-windows11-package-rehearsal-result.md`。
- 2026-10-30 P51-A34：hosted Windows Server 2025 D盘隔离完成父包初装、整包替换、失败候选隔离及显式手动恢复；旧/新候选各20,119项，4类持久数据标记保留。launcher持续BLOCKED/exit 1，无service/API/listener启动。GitHub Actions run 41020308619全11 jobs成功，A34证据Artifact SHA-256 `d284a29542f01825da7375151449030c754f7a8cf63a48c37f897f9758b5e325`。A34仅PASS_LIMITED；不代表Windows 11实机安装、正式信任、Pilot、Gate或Release通过。详情见 `docs/progress/plt-pkg-01-a09-p51-a34-cloud-install-rehearsal-result.md`。
- 2026-10-30 P51-A33：父包启动入口在受信任前置缺失时复用只读诊断并输出六项BLOCKED JSON，仍以exit 1拒绝启动；缺诊断脚本/损坏manifest回退、无listener、A29/A30篡改矩阵及同run PG18/A17均通过。Hosted run 41008231772全10 jobs success；后端3,849项；A17 PlanVersion 29 API调用。父包SHA-256 104b8559...55cf6。采用.NET流式SHA-256兼容PowerShell 5.1；多轮偏差及PR #60远端并发合并事实已记录。无API/Schema/Migration变化；仅PASS_LIMITED，Pilot/Gate/Release仍NOT_READY。详情见 `docs/progress/plt-pkg-01-a09-p51-a33-launcher-feedback-result.md`。
- 2026-10-30 P51-A32：精确将父包级payload/check-startup.ps1排除在当前应用布局投影之外；全源清单仍校验、其他未知文件仍拒绝。新增投影单测5/5、后端3,849项通过；A31父包诊断+PG smoke和A17 PlanVersion Edge/HTTPS/PG（29 API）同run通过，详情见A32结果文档。无API/Schema/Migration变化；候选仍非发行，Pilot/Gate/Release NOT_READY。
- 2026-10-30 P51-A31：hosted父包实际解包根目录README诊断命令专项PASS_LIMITED；清洁父包20,119文件，SHA-256 10eca56d...57acc6，命令固定BLOCKED/exit 2/无监听。后续A17组合检查发现新增父包级诊断脚本未列入应用投影白名单，已登记P51-A32；此workflow整体未全绿。无API/Schema/Migration变化；Pilot/Gate/Release仍NOT_READY。
- 完成 P51-A28 受限 Windows 启动协调器正式信任/凭据/ACL/TLS前置显式守门；hosted run 40981581644全10 jobs通过。真实父包仅固定拒绝，A17 PlanVersion Edge/HTTPS/PostgreSQL闭环PASS_LIMITED；不代表Windows 11设备或正式发行。
- 完成 P51-A29 启动manifest严格类型检查及7种篡改清单hosted负例；run 40983612763的PG smoke job通过，stdout为空、无listener、源manifest未变。未接入正向生产启动。
- 兼容性/升级：仅内部非发行候选及启动诊断守门变化，无API或数据库迁移；不得覆盖已有安装。
- 已知限制：正式产品公钥/License trust、服务账户数据库凭据/ACL/TLS配置与Windows 11设备安装升级仍未齐备，Pilot/Gate/Release保持NOT_READY。
- P51-A30新增父包只读启动前置诊断命令：仅读非秘密manifest，输出BLOCKED及缺少项，不启动服务或读取凭据/私钥。hosted run 40988858723的D盘父包PG smoke验证当前报告及4类篡改输入，A29七类守门矩阵同轮通过。
- 版本/升级：仅非发行包增加一个PowerShell诊断脚本与README说明；无API/Schema/Migration变化，不对已有安装执行升级。
- 已知限制：该命令只说明当前候选未具备的启动条件，不会使包具备正式信任/安装资格；Pilot/Gate/正式Release仍NOT_READY。



## Unreleased · 2026-10-30（内部云端验证，不是发行版本）

- 修正 PlanVersion 固定历史读取 Client 对浏览器原生 fetch 的接收者调用方式；增加 this/globalThis 回归覆盖。没有改变冻结 API、数据库、Migration、权限或状态机。
- 完成 A17 父包中 PlanVersion Edge/HTTPS/PostgreSQL 合成闭环 hosted 验收；详情见 [A27 验收记录](docs/progress/plt-pkg-01-a09-p51-a27-planversion-cloud-result.md) 与 [GitHub Actions run 40841364426](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/40841364426)。
- 兼容性：本次前端修复不要求数据库或API升级；hosted Windows Server 2025 验证不是 Windows 11 设备验收。
- 升级说明：仅内部代码候选，不能作为正式安装包；后续同源候选应从该提交重新构建，不对既有安装执行升级。
- 已知限制：manifest 保持 release_eligible=false/legal_clearance=false；正式License信任、服务账户凭据/TLS、离线安装升级和 Windows 11 实机验收仍未完成，Pilot/Gate 3/正式Release NOT_READY。
