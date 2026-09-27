# JOB-01-A05-P03：Windows任务列表独立加密游标密钥

2026-09-27 Phase2/编码前PASS，输入CR-JOB-005、P02加密cursor/current权限及既有Windows Vault/provider/加密恢复生命周期。只读固定KeyRef `job-list-cursor-v1`，不复用其他cursor或Secret主密钥、不默认创建；provider异常/缺失/非32byte静态启动失败。正式账户供给/独立口令备份仍operator职责，本次仅本账户临时引用验证。

DEC-277：显式resolver仅None才默认Windows provider，不让falsy测试Port触发意外fallback；无Schema/API/权限/依赖/License变化。临时UUID唯一引用确保事前不存在，备份仅在TemporaryDirectory，恢复原key旧密文token有效；错误口令不写Vault，恢复不能覆盖现存引用。测试最后清理本轮临时credential与备份，不碰正式引用。回滚撤新只读入口，后续运行接线前仍default404。

Changed/Files：entrypoints/windows_job_list_cursor.py固定专用KeyRef读取/codec装配，缺失/异常/错误长度仅ProductionJobListCursorStartupError静态报错。3新单位行为（含实际Windows Vault/备份恢复）；runtime Provider不生成、不导出、不轮换、不提供明文env/file fallback，正式运行组合尚未接列表。

Tests/Result WINDOWS_CURRENT_ACCOUNT_INTERNAL_PASS：Windows11/Python3.13.15全后端1213无失败（2既有权限跳过），另单独3新测试实际全部ok、无本项skip；falsy Port明确只读专用ref、错误类型/长度/Provider异常静态拒绝。真实本账户唯一job-list-test-UUID引用事前无key→加密备份+Vault供给→密文游标→覆盖恢复拒绝且原key不变→删own引用/缺失工厂拒绝→错误口令恢复拒绝且Vault空→恢复原key/旧token有效，最后删除own测试credential并确认不存在，临时备份目录已清理。未供给/读取/修改正式job-list-cursor-v1，未触碰用户凭据或外发。

P02真实PG当前Session/Doc双Scope分页权限HTTP回归重新通过：15成功/10拒绝/1空页延续，十三表无写及原上传回归。开发wheel666815 bytes/SHA256 `542dd5bf6d84f18df7612d7f6dd5e551e4dee4d10c439f0201c82e41277ad3d7`，非完整包。本轮测试无失败，最初猜测key CLI文件路径不存在后按实际secret_key_recovery.py读取，不改变实现。

正式供给：实际运行账户交互终端调用既有`python -m plm_assistant.entrypoints.secret_key_recovery provision job-list-cursor-v1 <绝对离线备份路径>`（口令隐藏输入、不放命令行）；export/restore同既有生命周期，备份与口令独立保管。这里只是操作说明，不代表已执行正式供给；新key不是旧key恢复。正式账户/异账户恢复与Server2025仍未验，Debian13暂缓且目标保留，性能/完整Owner/程序包/Gate待。

Next：P04实际Audit+Document列表原源/状态/混排分页矩阵，再P05 Windows两显式运行组合挂载；缺专用key必须拒绝启用，不替换测试key。无Migration/API/权限/依赖/升级，撤新只读入口回滚保历史。
