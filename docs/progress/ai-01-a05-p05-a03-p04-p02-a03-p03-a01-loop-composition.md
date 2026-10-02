# AI-01-A05-P05-A03-P04-P02-A03-P03-A01：Windows 探针循环组合

日期：2026-10-02；状态：限定范围 PASS；依据 CR-AI-003、DEC-20261002-662、ADR-007/012/013。

未发布工厂从同一受控 Bootstrap、当前账户数据库/License/SYSTEM/Vault 的单次 Worker 取得有维护准入的数据库运行时，装入 `ProviderProbeWorkerLoop` 并生成固定格式 WorkerRef。缺准入时释放数据库且错误不回显信任材料。构建不调用 `run_once`，不注册服务、不挂 Test/Activate 路由、不触发外发。

Win11 单元定向9项；`validation/ai-01-a05-p05-a03-p04-p02-a03-p03-a01-loop-composition/verify.py` 在新隔离 PG18 下证明持维护锁覆盖真实 Job/SecretStore/本机合成 TLS/成功与失败发布和审计，排他锁在运行时不可取得。后端2025项运行/3跳过，开发 wheel SHA-256 `9a19bb3fc4bbf49ddcfa5ba82863b88f6274de99f5b0d4689e055ab13a73c648`；测试簇已停止。

无 Migration/公开 API/SCM 名称变化；撤未挂载工厂即可回退，Job/审计历史保留。A02 须将真实 runner、第四固定身份、命令计划/安装/只读盘点/对账同步接通，A03 实机目标账户验证；当前仍不能宣称可安装服务或 Gate 3 通过。
