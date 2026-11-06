# CR-EXEC-037：SUR-07-A08 显式 PostgreSQL DLL 搜索路径

日期：2026-11-07  
状态：实施前记录；A08 未通过。

## 证据

Hosted run [42276408517](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42276408517) 的A08在完整校验提取的候选 staging 上，initdb.exe --version 探针完成成功；随后同一candidate投影到target layout，packaged platform-write 对 pgdata 执行完整initdb时返回3221225781/0xC0000135。故障诊断stage为PACKAGED_SMOKE_START，意味着前置version probe已通过。没有原始stdout/stderr；未定位具体DLL。同run A17成功，但不据此推断产品事实。

## 单点修正

只在A08 verifier调用 smoke 前，把将来target中同run候选的 runtime/pgsql/bin 与 runtime/pgsql/lib 两个固定目录前置到当前隔离Python进程PATH；实际initdb启动时，target布局已创建。保留原PATH其余内容，不输出路径，不改共享烟测/产品/安装包。此项验证是否为helper未显式搜索嵌入式PG DLL目录造成的差异。

## 验证、风险与回滚

Hosted Windows Server 2025 D盘同run非发行候选，继续运行完整 PG18、真实Edge/HTTPS、SurveyVersion业务流程、权限及License拒绝。安全摘要仍只允许固定阶段/marker/exit码。若0xC0000135消失但后续失败，按新证据单独处理；不得用version probe替代PG初始化。回滚仅删除PATH前置两项；本机/C盘不运行项目代码。


## 实施记录

已在A08 verify.py中验证目标根为 temp 的直属、ASCII、既有 rehearsal target 前缀和不存在，再将其 runtime/pgsql/bin 与 runtime/pgsql/lib 作为PATH前置项，原PATH末项保留。stage只读探针仍先按原PATH执行，便于区分candidate binary启动与target完整PG初始化；后续Hosted复验待完成。未修改产品或共享smoke工具。
