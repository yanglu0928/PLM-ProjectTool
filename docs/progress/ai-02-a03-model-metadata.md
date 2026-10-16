# AI-02-A03：AIModel 安全元数据读取

日期：2026-10-02；状态：Windows 11 / 隔离 PostgreSQL 18.6 内部与可选 HTTP 合同 PASS。依据 DEC-666、冻结 API-03/DM-04 与 Schema 0057。

Changed：新增部署管理员受权模型详情/列表服务、只读 SQLAlchemy 投影、独立 32 字节 HMAC 游标和可选 `/api/v1/admin/ai/models` GET/LIST 路由。游标绑定 Session、page_size 与资源 family；按创建时间/ModelId keyset 排序。许可和当前管理员 Session 在读取前复核；缺失/撤权不暴露模型。仅公开语义/受控能力/状态/ETag/质量引用，`quality_status` 始终为 `NOT_EVALUATED`，不把 AVAILABLE 或引用当作质量证明；不返回 Secret 或厂商异常。默认及当前生产组合均不挂该路由，返回404。

Tests：单元/合同6项；`validation/ai-02-a03-model-metadata/verify.py` 在 Windows11 隔离 PostgreSQL18.6 中验证真实管理员和普通用户 Session、License、三模型分页、新行隔离、`AVAILABLE` 加质量引用仍未评估、Session 撤权、默认404与安全投影。后端全量2041运行/3跳过；临时 PG 已停止。开发 wheel SHA-256 `285b20f78d92366ee3b77fa7d790449824230d3e074a8d49439face9b34fdf0c`。

Migration：无，复用0057。API：仅显式注入可选只读路由，无冻结 `/api/v1` Breaking Change。兼容与回滚：无新依赖；撤路由注入可回退，历史 Model/Audit 保留。Known Issues：正式目标账户尚无模型游标密钥供给，因此生产只读路由未启用；模型创建/状态 API、质量证明核验/真实模型调用、Server2025/Debian、Gate3/UAT/可用包未验。Next：`AI-02-A04` 检查正式密钥供给和 Windows 只读组合；不满足则继续独立任务，不虚报生产可用。
