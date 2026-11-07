# PLT-PKG-01-A09-P51-A39：Windows 11 离线安装/升级/重启路径核查结果

- 日期：2026-10-30
- 状态：PASS_LIMITED（只读核查；未进行安装或重启）
- 前置检查：`plt-pkg-01-a09-p51-a39-offline-install-path-precheck.md`
- 候选：A35已验父包 ZIP，SHA-256 `94700239dc2218466087fd4beec90f9d34cd4a6c96ceed1049033df58342e2f2`，本机 D盘 `D:\\A35Temp\\current-parent.zip`。

## 核查证据

- ZIP 根目录仅含 `manifest.json` 与 `payload-sha256sums.txt`。运行时内容在 `payload/`，其根级操作入口为 `README-FIRST.md`、`check-startup.ps1` 与 `start-trial.ps1`；没有根级离线安装/升级入口。
- `README-FIRST.md` 明确称候选不是安装器或 Pilot Release，启动前置仍未齐全；只提供解包后的配置说明和只读阻断诊断。父包 manifest 为 `WINDOWS_PARENT_PACKAGE_NON_RELEASE_CANDIDATE`、`release_eligible=false`、`legal_clearance=false`、`formal_startup_ready=false`，含正式公钥/License、DB凭据、服务ACL、TLS五类阻断。
- 仓库已有安装根合法性检查和只读安装计划；`windows_offline_install_coordinator.py` 的正式安装分支会拒绝且不写正式根。A34/A35只验证非发行包隔离替换/失败隔离/手动恢复，不能替代安装器、重启或用户验收。
- 未在本机解包或运行父包；仅从 D盘ZIP流读取名称、README和manifest字段。没有重启正在使用的 Windows 11。

## 结论与下一步

离线安装、升级、回滚和重启的用户路径尚不存在。不能把候选ZIP或A34/A35隔离演练称作可安装程序包。下一项建立 `CR-PKG-012`，新增非发行 Windows 父包离线接收/完整性校验/隔离落地入口；在正式信任材料缺失时仅输出阻断、不注册或启动服务。用户本机测试限定 D盘隔离根，不触碰 C盘或现有产品目录。

本轮不改变 Gate/Pilot/Release 判定，均保持 NOT_READY。
