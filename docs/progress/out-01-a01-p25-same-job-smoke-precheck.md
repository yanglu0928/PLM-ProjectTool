# OUT-01-A01-P25 编码前检查：同一 Hosted job 的父包 PG18 smoke 对照

- 日期：2026-11-06
- 状态：编码前检查通过；同作业差分步骤待Hosted验收
- WBS：OUT-01-A01-P25（诊断切片，真实HTTP/Edge仍未通过）
- 冻结基线：API Contract V1、DB Schema V1、CR-OUT-021。仅修改Hosted验收工作流，不改产品代码、API、ORM/Migration、数据库模式、Publisher信任或安装包。
- 证据输入：run [42156574221](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42156574221) 中P25仍在initdb.exe启动前以 `3221225781 / 0xC0000135` 退出；独立 `Clean extraction and temporary PostgreSQL lifecycle smoke` 通过。CR-OUT-021已明确：恢复P25诊断时先在同一P25 job运行既有父包smoke helper，再采集安全白名单证据；不得重复猜测flags/PATH。
- 单一问题：在配置Python 3.13、Node 24且具备同run前端/PG sidecar/父包候选的P25 Windows Server 2025 job上下文中，已有 `tools/smoke_windows_parent_package_pg_cloud.py` 能否初始化并完成临时PG18/pgvector smoke？
- 实施：在P25现有父包/sidecar provenance及语法检查之后、P25自己的PG对照之前，使用同一候选ZIP和verification-summary，在新的 `RUNNER_TEMP` 直系目录中调用现有parent-package smoke helper；summary也只写 `RUNNER_TEMP`。helper非零立即失败关闭，不继续P25 initdb/HTTP/Edge步骤；helper成功才运行既有P25流程，不改其输入/参数。
- 独立验收：Hosted run必须显示P25 job同一个Windows runner中helper退出码0、bounded summary通过；随后观察P25 initdb/HTTP/Edge既有步骤。若helper通过但P25失败，结论只表明同job具备PG生命周期能力而P25后续步骤仍失败，按日志设计下一个可判别切片；不得宣称真实HTTP/Edge/P25通过。全链其他job结果单独记录。
- 安全/数据：只用本run非发行父包与合成数据库；无客户数据、秘密、外部API、插件执行、生产服务或数据库写入。Hosted `TEMP/TMP/RUNNER_TEMP`保持D盘。不会清理本机C盘Temp。
- 风险/回滚：额外执行一次已通过的临时父包 smoke，增加Hosted耗时；不改变父包归档或业务状态。回滚仅移除该job步骤及对应追踪文档。
- Secret检查：新增文本仅含仓库路径、公开run URL、固定helper参数名和安全结论；不含密钥、账户凭证、客户数据或运行时原始环境值。
- 决定：PASS_WITH_LIMITATION，可实施该单变量Hosted job差分。该步骤诊断PG装载/执行能力，不替代P25真实HTTP/Edge验收，Gate、Pilot和Release状态不变。


## Hosted结果与重新编码前记录（run 42159992981）

P25同一job父包smoke已成功，但smoke从父包候选原始PG路径、原始PATH启动，并使用其既有参数；P25精确对照脚本从同run父包解包PG子集，移除Node PATH后initdb失败。父包/sidecar 1,627项内容完全一致。二进制路径、用户/参数及PATH条件没有全匹配，不能把现象定为Node PATH根因。

### 下一项编码前检查

- 单一问题：Node目录过滤是否为P25 initdb失败的因果因素？
- 最小实验：同一P25 job、同一父包PG payload解包目录和同一 `initdb.exe`，使用完全相同的P25参数，分两个新的D盘数据目录分别执行原始PATH与删除Node目录后的PATH。只报告PATH过滤布尔值/计数、退出码、stdout/stderr字节数、PG_VERSION是否产生；不得输出PATH、环境变量值、错误原文或数据库内容。
- 判定：仅过滤PATH成功才支持该因素；结果相同则排除PATH过滤充分解释并转查二进制装载位置差异。P25仍须真实HTTP/Edge通过才算验收。
- 风险、回滚：只改Hosted比较器/摘要；无API/Schema/产品代码变化。仅合成临时库，D盘RUNNER_TEMP直接子目录；不开服务、不做业务写入、不调用外部API或插件。本机不运行代码；失败临时目录留在一次性Hosted runner。
- Secret检查：不打印任意环境变量值，不新增密钥/客户数据。
- 决定：PASS_WITH_LIMITATION，可实施此Hosted单变量双臂探针；P25仍BLOCKED_DIAGNOSTIC。
