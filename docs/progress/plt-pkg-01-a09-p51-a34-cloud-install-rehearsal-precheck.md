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
