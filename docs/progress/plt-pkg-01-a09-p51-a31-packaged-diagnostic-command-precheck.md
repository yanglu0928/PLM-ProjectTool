# PLT-PKG-01-A09-P51-A31：实际父包运行README诊断命令编码前检查

- 日期：2026-10-30
- 前置：P51-A30诊断脚本已打包；run 40988858723在隔离副本执行功能和篡改矩阵PASS_LIMITED。
- 当前证据差距：A30从真实候选复制诊断脚本和manifest到独立case目录后运行，尚未在清洁解包的原始payload路径直接按README命令调用；包内路径和当前工作目录联动未形成独立验收。
- 单一目标：hosted Windows D盘清洁解包后从父包根目录执行README所载确切命令，确认脚本按包相对路径读取manifest，输出BLOCKED/阻断项，exit=2，且不启动服务/监听。
- 范围：扩展现有parent PG smoke的文档命令验证与结果字段；必要时仅修复README调用路径。保留A28/A29固定启动守门和A30阻断报告；不改变业务API/Schema/License、不读取真实Secret、不启产品服务、不写入已安装位置。
- 验收：使用实际候选archive完整清洁解包；从解包根目录使用README的powershell命令原样运行；断言exit=2、stdout为稳定BLOCKED JSON且含所需reason、stderr为空；伪造/缺失manifest仍统一拒绝；产品端口未监听、源候选archive/hash不变、临时目录清理。
- 回滚：仅本smoke扩展/README路径必要修复可回滚；已打包诊断工具保持只读和永远不声明release ready。
- 执行环境：只用GitHub hosted Windows Runner的D: RUNNER_TEMP，不在用户本机/C盘运行。

## 编码前结论

当前限制是调用方式尚未被按文档在实际清洁解包根复验；不依赖真实信任或客户数据，属于Pilot交付链可独立完成的Windows包可用性检查。先写入本检查再实施。
