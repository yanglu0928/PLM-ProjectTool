# PLT-PKG-01-A09-P51-A31：实际父包README诊断命令验收结果

- 日期：2026-10-30
- 状态：PASS_LIMITED（专项父包命令验收通过；非发行、非Windows 11设备验证）
- Hosted run：https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/40992356658
- 验收作业：Clean extraction and temporary PostgreSQL lifecycle smoke，job 123860726604，success。
- 云端边界：GitHub hosted Windows Server 2025 runner，候选解包/数据库工作区位于 D:\ RUNNER_TEMP；本机未运行项目代码。
- 候选：父包 payload 20,119文件，归档 SHA-256 10eca56d28e3c3a137298bc9b0a1c9811e33654e513bfc2e174e22108157acc6；run内同源构建。
- 实际 README 命令：从清洁解包父包根目录执行 powershell -NoProfile -File .\payload\check-startup.ps1。exit=2，stderr为空；状态 BLOCKED，release_eligible=false，legal_clearance=false，输出为manifest推导的非秘密阻断报告。产品监听未启动/未发现。
- 负例：4类诊断manifest变体均以空stdout、固定拒绝stderr和exit=2失败关闭；源manifest未变。原A29 7类启动manifest篡改矩阵继续通过。
- 同作业的PG18.6/pgvector0.8.6临时数据库初始化、查询、停止与临时目录清理通过。正式信任源未使用，产品API/服务未启动。
- 全量依赖回归：后端3,849项通过；前端、嵌入式运行时、父包组装和临时PostgreSQL smoke均成功。
- 工作流后续独立A17 job失败：投影严格映射未识别新增父包文件 payload/check-startup.ps1。该组合缺口已登记为P51-A32，故本run不是全绿。
- 限制：不代表Windows 11设备、正式安装、真实公钥/License信任、Gate或Release验收。Pilot/Gate 3/正式Release仍NOT_READY。
