# CR-EXEC-015：映射父包 provenance 文件至隔离 HTTPS 验收布局

- 日期：2026-10-28
- 状态：实施中
- 来源：CR-EXEC-013 将经哈希验证的父包 provenance 文件保留在 A17 候选中；A17 包内 HTTPS smoke 使用精确 allowlist 映射，拒绝了该根目录文件，导致实际旅程未启动。
- 证据：hosted run 40643422039 的 A17 job 在 tools/plan_windows_unified_caddy_install.py -> tools/rehearse_windows_unified_pg18_layout.py 的 target_name 中抛出 unmapped candidate payload family；父包组装、投影测试、候选构建和 PG smoke 已通过。
- 目标：保留 provenance 内容，并为 provenance/ 增加一个受安全函数检查的明确目标前缀映射，不扩大其他未知根目录或路径的映射范围。
- 基线差异：隔离 Windows HTTPS rehearsal 的只读文件映射扩展；不改变产品包 payload、业务 API、依赖、服务启动权限、信任状态或发行资格。
- 风险：若映射前缀过宽可能允许意外源路径写入 rehearsal。通过安全归一化、仅接受 provenance/ 后代路径、目标路径碰撞检查和原有完整哈希核对控制风险。
- 回滚：撤销 provenance 映射与对应测试；保留失败 run 与变更记录。
- 验证计划：先增加精确 provenance 正向映射及路径/目标碰撞测试，再运行 Windows hosted A17 全流程；确认 provenance 文件全部映射、hash 对照、业务流程日志与临时目录清理证据。未达到 Edge/HTTPS/PG 的既定 markers 不关闭 A27。
- 安全：只在 hosted Windows runner 使用合成资料，不运行用户本机代码、不外发 Secret/客户数据。
