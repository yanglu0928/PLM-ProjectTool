# PLT-PKG-01-A09-P51-A29：启动清单篡改抗性守门编码前检查

- 日期：2026-10-30
- 当前 Phase：Phase 2 Platform Core；CR-EXEC-002 Windows 11受控内部试用包关键路径
- 前置：P51-A28 hosted run 40981581644 为PASS_LIMITED；结果见`docs/progress/plt-pkg-01-a09-p51-a28-startup-coordinator-result.md`。
- 证据基线：当前包manifest仅表达所有启动信任前置为false；`start-trial.ps1`固定fail-closed；测试只覆盖manifest生成的正常值，尚未覆盖用户可编辑/截断/类型变化/阻断码缺项的清单篡改输入。
- 单一目标：对包内启动协调器增加篡改清单负例矩阵，验证修改manifest的状态字段、类型或阻断码不能使启动器越过固定拒绝，并且不会输出诊断中的路径/凭据、不会启动listener。
- 范围：启动清单校验测试、必要的启动守门代码、CI定向测试及结果文档。不得接线正向生产启动、真实Credential Manager秘密读取、License私钥、证书/私钥材料或业务API。
- 验收：hosted Windows runner D: RUNNER_TEMP中，围绕本轮自有临时候选创建独立拷贝；逐项篡改正式信任布尔值、数据库凭据状态/目标引用、服务ACL、TLS状态、blocker_codes与JSON类型，并验证每例以固定非敏感错误退出1、stdout空、指定loopback端口无listener；源候选hash保持不变，临时拷贝和进程清理完成。任何情况下不得把伪造的ready manifest当成功启动。
- 风险/差异：无冻结API、Schema、业务权限或产品Scope变化。为安全边界的测试覆盖增强，不产生数据迁移。若发现PowerShell宽松类型比较导致误接受，仅收紧校验并保留永久fail-closed；回滚为恢复原启动脚本和相应测试。
- 执行环境：仅GitHub hosted Windows runner；不在用户本机或C盘运行项目代码。

## 编码前结论

输入文件、守门脚本和当前manifest契约已核实；A29是当前启动包关键路径中独立且可在无正式密钥/客户资料条件下完成的安全任务。先在同一分支写入本检查，再实现并执行hosted负例矩阵。