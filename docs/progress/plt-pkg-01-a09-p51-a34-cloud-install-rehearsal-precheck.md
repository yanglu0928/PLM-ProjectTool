# PLT-PKG-01-A09-P51-A34：当前父包在隔离云端目录的离线安装/升级演练编码前检查

- 日期：2026-10-30
- 前置：A31父包诊断、A32应用投影、A33启动失败诊断均已在hosted Windows runner完成PASS_LIMITED；A16已有较早候选的隔离安装/升级演练记录，必须先审计可复用性。
- 当前问题：当前完整父包候选已可构建、清洁解包、D盘受限staging并通过PG/A17流程，但尚未证实既有隔离安装/升级演练可消费当前parent-package布局；A16候选版本不同，不能推定兼容。
- 单一目标：在GitHub hosted Windows runner的D盘RUNNER_TEMP内，复用或补齐A16隔离安装/升级演练，使当前parent-package候选在一次性应用根目录完成可回滚的版本替换，并验证data/config/license等用户状态标记保留。
- 前置审计：先读取A16实现/验收记录及Release Skill，确认安装器输入布局、根目录边界、替换/失败恢复语义；staging helper A33已复用，不重复实现。若A16没有可复用演练器，在编码前记录最小方案、回滚和验证计划。
- 范围：仅hosted Windows Server 2025自有临时根；只消费同run非发行parent candidate artifact。正向生产启动、真实License信任、服务安装和系统目录写入不在范围。试运行最终仍应由A33守门拒绝，且不启动服务/API/listener。
- 验收：只触及D:\\a\\_temp本轮拥有的应用/备份根；验证升级前后data/config/license/plugins marker保持一致、替换失败不自动启动服务并可显式恢复旧app/runtime、临时备份/进程/目录清理；完整hosted流程通过。
- 回滚：移除本轮生成的临时演练目录/辅助脚本，不修改已有安装；如果目标路径逃逸、已有目标变化或清理失败则停止并记录，不继续任何安装。
- 风险与限制：Server 2025 hosted runner只能证明当前Windows Server 2025临时路径行为，不能推定Windows 11设备兼容；Debian 13仍按用户指令跳过。没有正式公钥/License信任材料时，任何安装后启动仍应失败关闭。Pilot与Formal Release均保持NOT_READY。
- 编码前结论：A33已覆盖父包D盘staging；A34只在A16审计确认存在当前父包兼容缺口后实施安装/升级演练适配。真实License trust不满足时launcher仍应失败关闭；不运行用户本机代码。


## 前置范围收敛（2026-10-30）

- A33 same-run smoke summary已报告candidate_staging PASS_LIMITED；只读检查确认 `tools/stage_windows_parent_candidate_cloud.py` 已实现D盘RUNNER_TEMP直接子目录/非C盘限制、归档与逐文件Hash检查、现有目标拒绝、无发行状态和清理；`tools/smoke_windows_parent_package_pg_cloud.py` 已执行越界路径/既有目标负例，并实际解包当前20,119文件父包。因此原定“增加隔离落地/解包演练”已被A33同run覆盖，不重复开发或重复计验收。
- A34范围收敛为：只读审计A16安装/升级演练实现对当前parent-package布局的兼容缺口，随后如确有缺口，再为当前非发行父包增加D盘RUNNER_TEMP下可回滚的应用版本替换演练；保留data/config/license等既有标记、禁止C盘/系统目录、失败不自动启动服务。编码前先完成A16工具与证据审计，当前尚未编码。

## A16 复用性审计与实施前确认（2026-10-30）

### 编码前检查

