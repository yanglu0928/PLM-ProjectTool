# Changelog

## Unreleased · 2026-11-02（内部云端验证，不是发行版本）

- P51-A48 按固定依赖顺序输出信任、DB凭据、服务ACL、TLS四组readiness待办；hosted run 41386839114 全12 jobs成功。零blocker完整登记仍需独立核验且不授权；候选ZIP SHA-256 `8e642dc1…aa48948`、20,122 files；A17/A34/PG通过。PASS_LIMITED。
- 兼容性：仅 hosted Windows Server 2025，无新Windows 11实测。
- 升级说明：仅内部非发行诊断候选更新；未安装/升级产品。
- 已知限制：正式信任/DB/ACL/TLS/法务条件未满足，Pilot/Gate/Release保持NOT_READY。


## Unreleased · 2026-11-02（内部云端验证，不是发行版本）

- P51-A47 为9个 readiness 缺项增加静态责任角色和下一步动作；hosted run 41383869172 全12 jobs成功。父包ZIP SHA-256 `1db6e14e…1452d370`、20,122 files；完整不授权、未知/秘密输入不回显；A17/A34/PG组合通过。PASS_LIMITED。
- 兼容性：仅 hosted Windows Server 2025；没有新的 Windows 11 实机验收。
- 升级说明：仅内部非发行候选诊断工具更新；未安装产品。
- 已知限制：正式公钥/License、DB身份、服务ACL、TLS与法务放行缺；Pilot/Gate/Release NOT_READY。


## Unreleased · 2026-11-02（内部云端验证，不是发行版本）

- P51-A46 为 readiness PowerShell 入口新增可选中文可读模式；GitHub hosted run 41382282100 全12 jobs成功。不完整/完整/无效三态通过，完整不授权、哨兵不回显，默认JSON保持兼容。候选ZIP SHA-256 `c9b6d945…7164d3`、20,122 files；A17/A34/PG18组合通过，PASS_LIMITED。
- 兼容性：仅 hosted Windows Server 2025；无新的 Windows 11 实机运行。
- 升级说明：只更新内部非发行父包诊断工具；没有安装/升级程序。
- 已知限制：正式公钥/License、DB身份、服务ACL、TLS、法务放行未满足；Pilot/Gate/Release仍 NOT_READY。


## Unreleased · 2026-11-02（内部云端验证，不是发行版本）

- P51-A45 为包内就绪报告增加9个缺项的静态中文填写指导；hosted run 41378263123 全12 jobs成功。候选ZIP SHA-256 `e2858a6b…0256ca`、20,122 files；完整登记不授权、非法值不回显、manifest不变。A17/A34/PG组合通过，结果 PASS_LIMITED。
- 兼容性：仅 GitHub hosted Windows Server 2025；未进行新的 Windows 11 实机验收。
- 升级说明：仅更新内部非发行候选诊断工具；未安装或启动产品。
- 已知限制：正式公钥/License、DB身份、服务ACL、TLS和法律放行仍缺；Pilot/Gate/Release NOT_READY。


## Unreleased · 2026-11-02（内部云端验证，不是发行版本）

- P51-A44 将非秘密 Pilot 就绪报告/模板和 PowerShell 入口纳入 Windows 候选包，并在 hosted run 41376505925 完成12/12组合验收；9项缺项正确显示、完整登记仍不授权、非法输入不回显。父包SHA-256 `8e3e4e37…f801d`，20,122 files；A17 29 API/A34恢复通过。详情见 [A44结果](docs/progress/plt-pkg-01-a09-p51-a44-readiness-tool-bundling-result.md) 与 [run](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41376505925)。
- 兼容性：仅 GitHub hosted Windows Server 2025；未进行新的 Windows 11 实机验收。
- 升级说明：仅内部非发行包内容变化；没有产品安装/服务升级。
- 已知限制：正式公钥/License/DB身份/服务ACL/TLS和法律放行仍缺；Pilot/Gate/Release保持 NOT_READY。


## Unreleased · 2026-11-02（内部云端验证，不是发行版本）

- P51-A43 从固定公开输入云端重建当前 PR 源码的 Windows 父包候选；12/12 hosted jobs 成功，父包 ZIP SHA-256 63ed5c8d…05a7a、20,118 个文件。同run完成暂存、PG18/pgvector、A17 29次API合成业务流和A34隔离替换/手动恢复演练。详情见 [A43 结果](docs/progress/plt-pkg-01-a09-p51-a43-hosted-rebuild-result.md) 与 [run 41370951575](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41370951575)。
- 兼容性：仅GitHub hosted Windows Server 2025；不能推定Windows 11新运行兼容。
- 升级说明：生成仅限内部验证的临时候选artifact，不是安装器或正式Release；未在本机安装/运行。
- 已知限制：正式信任、License、数据库凭据、服务ACL与TLS前置仍缺，应用/服务未启动，Pilot/Gate/Release保持NOT_READY。

