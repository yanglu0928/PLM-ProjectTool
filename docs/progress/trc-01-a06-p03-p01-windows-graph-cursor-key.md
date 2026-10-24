# TRC-01-A06-P03-P01：Windows Trace 图游标独立密钥来源

日期：2026-10-02；Phase 2；状态：**Windows 11 当前账户内部来源 PASS，正式目标账户供给未执行**。输入 P02-P02 AES-GCM 游标、已有 Windows Vault/交互式密钥生命周期、CR-TRC-002；决策 `DEC-20261002-611`。冻结 Gate 2 原提交不修改。

新增只读组合入口，固定专用 KeyRef `trace-graph-cursor-v1`，从当前进程登录账户 Windows Credential Manager 解析精确32字节密钥。缺失、错长、Provider异常均返回安全启动错误，不把底层路径/异常向外传，不自动生成、不复用其他密钥、无环境变量或明文文件回退。普通应用及当前 Windows 平台模式尚未挂通用 Trace 图路由，因此本项没有启动前置变化。

验证：定向3/3；真实 Windows 11 当前账户使用唯一 `trace-graph-test-UUID` 临时引用：事先确认不存在→加密备份并供给→生成游标→覆盖恢复拒绝且原密钥不变→删除**仅该测试引用**后入口拒绝→错口令恢复拒绝→正确恢复后旧游标可解→最终删除临时引用并确认不存在；备份临时目录清理。未读取/创建/覆盖正式 `trace-graph-cursor-v1`。后端全量1879项运行/3跳过/无失败；开发wheel SHA-256 `7f8d4648ca1dccbf53ffea7d9f677efbeffe1e1816df1bfa79fdb170deec68fd`。

兼容/升级/回滚：只新增入口与测试，无公开API、Schema/Migration、新依赖或历史数据修改；不装配入口即可回滚。未来挂正式图HTTP前，实际运行账户须通过既有隐藏口令的交互式 `secret_key_recovery provision trace-graph-cursor-v1 <绝对离线备份路径>` 供给，备份与口令分开保存并做目标账户恢复演练；这里**未执行**正式供给，不把本账户临时成功当正式发行通过。CR-TRC-002 的三字段引用 Owner Scope 解析仍缺，通用图HTTP继续关闭；Server 2025/Debian、License正式信任、性能/UAT/Gate/发行包仍待。