| 字段 | 结论 |
|---|---|
| 当前 Phase | Phase 2：Platform Core / `CR-EXEC-002` Windows 11 Pilot 关键路径 |
| 当前 WBS | `PLT-PKG-01-A09-P51-A34` |
| 输入基线 | A33 成功证据 run `41008231772`；当前父包 artifact `12955978718`；A31 父包 artifact `12951373170`（run `40995913354`）；A16 演练源码及结果；`CR-EXEC-002`。两份父包均为带明确非发行状态的同仓库 Actions artifact。 |
| 前置任务 | A31/A32/A33 hosted Windows 验收通过；A16 实现与证据已审计；A33 staging helper 已覆盖归档解包及Hash校验。 |
| 涉及模块 | 仅 hosted 包装验收工具、独立验证 runner、GitHub Actions cloud workflow 与进度文档；不改产品运行时代码、服务安装器、API、数据库、License 或客户数据。 |
| 涉及实体 | 已完成 A31 候选包、同 run 当前候选包、各自已验证 staging inventory、一次性安装根和四类合成持久标记。 |
| 涉及 API | 无产品 API；安装后只调用 A33 launcher 的 fail-closed 路径，预期输出 BLOCKED、退出码 1、无 listener/service/API。 |
| 涉及权限 | workflow `GITHUB_TOKEN` 增加只读 `actions:read`，仅用于下载同仓库已完成 A31 父包 artifact；工作区限定本次 hosted runner 的 ASCII D 盘 `RUNNER_TEMP`。 |
| 验收标准 | 以 A31 旧候选初始化临时安装根，再用当前父包替换 `payload` 与根 manifest/checksum；data/config/license/plugins 合成标记 Hash 不变；失败注入期间新版保持活动，只有显式 restore 才恢复旧候选并隔离失败版；新版启动命令仍产生 A33 预期的六项 BLOCKED、安全JSON、exit=1且无服务/API/listener；来源候选/清单未变、staging/安装/备份目录清理完成。 |
| 风险 | Actions artifact retention 到期会阻断 A31 输入；依靠既有单仓库、非发行候选和同仓库只读 token，不访问用户设备、正式安装根、客户数据库或 C 盘。Hosted Windows Server 2025 证据不等同 Windows 11 实机验收。 |
| 回滚/恢复 | 产品安装与系统状态不触碰。失败场景只在随机新建的 runner temp 根注入；明确演示手动 restore，不做自动回滚；外层 finally 仅清理本轮 owner-token 根，任何路径校验或清理失败均使 run 失败。 |

### 审计发现与范围决策（先记录，后编码）

- `tools/rehearse_current_app_directory_upgrade.py` 的稳定核心是显式备份 runtime/app、切换后失败不自动回滚及单独 `restore_previous()`；可借鉴该事务顺序。
- `validation/plt-pkg-01-a09-p51-a16-upgrade-launch-integration/verify.py` 固定 Windows 11、本机 `D:\PLMToolTemp`、两份 Current App ZIP/stage、SHA 与旧配置映射。因此不能直接用于当前父包 artifact 或 hosted `RUNNER_TEMP`。
- 当前父包的 A33 `stage_candidate()` 已验证 manifest、逐文件 SHA、路径与非发行态，并在实际归档中完成清洁解包。升级演练应消费这项验证后的两个独立 staging；避免重复实现 ZIP 解包或降低校验强度。
- 变化仅为验收工具适配：从 A16 的固定 Current App 输入改为同仓库 A31→当前父包输入，且把执行位置固定在 hosted D 盘。冻结产品基线、交付范围和正式安装语义不变，不需新增产品 CR；差异、Artifact来源和验证结果保留在本记录及 A34 结果。
- 编码计划：新增父包专用、限定 `RUNNER_TEMP` 的可回滚演练工具及定向单测；在 `cloud-sandbox-validation.yml` 新增 hosted Windows job，下载 A31 已验证候选及同 run 当前候选并执行升级/失败恢复/launcher 拒启验收；workflow 仅加 `actions:read`。编码/文档改动在 D 盘项目 checkout 中完成，所有项目代码和测试只由 GitHub hosted runner 运行，不使用本机 C 盘 Temp。
- 该验收只证明 Server 2025 hosted runner 的受控目录替换与失败恢复行为，不能据此关闭 Windows 11 设备安装/升级、Gate、Pilot 或正式 Release。
