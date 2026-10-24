# AIModel Schema 增量 `20261002_0057`

日期：2026-10-02；WBS：`AI-02-A01`；依据冻结 DM-04、SC-01/02、API-03 与 DEC-664。原 Gate 2 冻结版本及提交 `64cdf09` 不追写。

`plm.ai_models` 保存部署级稳定 ModelId、Provider FK、受控 model key、kind、revision、Embedding dimension、状态/锁版本和创建责任；`plm.ai_model_capabilities` 保存受控布尔/整数能力声明，`plm.ai_quality_profile_refs` 保存可选质量证明引用。初态 `SUSPENDED`，不是连通或质量通过。唯一语义身份含 Provider/key/kind/revision/dimension，NULL 亦参与去重；EMBEDDING 必有有效维度，其他 kind 必无维度。语义字段及两个子表历史不可 UPDATE/DELETE/TRUNCATE；主表 state/lock 留给后续受权命令。质量引用当前仅为受约束引用值，尚未解析或验证证明有效性。

Migration 从 `0056` 升到 `0057`，空表可降级回 `0056`；任一模型/能力/引用历史存在时拒绝物理降级。无旧表改写或生产数据迁移、无公开 API/依赖变化。部署前应备份并核对当前 head，生产升级及目标环境另行验收。
