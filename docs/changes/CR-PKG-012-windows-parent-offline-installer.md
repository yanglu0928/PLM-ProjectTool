# CR-PKG-012：Windows 父包离线安装入口与安全分阶段落地

- 日期：2026-10-30
- 状态：按用户 2026-09-24 持续自主执行授权登记，实施前置记录；不代表 Gate/Release 批准或通过。
- 来源：`PLT-PKG-01-A09-P51-A39` 发现父包无根级接收/校验/落地入口；用户持续授权要求交付可用程序包，并要求本机项目运行优先 D盘/云端。

## 变更

在 Windows 父包根目录增加独立 PowerShell 5.1 离线安装入口和操作说明。入口接收外部预期 SHA-256 与显式安装根，先检查候选ZIP身份、根清单、路径安全、逐文件hash和目标盘空间，再在同一目标盘的私有staging中解包/读回验证。对非发行候选默认只可停留在隔离准备态；正式信任/License、服务身份/ACL、TLS、数据库凭据及法务放行任一未满足时，拒绝发布到正式运行位置并禁止SCM/数据库/API启动。不得从包内自报布尔值授予信任。

## 基线影响

- 保持模块化单体、数据模型、API/DB Schema、License协议与服务安全边界不变；不新增外部依赖或联网动作。
- 父包增加根级安装脚本和说明，包清单/父包hash及组装测试随之更新；是可追溯的包布局扩展，不覆盖历史候选。
- 不安装到用户真实目录，不读写 C盘；W11验证目标用 D盘新建ASCII隔离目录。不得注册服务、启动数据库/应用、执行Migration或重启用户设备。

## 方案与选择

- A：只补充人工解包说明。风险最低，但不能稳定核验整包/逐文件完整性、失败清理和重复执行，无法形成可交付安装路径。
- B：实现离线、分阶段、fail-closed 的包接收/校验与隔离落地入口；发生异常时保持原目标不变并给出固定非秘密状态，显式清理需限制到工具所有的staging。选B，满足Pilot准备目标且不越过启动安全门。

## 风险与回滚

- 路径穿越/重解析点/大小bomb：禁止绝对路径、`..`、重复成员、链接、超界展开和未知根布局；解包前限额，逐件比对包外固定manifest/checksum并对落地文件重新hash。
- 未授权信任提升：只读验证固定字段；绝不接受CLI `--force`/skip；无论manifest声明如何，未release clearance都不能发布/启动。
- 磁盘中断/重复执行：只写空目标或工具owner-token临时根；异常仅删除逐路径确认的私有staging，已存在目标拒绝覆盖；恢复由人工选择，保留旧目录。
- 回滚：移除新增根级脚本与说明并从组装器移除入口；数据库/API/服务未变更。保留CR、旧候选和验收记录。

## 验证计划

1. 合成正例：D盘隔离目标、外部预期SHA正确、完整目录落地且读回hash一致；重复执行拒绝。
2. 负例：错SHA、坏ZIP、绝对/穿越/重复/链接路径、manifest或清单不匹配、大小上限、已有目标、注入中断；不留下部分目标或删除非owner目录。
3. 对A35真实非发行候选做Windows 11 D盘隔离验收；确认状态仍为 `BLOCKED`，无SCM/service/API/listener、数据库、License secret读取或C盘写入。
4. hosted Windows workflow跑同一工具测试并重建带新入口的候选；重启和真实安装留待正式信任及可控目标环境，当前不得宣称通过。

## 实施前安全细化（2026-10-30）

A39 对当前 ZIP 的只读核查后，发现把可执行 bootstrap 脚本放进未签名候选包根目录会令用户在验证外层 ZIP 前先执行未验证代码，与“先验整包身份、再执行安装逻辑”目标冲突。按同一 CR 的安全目标改为：将可审查的离线接收/隔离暂存命令保留在公开源仓库，要求包外 hosted `verification-summary.json` 与完整 ZIP SHA-256 匹配；命令只调用现有受限暂存校验器、只写 `RUNNER_TEMP` 下非 C 盘新目录，生成 `installation_performed=false` 回执。第一步不把脚本嵌入候选ZIP、不发布到正式安装根、不注册或启动服务。此为实现位置细化，不改变产品/API/DB/License基线或安全门禁；后续若需自包含正式安装器，须另行具备可验证代码信任链。


## 执行环境变更（2026-11-02）

用户明确要求此后不在本机运行任何程序，所有运行均在模拟沙箱完成。A40验收已调整为 GitHub hosted Windows 2025 sandbox；临时目录必须在非C盘runner temp。该环境只能证明云端沙箱中的Windows Server 2025行为，不推定Windows 11兼容。此前Windows 11本机演练保留为历史证据，本轮及后续新运行不在本机执行。

## A40 云端验收结果（2026-11-02）

