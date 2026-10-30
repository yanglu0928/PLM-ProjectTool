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
