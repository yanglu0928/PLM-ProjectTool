# AI-02-A05：AIModel 可选创建 HTTP

日期：2026-10-02；状态：Windows11 / 隔离 PostgreSQL18.6 与可选 HTTP 合同 PASS。依据 DEC-668、冻结 `AI_MODEL_CREATE`、A02 持久幂等命令。

Changed：增加严格 JSON/Origin/Session/CSRF/幂等键的可选 POST `/api/v1/admin/ai/models`，只接收模型语义、受控能力及空质量引用。A02 写事务内取首次模型投影；新建与同 Key 历史重放均返回 201 `SUSPENDED`、`"v0"`、空质量引用及 `NOT_EVALUATED`，不受后来状态或质量引用改变影响。普通默认应用与当前生产组合不挂创建路由。无模型调用或外发。

Tests：合同3项；`validation/ai-02-a05-model-create-http/verify.py` 在隔离 PG18 验证真实 201、修改数据库状态和质量引用后原始投影重放、换载荷409、普通用户404、License403，唯一 Model 与唯一 Audit。A02 内部同 Key 并发已独立验证，本项未重复。后端全量2047运行/3跳过；临时 PG 停止。开发 wheel SHA-256 `5ac6dcb40071e4337aa0e300f87c2caaba56b5b97b2b1693e92d4f50cbed4f58`。

Migration：无，复用0057。API：冻结 POST 合同的可选实现，无 Breaking Change。兼容与回滚：不挂或撤路由即可停止公开创建，已有模型/收据/Audit 保留。Known Issues：正式写组合、目标账户信任、质量证明核验/模型状态/真实模型调用、Server2025/Debian、Gate3/UAT/可用包待。Next：`AI-02-A06` Windows 显式写组合与合成 PG 验收。
