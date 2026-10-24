# AI-01-A05-P05-A03-P04-P01 受控部署探针策略来源

- 日期：2026-10-02；Phase 2；输入 CR-AI-002、现有 `EndpointProbePolicy/Registry` 与 Bootstrap YAML。P04 前置缺口已登记，P01 可独立验证。
- Changed：受控非秘密 Bootstrap 配置增加最多 16 条 `ai_probe_policies`；严格六字段、引用唯一；独立部署工厂转换不可变 Registry，缺失/不安全或类型错误固定消息失败关闭。进程启动快照，不从 Provider API 接收 URL；更新须重启并重新执行 Provider Test。
- Files：Bootstrap 配置与示例、AI 策略工厂及单元测试、决策/CR/状态/版本记录。Migration：无。API：无。Architecture：无变更，不调用厂商或外发。
- Tests：定向 5/5；Windows 11 后端全量 2006 运行/3 跳过；开发 wheel SHA-256 `92609fefc0dd1a01e873ba37a1302c9ea2629d1e45aadbe265711785a878c03f`。涵盖 YAML 实际解析、固定探针、缺失、重复/额外字段、Secret 字段、不安全 URL 和不支持 Kind。无真实外发。
- Result：本 WBS PASS；P04 仍 PRECONDITION_BLOCKED，正式路由保持 404。Known Issues：目标账户配置 ACL/正式外发目的地、Test/Worker/Activate 同源组合、Server 2025/Debian、POC-03 质量/Gate/UAT/可用包未验。
- Next：`AI-01-A05-P05-A03-P04-P02` 让 Windows Test 提交与 Worker 共用此策略来源并做失败关闭组合验证；随后再重检激活装配。
