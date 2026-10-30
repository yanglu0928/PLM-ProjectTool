# PLT-PKG-01-A09-P51-A33：启动失败时显示安全前置诊断验收结果

- 日期：2026-10-30
- 状态：PASS_LIMITED（托管非发行候选受限验收；不是Windows 11设备验收或正式Release）
- GitHub Actions：https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41008231772
- PR #61：https://github.com/yanglu0928/PLM-ProjectTool/pull/61
- PR head：71fbd5b24db60abad3c00af27f4824929dfbf60d
- 托管工作流测试引用：612bf987d423501161533a8430066cd565a89ada；10/10 jobs成功。
- 环境：GitHub hosted Windows Server 2025；候选解包、临时数据库和工作目录均在D盘RUNNER_TEMP；未在用户本机运行项目代码。

## 验收证据

- 父包 smoke job 123910523879：清洁解包20,119个payload文件；父包ZIP SHA-256为 `104b8559ccf018846774f6c527dc6f9c7141e1623669a2a9c8b191b824655cf6`。
- 实际运行payload/start-trial.ps1：向stdout输出经白名单验证的BLOCKED JSON（六项阻断码），退出码仍为1，stderr为固定拒绝文案；监听器未启动，服务及产品API均未启动。
- 缺少check-startup.ps1和损坏manifest两种场景均保留固定拒绝回退；source manifest未改变。父包smoke同时报告A29七项manifest篡改矩阵与A30四项诊断输入篡改矩阵通过。
- 同run PG18.6/pgvector0.8.6临时数据库生命周期通过；临时资源在D盘托管runner范围内管理。
- 同run A17 job 123910809501：打包PlanVersion的Edge/HTTPS/临时PostgreSQL流程29次API操作成功；PlanVersion为IN_REVIEW，WBS/Requirement/Validation=(2,2,1)，Review/Round为IN_REVIEW，决定数为0，身份为合成测试身份。候选状态为PASS_LIMITED。
- 后端3,849项回归、前端测试与构建、Python嵌入式运行时、PG sidecar、父包组装和A17候选投影等同run任务全部成功。

## 实施偏差与修正

- 早期hosted运行依次发现子进程超时、诊断JSON未转发、清单路径正则误转义、阶段定位不足，以及本轮阶段标签编辑漏保留清单哈希赋值；这些记录均保留在本目录下A33编码前检查文档。
- 恢复哈希赋值后，hosted smoke仍在PowerShell Get-FileHash阶段回退。依据失败日志先登记，再改为.NET SHA-256流计算，继续使用相同SHA-256、同一清单摘要比较及诊断文件逐项摘要比较。
- PR #60在2026-10-30 05:09:30 UTC已由远端合并至main；本自动化未执行合并。随后发现的遗漏与修复记录在以最新main为基准的PR #61，不强推、不覆写main。

## 限制

此结果只证明当前托管非发行候选在启动被阻断时安全显示诊断。正式产品公钥/License信任、真实数据库凭据、服务账户/ACL、TLS、正向生产启动、Windows 11本机安装/重启/升级、客户UAT、Gate 3～7及正式多平台Release仍未通过。Pilot与Formal Release继续NOT_READY；不把合成身份或测试报告作为客户决定。
