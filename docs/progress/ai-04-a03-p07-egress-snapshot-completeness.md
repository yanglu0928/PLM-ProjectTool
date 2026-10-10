# AI-04-A03-P07：EgressAuthorization 快照完整性

- 日期：2026-10-02
- 结果：PASS（Windows 11 / PostgreSQL 18.6 隔离验证）
- 依据：CR-AI-012、DEC-704、冻结 API-03

Schema0067 为每个新外发授权快照强制 Model、批准角色、preview payload/source refs 指纹、载荷/Token/重试上限和捕获时 `AUTHORIZED` 状态。Model 必须为同 Provider 下的 AVAILABLE 模型。旧快照的新列保持 NULL 且不得被新执行链使用，不伪造回填。

验证：空库与0065遗留快照 up/down/re-up，drift=0；缺完整字段、SUSPENDED Model、非批准角色、越界载荷、更改/删除均拒绝，完整新快照拒绝降级。后端2106运行/3跳过PASS。开发wheel SHA-256 `4550d75d6d8961ce493637a56b618e3c32132d4aee7caf5b58d4144146ce9589`。

本项无真实外发、公开API或生产迁移；Egress Owner、AITask原子创建与Worker每批次撤销重校验待后续。