GitHub hosted Windows 2025 workflow run [41369734304](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41369734304) 完成：19/19定向测试通过；从A35 hosted run取得的ZIP摘要为 `94700239dc2218466087fd4beec90f9d34cd4a6c96ceed1049033df58342e2f2`，核对外部摘要后在D盘 `RUNNER_TEMP` 完成20,119项暂存。回执固定为 `HOSTED_WINDOWS_CANDIDATE_STAGING_PASS_LIMITED`，安装、服务启动、发行及法务放行均为false。A38 readiness报告维持5项阻断，父包诊断为BLOCKED/exit 2。证据artifact ID `13108667793`，SHA-256 `c3caf121738c27a678d0efc9b25030a12f5bf5f65aee625763f68761513f49aa`。

首次云端试跑暴露并修正三项执行偏差：A34要求RUNNER_TEMP保持D盘根目录，故只将TEMP/TMP指向该根并将证据放入其专属子目录；Windows临时合成输入必须继承D盘TEMP/TMP；预期的诊断exit 2须在成功断言后清零，避免Actions将安全拒绝误判为步骤失败。所有修复由后续同一专用workflow复验通过。全程未在用户本机执行程序；托管Windows 2025结果不推定Windows 11兼容。


## A44 readiness report 随包接入（2026-11-02）

按本 CR 的包级操作说明与不授权边界，A44 将现有非秘密输入登记器和只读报告工具纳入父包，模板及脚本均受父包逐文件SHA清单覆盖。hosted run [41376505925](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41376505925) 12/12 jobs成功：9缺项列示、完整合成登记仍不授权、非法值不回显、manifest/checksum不变；A17 29 API流与A34手动恢复均成功。内部父包SHA-256 `8e3e4e37224ad3653c2f2d758d024e23a5c6591fde89cb85efd375bc304f801d`。A44仅PASS_LIMITED，未安装或启动产品。两项实施偏差及处理详见A44前置/结果记录；新报告资源仅属于父包操作区，应用运行布局排除规则以显式路径清单更新且未知路径仍失败关闭。


## A45 就绪报告字段指导（2026-11-02）

A45为父包只读报告新增9项缺失引用的静态指导，注明需维护内容、证据来源和禁止输入项；不回显登记值，也不改变启动授权。Hosted run [41378263123](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41378263123) 全12 jobs成功，父包ZIP SHA-256 `e2858a6b6af852ada906e84671b539dee25c2571387940e4680346dd2c0256ca`、20,122 files；A17/A34和PG组合检查通过。仅PASS_LIMITED，Pilot/Gate/Release仍NOT_READY；不构成Windows 11新实测或产品安装。结果见 `docs/progress/plt-pkg-01-a09-p51-a45-field-guidance-result.md`。


## A46 中文可读就绪报告（2026-11-02）

PowerShell包内入口增加可选 `-Readable`，展示UTF-8中文状态和字段指导；默认JSON模式及exit code保持。Hosted run [41382282100](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41382282100) 12/12 jobs成功，真实父包 smoke 覆盖不完整/完整/无效三态；完整仍需独立核验、不授权，非法合成值不回显，manifest不变。ZIP SHA-256 `c9b6d945f359e6777396b6a12309c62b7deff141b0f6808f340d195a407164d3`、20,122 files。A17/A34/PG通过。仅PASS_LIMITED；正式信任及Pilot/Gate/Release未通过。首轮换行及覆盖偏差、处置详见A46记录。


## A47 责任角色与下一步提示（2026-11-02）

九项非秘密缺项各自附加固定职责角色和静态下一步，JSON/中文可读报告都展示；不代填、不访问外部系统、不改变授权。Hosted run [41383869172](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41383869172) 12/12成功，父ZIP SHA-256 `1db6e14e10fb878cf290add82cb69b5ebd387ccaca783c0da23e2c6d1452d370`、20,122 files；完整登记不授权，非法输入不回显，A17/A34/PG组合通过。仅PASS_LIMITED，Pilot/Gate/Release仍NOT_READY。


## A48 推荐处理顺序（2026-11-02）

就绪报告新增静态四组建议顺序：公钥/License信任、DB凭据范围、服务身份/ACL、TLS证书/域名/续期。JSON和中文模式一致显示当前仍阻断项；顺序只是操作建议，不授权或关闭验收。Hosted run [41386839114](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41386839114) 12/12成功，20,122文件父ZIP SHA-256 `8e642dc1c4393fdae80935622349b094122b18509816fc8ce4a9d7805aa48948`。零blocker完整登记合成分支仍不授权、要求独立核验；A17/A34/PG通过。仅PASS_LIMITED。


## A49 突出第一条待办（2026-11-02）

可读报告新增置顶第一条动作；JSON `recommended_first_action` 与列表第0项复用同一对象。零待办时显示仍需独立核验，不授权。Hosted run [41388401825](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41388401825) 12/12成功；父ZIP `07d74e91529ef35f3215dd6d5045a59152fc778345825df8aa37a0f49c88920c`，20,122 files；完整blocked、零blocker完整、无效三态和A17/A34/PG通过。仅PASS_LIMITED，Pilot/Gate/Release保持NOT_READY。
