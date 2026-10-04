# AI-02-A02：AIModel 内部首次登记命令

日期：2026-10-02；状态：Windows11 / 隔离 PostgreSQL18.6 内部链 PASS。依据 DEC-665、冻结 DM-04/API-03 和 Schema 0057。

Changed：新增不可变 `AIModelDefinition`、受权内部 `AIModelCreateService` 与 SQLAlchemy Repository。两次当前部署管理员 Session/CSRF 检查夹持 License Guard；写事务内以 actor/operation-scoped 幂等收据锁定请求，锁定并核对 Provider 当前配置与 CHAT/EMBEDDING/RERANK/结构化能力，插入初态 SUSPENDED 的模型及能力声明，并与 Audit/收据原子提交。同 Key/同载荷返回原 ModelId，换载荷冲突；相同语义不同 Key 由 PostgreSQL 唯一约束安全拒绝。历史重放不表示 Provider 仍可用。质量证明尚无独立 Owner 证明适配器，非空质量引用失败关闭；不写假的质量结果。

Tests：定向单元3项拒绝畸形身份、Secret 表示泄漏及未证实质量引用；`validation/ai-02-a02-model-create/verify.py` 在隔离 PG18.6 上验证真实管理员/普通用户/CSRF/许可、Provider 能力与不存在/退休、CHAT 结构化能力、EMBEDDING 初态、重复语义、同 Key 并发重放/换载荷冲突、Audit 故障完整回滚与用户停用后拒绝。后端全量2035运行/3跳过。临时 PG 已停止；开发 wheel SHA-256 `a25716a89929f2469ab578a7c6b4337b92fdb3c0d872d62fbd87ac9dd26244d0`。

Migration：无，复用0057。API：无，未挂生产组合/路由。兼容与回滚：无新依赖或冻结 API 变化；可撤未挂内部命令，有历史时保留 Model/Audit/收据并向前修复。Known Issues：质量证明核验/关联、模型读/状态/公开创建 API、实际 Provider 连通/外发与质量 Gate、三平台发行、UAT/可用包仍待。Next：`AI-02-A03` 安全模型元数据读取及受权只读 API 合同。
