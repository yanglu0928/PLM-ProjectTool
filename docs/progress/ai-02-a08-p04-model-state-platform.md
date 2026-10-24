# AI-02-A08-P04：Windows 模型安全状态写组合

日期：2026-10-02；状态：Windows11 隔离 PostgreSQL18.6 合成平台链 PASS。依据 DEC-673、CR-AI-004/005、P03 可选 HTTP。

Changed：只在显式 `--platform-write` 注入 Model `:set-state`；登录模式404、只读模式POST405。复用同账户数据库、License、Session、Audit、收据；不加入 AVAILABLE 或质量结论，不启动厂商调用。

Tests：`validation/ai-02-a08-p04-model-state-platform/verify.py` 验证三模式、写模式真实暂停v1/退役v2、原暂停重放仍v1、详情当前RETIRE、AVAILABLE422、普通用户404、License403、缺模型游标钥启动失败。首轮合成模型未插入必需能力行，GET 按设计返回503；修复测试夹具后重跑整链 PASS，生产投影未改。后端全量2052运行/3跳过；临时 PG 停止。开发 wheel SHA-256 `494a3e3b8e53ad1667cd3920599b498e63a4abdb62b935e03a85e15a6f1c6d32`。

Migration：无，复用0058。API：冻结 `:set-state` 的受限显式写装配，无 Breaking Change。兼容与回滚：撤路由组合可回退，有历史状态结果时保留向前修复。Known Issues：正式目标账户/Server2025/Debian、质量 Owner/AVAILABLE/真实 Provider Worker、Gate3/UAT/可用包未验。Next：独立 `AI-03-A01` Prompt 基础；AI-02 未全部关闭。
