# PLT-PKG-01-A09-P51-A34：当前父包在隔离云端目录的离线安装/升级演练编码前检查

- 日期：2026-10-30
- 前置：A31父包诊断、A32应用投影、A33启动失败诊断均已在hosted Windows runner完成PASS_LIMITED；A16已有较早候选的隔离安装/升级演练记录，必须先审计可复用性。
- 当前问题：当前完整父包候选已可构建、清洁解包并通过PG/A17流程，但尚未对当前候选执行安装/升级器路径演练；A16使用的候选版本不同，不能推定此父包布局兼容。
- 单一目标：在GitHub hosted Windows runner的D盘RUNNER_TEMP内，对A33当前父包执行受限离线落地/替换演练，验证目标路径 containment、现有目录保护、组件Hash和失败后清理/恢复边界。
- 前置审计：先读取A16/A26实现和对应Skill，确认是否已有可复用演练器；不重复造轮子。若现有脚本不接受当前parent-package artifact，在编码前记录最小差异与兼容/回滚计划。
- 范围：仅hosted Windows Server 2025自有临时根；只消费同run非发行parent candidate artifact。正向生产启动、真实License信任、服务安装和系统目录写入不在范围。试运行最终仍应由A33守门拒绝，且不启动服务/API/listener。
- 验收：所有写入路径均在D:\\a\\_temp本轮子目录；对ZIP、manifest、payload总数/Hash独立验证；模拟已有目标保护和受控失败清理；无C盘项目/候选运行，既有目标marker不变，临时目录清理；完整hosted job通过。
- 回滚：移除本轮生成的临时演练目录/辅助脚本，不修改已有安装；如果目标路径逃逸、已有目标变化或清理失败则停止并记录，不继续任何安装。
- 风险与限制：Server 2025 hosted runner只能证明当前Windows Server 2025临时路径行为，不能推定Windows 11设备兼容；Debian 13仍按用户指令跳过。没有正式公钥/License信任材料时，任何安装后启动仍应失败关闭。Pilot与Formal Release均保持NOT_READY。
- 编码前结论：需先完成A16/A26演练器可复用性只读审计；审计通过前不改产品/打包器代码。当前任务仅针对受控云端临时目录，不需要用户本机执行。


## 前置范围收敛（2026-10-30）

- A33 same-run smoke summary已报告candidate_staging PASS_LIMITED；只读检查确认 [0m `tools/stage_windows_parent_candidate_cloud.py` 已实现D盘RUNNER_TEMP直接子目录/非C盘限制、归档与逐文件Hash检查、现有目标拒绝、无发行状态和清理；`tools/smoke_windows_parent_package_pg_cloud.py` 已执行越界路径/既有目标负例，并实际解包当前20,119文件父包。因此原定“增加隔离落地/解包演练”已被A33同run覆盖，不重复开发或重复计验收。
- A34范围收敛为：只读审计A16安装/升级演练实现对当前parent-package布局的兼容缺口，随后如确有缺口，再为当前非发行父包增加D盘RUNNER_TEMP下可回滚的应用版本替换演练；保留data/config/license等既有标记、禁止C盘/系统目录、失败不自动启动服务。编码前先完成A16工具与证据审计，当前尚未编码。
