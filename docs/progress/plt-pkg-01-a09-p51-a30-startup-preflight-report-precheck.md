# PLT-PKG-01-A09-P51-A30：启动前置诊断报告编码前检查

- 日期：2026-10-30
- 当前 Phase：Phase 2 Platform Core；CR-EXEC-002 Windows 11受控内部试用包关键路径
- 前置：P51-A28/A29已在hosted Windows候选包证明启动前置缺失与manifest篡改时失败关闭；正式产品信任材料仍缺，不能正向启动。
- 当前体验问题：启动器为了不泄露细节，对所有拒绝输入都输出统一固定信息；包manifest已有非秘密阻断码，但运维/试用人员无法快速看到本候选缺少哪些准备项。
- 单一目标：新增只读的包内启动前置诊断入口，严格验证manifest schema并输出稳定、非秘密的阻断项报告；正式候选仍显示BLOCKED并退出非零，不能启动服务或声称ready。
- 范围：新增一个PowerShell诊断脚本、D盘hosted smoke中的成功/篡改输入检查、结果记录。不得放宽start-trial fail-closed，不读取Credential Manager blob、不读取私钥/证书、不探测客户文件、不启动数据库/API/Caddy或打开listener，不改变API/Schema/License/权限。
- 验收：对真实同源候选manifest，报告所有当前未验证的启动前置字段和blocker codes；输出不得包含绝对路径、秘密值或运行环境变量。对缺失/额外字段、JSON类型错误及伪造ready/license/legal字段均安全拒绝/保持BLOCKED；exit code非零，stdout/stderr合同固定；确认没有启动进程或监听、原候选字节hash不变且清理本轮目录。
- 风险/回滚：无迁移/API breaking change；诊断入口仅辅助内部准备，不是正式配置或release资格判定。回滚删除独立诊断入口及验证调用，原A29启动守门保持不变。
- 执行环境：所有脚本/程序仅在GitHub hosted Windows runner的D: RUNNER_TEMP执行；不在用户本机/C盘运行。

## 编码前结论

该诊断可复用A28显式非秘密metadata与A29严格失败关闭边界，解决操作可读性问题且不需要任何真实密钥或客户数据。检查已完成，下一步在本分支实现并由hosted runner验证。
