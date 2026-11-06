# CR-EXEC-034：SUR-07-A08 临时根对齐 PG18 所有权约束

日期：2026-11-07  
状态：实施前记录；A08 未通过。

## 证据与原因

Hosted run [42266017538](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42266017538) 的A08通过同run候选校验、D盘边界、语法和CR-EXEC-033 staging提取，进入现有 packaged smoke。安全摘要调用帧：verify.py:301 → smoke_current_app_packaged_https.py:226 → smoke_packaged_platform_write_https.py:330 → smoke_packaged_pg18_migration.py:109，异常ValueError，固定stage为 PACKAGED_SMOKE_START。

只读源码显示 smoke_packaged_platform_write_https.py:330 调用 _migration_temp_root；该函数要求 PLM_P51_TEMP_ROOT 的解析路径位于 RUNNER_TEMP/<父目录名以 plm-p51-a27- 开头>/PLMToolTemp。A08运行根为 plm-sur-a08-<run id>，故现有路径被拒绝。失败在PG18数据目录创建/进程启动之前，不是数据库或产品失败证据。

## 单点修正

仅将A08 Workflow的owned runRoot与精确清理叶名称从 plm-sur-a08-<run id>改为 plm-p51-a27-a08-<run id>。PLMToolTemp继续为该runRoot的唯一子目录，PLM_P51_TEMP_ROOT仍指向此目录；保留非C盘/ASCII/唯一性、父子关系清理校验、摘要路径和其他plm-sur-a08依赖/结果命名不变。

无业务代码/API/Schema/Migration、验收门槛或产品包变更。

## 风险、回滚与验证

风险仅为路径契约对齐；helper继续执行原有强边界验证。回滚为恢复A08 Workflow中的旧runRoot名和对应叶名。不触碰其他任务的目录。Hosted Windows Server 2025 D盘完整复验需通过staging、isolated PG18、Edge/HTTPS、SurveyVersion/A12断言与License拒绝标记，并清理精确owned根；原始日志不上传，合成数据，无客户外发。


## 后续托管证据（2026-11-07）

run 42269084207确认前置 staging 修正生效，且A08运行根满足 _migration_temp_root 后，initdb.exe仍以非零码失败。当前安全摘要仅含RuntimeError和帧 verify.py:301、smoke_current_app_packaged_https.py:226、smoke_packaged_platform_write_https.py:357、smoke_packaged_pg18_migration.py:66。helper的通用异常对象包含`command basename, exit code, captured output`结构；实际A08包装器没有暴露消息体，故需要CR-EXEC-035受限提取命令basename/exit code。此失败尚未证明helper输出内容或具体PG原因。
