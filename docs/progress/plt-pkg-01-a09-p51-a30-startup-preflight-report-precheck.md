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


## 首轮 hosted 验收偏差（2026-10-30）

- Run 40985349086 的父包构建成功；clean extraction job在实际候选诊断报告断言处失败，错误为诊断进程没有满足预期的BLOCKED报告合同。发生在PG18临时数据库启动之前。
- 同一job中A29的7类启动manifest篡改守门已先行通过；未启动产品API/Caddy/PG，亦未读取Credential Manager秘密blob/License私钥。异常路径由smoke finally清理本轮D盘RUNNER_TEMP拥有的解包目录。
- 当前Harness只记录了通用错误，没有保存安全分类（进程退出码/输出形态）；因此不能把失败归因于产品输出格式还是PowerShell执行差异。本项不计PASS。
- 先记录偏差后调整：增加无原始正文/环境路径/秘密输出的分类证据（仅退出码、stdout是否为合法BLOCKED JSON、stderr是否匹配固定拒绝、字节长度），再由hosted Windows复验；若查明产品输出合同不符，只做最小修复，维持任何情况下不启动服务的约束。

- 后续run 40986507196增加安全分类后，诊断进程退出1、stdout为空、stderr为非空非固定拒绝；PowerShell脚本静态复核发现TLS证书与私钥共用manifest阻断码时，消息hashtable重复定义同一键。该错误由本次诊断实现引入，未触发服务/监听，隔离目录通过smoke异常清理；不计PASS。修正为单一TLS配置提示后重新hosted验证。

- 第三轮run 40987631545的诊断程序成功输出JSON，但 smoke 的完整字段断言失败，发生在PG initdb之前。核查发现测试期望仍将TLS证书与私钥拆成两码，而A28冻结manifest用单一TLS_CERTIFICATE_CONFIGURATION_NOT_VERIFIED表示两项；产品结果保持BLOCKED且未启动任何服务。先记录偏差，再同步测试期望到现有manifest契约，不扩大业务/安全范围；本轮不计PASS。
