# TRC-01-A08-P04：Trace supersede 冻结三字段引用同事务解析

日期：2026-10-02；Phase 2；结果：**内部原始引用命令/隔离 PostgreSQL 18 PASS；公开 HTTP 未挂载**。输入冻结 API-02 的 `ResourceVersionRef`、P02 原子替换、P03 前置与 DEC-20261002-618。

新增显式 Owner 注册的 `TracePublicEdgeResolver` 与 `SupersedeTraceLinkRefs` 内部入口。原始 source/target 只有 `resource_type/resource_id/version_id`；先校验当前 License、Session/CSRF、ACTIVE 项目经理并锁旧边，按原始三字段及旧边版本预留持久收据。同 Key 历史结果在重验当前身份/项目/许可及旧终态/替代 ID 后返回，不要求已变为不可读的新端点再次证明。首次写入才由注册 Owner 在同一事务解析真实 Scope/Project，再执行 P02 的相关性、两端固定证明、环、新边插入、旧边终结、双 Audit 与收据原子提交。当前仅注册 `DOC-02`；未知或跨项目类型失败关闭，不接受客户端提供内部 Owner/Scope。

验证：新增单元 2 项覆盖冻结引用、Owner 失效后安全重放、同 Key 不同原始载荷冲突、未知/非法引用拒绝；原 P02 单元回归。Windows 11 一次性 PostgreSQL 18 使用真实 Document Owner/Session、`DOC-02` 三字段输入完成旧边 v1/新边 v0；来源文件随后变为 RESTRICTED，原 Key 重放仍返回第一次替代 ID，不重新创建边；原 Trace 创建/图/撤销 HTTP 与内部替换链回归 PASS。全后端 **1897 运行、3 跳过、无失败**；开发 wheel SHA-256 `29a227016ed0e5501e4f4cfec3741cbffa989353e146eadff47cbb85a0ce1fa0`。开发 wheel 不是可使用发行包。

兼容/升级/回滚：Trace Application/Owner 内部 Port 增量，无公开 API、Schema、Migration、新依赖或旧数据改写。不注入 Resolver 即不可调用原始引用入口；P02 已解析内部入口保留。历史终态不可逆，已用收据应继续保留以支持首次结果重放。其他业务 Owner、关系 Owner、P05 可选 HTTP、正式目标账户信任、Server2025/Debian、性能/UAT/Gate 3 与可用程序包仍待。下一项 P05 再验证冻结 HTTP 请求解析与真实 ASGI/PG，不将本项内部 PASS 外推为公开可用。
