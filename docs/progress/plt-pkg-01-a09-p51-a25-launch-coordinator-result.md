# PLT-PKG-01-A09-P51-A25：Windows启动守门实施记录

- 日期：2026-10-28
- 状态：IMPLEMENTED_AWAITING_HOSTED_VALIDATION
- 前置审查：docs/progress/plt-pkg-01-a09-p51-a25-launch-coordinator-precheck.md
- 实施：父包中新增 payload/start-trial.ps1；脚本检查候选manifest的类型、非发行/未法务放行状态、formal_startup_ready、公钥资源状态及阻断码。在当前父包明确缺正式产品公钥且formal_startup_ready=false时，脚本在启动任何API/Caddy子进程前以固定错误退出。
- hosted smoke：清洁解包后运行包内guard，断言exit 1、stdout为空、stderr固定为“Packaged production startup blocked; trust prerequisites are not ready.”；回环端口仍可绑定。Credential内容未读取/输出；API、Caddy和PG均不由guard启动。
- 安全边界：本次没有添加密钥、证书或Credential。正向生产启动路径未实现/未验，Caddy HTTPS、服务账户/ACL及正式信任未就绪；manifest维持release_eligible=false/legal_clearance=false。此候选不可视为Pilot或正式发行。
- 运行：只在本次提交触发的GitHub hosted Windows workflow执行，D盘runner临时目录；用户本机不运行。
- 验证：等待新的hosted Windows jobs及artifact日志；当前实现不得标PASS。


## 首轮托管验证偏差

- Run 40619189190：基础构建、PG18、前后端测试、embedded backend和父包组装成功；D盘smoke在包内 `start-trial.ps1` 固定失败响应断言处失败。产品API入口只执行预期的无凭据拒绝进程，没有打开listener；Caddy与临时PostgreSQL阶段尚未开始。失败日志未输出子进程stderr，暂不能区分PowerShell解析异常与输出合同差异。
- 复核发现：smoke在前置启动探针异常时尚未进入PG生命周期的清理 `finally`，因此本次runner临时解包根可能仅由runner回收。下次代码提交先加异常安全清理及有限诊断（内容限runner生成的非敏感固定脚本输出），再重跑；不得将run 40619189190计为通过。
