# PLT-PKG-01-A09-P51-A25：Windows启动守门实施记录

- 日期：2026-10-28
- 状态：IMPLEMENTED_AWAITING_HOSTED_VALIDATION
- 前置审查：docs/progress/plt-pkg-01-a09-p51-a25-launch-coordinator-precheck.md
- 实施：父包中新增 payload/start-trial.ps1；脚本检查候选manifest的类型、非发行/未法务放行状态、formal_startup_ready、公钥资源状态及阻断码。在当前父包明确缺正式产品公钥且formal_startup_ready=false时，脚本在启动任何API/Caddy子进程前以固定错误退出。
- hosted smoke：清洁解包后运行包内guard，断言exit 1、stdout为空、stderr固定为“Packaged production startup blocked; trust prerequisites are not ready.”；回环端口仍可绑定。Credential内容未读取/输出；API、Caddy和PG均不由guard启动。
- 安全边界：本次没有添加密钥、证书或Credential。正向生产启动路径未实现/未验，Caddy HTTPS、服务账户/ACL及正式信任未就绪；manifest维持release_eligible=false/legal_clearance=false。此候选不可视为Pilot或正式发行。
- 运行：只在本次提交触发的GitHub hosted Windows workflow执行，D盘runner临时目录；用户本机不运行。
- 验证：等待新的hosted Windows jobs及artifact日志；当前实现不得标PASS。
