# AI-02-A06：Windows 模型创建显式写组合

日期：2026-10-02；状态：Windows11 隔离 PostgreSQL18.6 合成平台链 PASS。依据 DEC-669、A05 可选创建合同及既有显式写组合。

Changed：AIModel POST 只注入 Windows `--platform-write`；登录专用模式 404、显式只读平台 POST 405。复用现有当前账户数据库/License/Session/Audit/收据，不新增模型外发或自动可用化。

Tests：`validation/ai-02-a06-model-create-platform/verify.py` 在隔离 PG18 验证三模式、写模式真实管理员201/同 Key重放/GET、普通用户404、License403及缺模型游标钥启动失败；这也补齐 A04 只读/写组合与PG整链验证。后端全量2047运行/3跳过；临时 PG 停止。开发 wheel SHA-256 `ef4ba16aeb3f4ed0ddb6a8bca78f76bf4617689003d8714afb2ecc6c8f598741`。

Migration：无。API：冻结 POST 的显式写装配，无 Breaking Change。兼容与回滚：未供给正式目标账户信任/模型游标钥不能启动显式平台；撤模型创建路由组合可回退，历史数据保留。Known Issues：正式目标账户/Server2025/Debian、质量证明 Owner/模型状态与实际调用、Gate3/UAT/可用包未验。Next：`AI-02-A07` 模型质量证明关联及状态转换前置核查；前置不足时保持暂停并转向独立工作项。