## Unreleased · 2026-11-02（内部云端验证，不是发行版本）

- P51-A42 将包外 Authenticode 指纹校验接入候选暂存CLI。安装器与指纹成对提供；校验失败时ZIP暂存目标不创建；成功收据仅标记 TEST_ONLY。GitHub hosted Windows run 41370763918 的26项定向回归和A35集成通过，PASS_LIMITED。
- 兼容性：仅在 GitHub hosted Windows Server 2025 验收；不推定 Windows 11 实机兼容。
- 升级说明：仅开发/云端验证工具更新，没有安装包升级或产品安装。
- 已知问题：真实产品发布者证书/固定指纹及安全安装执行路径仍未建立；Pilot/Gate/正式Release仍 NOT_READY。


## Unreleased · 2026-11-02（内部云端验证，不是发行版本）

- P51-A41 新增 Windows Authenticode 只读校验器，要求包外签发者指纹；未签名、签名异常、指纹不匹配或调用失败均拒绝。GitHub hosted Windows run 41370436650 的24项定向回归及真实签名/未签名文件验证通过，PASS_LIMITED。
- 兼容性：只在 GitHub hosted Windows Server 2025 验证；不推定 Windows 11 实机兼容。
- 升级说明：仅内部验证工具；没有改变候选父包，不安装或升级已有程序。
- 已知限制：未提供真实产品代码签名证书/外部正式指纹，验证结果标记 TEST_ONLY；Pilot/Gate/正式Release仍 NOT_READY。


## Unreleased · 2026-11-02（内部云端验证，不是发行版本）

- P51-A40 新增 hosted 离线候选暂存CLI与专用 GitHub Actions 验收；19/19 定向测试通过。A35 父包 SHA-256 `94700239…e2f2`，20,119 payload files 验证并暂存；A38 保持5项启动阻断，包内诊断 `BLOCKED/exit 2`。验收 run [41369734304](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41369734304)，结果 PASS_LIMITED。
- 兼容性：验收运行于 GitHub hosted Windows Server 2025、D盘 runner temp；不构成 Windows 11 实机兼容证据。自2026-11-02起没有在用户本机运行程序。
- 升级说明：仅内部开发工具/云端workflow变更；没有生成可安装升级包，不触碰已有安装。
- 已知问题：正式产品公钥/License信任、数据库凭据身份、服务账户ACL、TLS材料及包外可验证代码信任仍未齐；未安装、未启动服务，Pilot/Gate/正式Release保持 NOT_READY。

- 2026-10-30 P51-A39：只读核查A35真实父包确认根目录无安装/升级入口，只有manifest、hash清单；payload仅含说明、诊断和fail-closed launcher。A34/A35隔离恢复不等于安装或重启。新增CR-PKG-012，在持续授权下推进离线分阶段安装入口，不越过正式信任/服务/TLS/DB门禁；本轮未解包、安装或重启。见A39结果及CR-PKG-012。
- 2026-10-30 P51-A38：新增只读 Pilot 就绪诊断器，合并非发行父包 manifest 的固定阻断字段与A37登记完整度。即使所有标志为真且登记完整，也恒定返回pilot_ready=false/launch_authorized=false/release_eligible=false/legal_clearance=false。Windows 11 Python 3.13合计12/12测试通过；用A35父包SHA 94700239...e2f2内存读取manifest与空模板完成只读集成。无服务/DB/凭据访问或C盘运行，Pilot/Gate/Release不变。详见 `docs/progress/plt-pkg-01-a09-p51-a38-readiness-report-result.md`。
- 2026-10-30 P51-A37：新增 Windows Pilot 非秘密输入登记器、空白JSON模板及操作约定。只接受固定格式的公钥SHA指纹、License/证据引用、固定DB Credential Manager目标、Windows服务身份引用和TLS元数据；未知字段/无效值拒绝且不回显。完整登记也只标记需独立验证。Windows 11 Python 3.13合成测试6/6通过，未读密钥或接入启动放行。PASS_LIMITED，Pilot/Gate/Release不变。见 `docs/progress/plt-pkg-01-a09-p51-a37-input-register-result.md`。
- 2026-10-30 P51-A36：盘点 Windows 11 Pilot 正式信任前置自动化。固定公钥/License、限定数据库凭据、服务身份/ACL、真实TLS链尚缺实际输入；现有工具只提供缺项守门或材料到位后的部分检查。无前置被虚假关闭，Pilot/Gate/Release仍NOT_READY。Windows 11本机启动前置单测2/2通过；另一模块导入依赖未装，不写C盘安装。详见 `docs/progress/plt-pkg-01-a09-p51-a36-windows11-trust-prerequisite-audit-result.md`。
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
