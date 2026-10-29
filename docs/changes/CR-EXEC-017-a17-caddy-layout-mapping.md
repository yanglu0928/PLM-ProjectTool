# CR-EXEC-017：修正 A17 候选包 Caddy 布局映射

- 日期：2026-10-29
- 状态：映射修正确认有效，A17 总体验收待后续修正与重验
- 来源与证据：GitHub hosted Windows 2025 run 40808408854 的 A17 作业已完成候选投影、父包 PostgreSQL 初始化/迁移与产品 API readiness；随后在 packaged HTTPS smoke 中失败，明确报错 `packaged Caddy executable missing from verified layout`。同轮其他 9 个作业通过。源码核查确认父包组装器将官方 Caddy 放入 `payload/runtime/caddy/caddy.exe`；当前映射器把 `payload/runtime/` 通用映射到 `runtime/python/`，因而与实际运行路径 `runtime/caddy/caddy.exe` 不一致。尚未产生 Edge 或最终 PG 清理 PASS markers，A27 不通过。
- 问题：统一候选布局把父包中的 Caddy 可执行文件投影到错误目录，导致 A17 无法启动包内 HTTPS 代理。
- 方案比较：A. 为更具体的 `payload/runtime/caddy/` 前缀增加优先映射至 `runtime/caddy/`，保留其余 `payload/runtime/` 到 `runtime/python/` 的映射；B. 修改 smoke 去运行错误投影位置的 Caddy，掩盖布局错误。选择 A，以包的既定布局为准。
- 基线差异：仅更正非发行候选的测试/布局映射规则；不改候选包二进制、运行时、业务逻辑、安装根、配置、Schema、API 或正式发行基线。
- 影响与风险：受影响的只有 A17 synthetic layout 的 Caddy 文件目标路径；可能发生目标路径冲突，将由映射器的 Windows 大小写不敏感冲突检查拒绝。其他运行时文件映射保持不变。
- 回滚：删除新增的特定前缀映射，恢复通用前缀行为；只影响可丢弃的 hosted 临时布局，不触及用户数据。
- 验证计划：托管 Windows 作业运行映射/候选投影检查和完整 A17 package HTTPS flow；要求看到 PlanVersion Edge、PostgreSQL state、进程停止及临时目录清理 markers，且固定候选包 Hash 未改变。未达到这些条件不关闭 A27。
- 执行边界：只用 GitHub hosted runner；不在用户本机或 C 盘执行项目代码。候选数据为合成数据，不外发客户材料或 Secret。

- 托管复验追加（run 40810209866）：新映射使 packaged A17 越过此前 Caddy missing-path 失败，并到达 Workflow GET/START/replay/CSRF/conflict/Audit PASS；整个 WBS 尚未完成，随后独立日志输出编码问题由 CR-EXEC-018 追踪。
