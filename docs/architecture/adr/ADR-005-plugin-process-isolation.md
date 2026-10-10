# ADR-005：开发者插件采用独立 Python 子进程与 stdio Contract

## Status

`ACCEPTED_FROM_BASELINE / NOT_GATE_2_FROZEN`

## Date

2026-09-22

## Context

输出格式与少量扩展能力需要独立升级，但插件异常不能拖垮 FastAPI，插件也不能获得数据库、AI Key 或 License 私钥。POC-08 已证明短命子进程、JSON-RPC over stdio、超时和崩溃隔离可行；它未证明可安全运行任意第三方代码。

## Decision

1. 插件统一由 `PluginService` 管理，通过独立 Python 子进程和 JSON-RPC 2.0 over stdin/stdout 调用。
2. 加载前验证开发者签名、Manifest、Plugin API Version、目标 OS、入口路径、包完整性和声明依赖。
3. Plugin 子进程只接收最小 OutputContext、受控 Plugin API 和单次工作目录；不继承数据库连接、AI Key、License 私钥或宿主完整环境变量。
4. timeout、crash、invalid JSON、版本不兼容、签名失败和越界入口必须失败关闭并映射为 `PLUGIN_*` 错误。
5. 宿主回收超时/崩溃进程树，插件失败不得导致 FastAPI 或其他 Job 失效。
6. 插件包只由开发者工作台签名提供。客户只能安装、启用、禁用和升级开发者包；V1 不开放客户 SDK、任意第三方插件或插件市场。
7. V1 不承诺容器、强制网络沙箱或恶意代码隔离；独立进程仅提供故障边界与凭据最小化。

## Consequences

- 插件可独立版本化并在不改宿主业务代码的情况下升级。
- stdio Contract 易于离线部署和跨 Windows/Linux 验证，无需自定义 TCP。
- 进程启动存在开销；正式实现可在不改变隔离与 Contract 的前提下评估受控进程池。
- 由于没有强沙箱，只能信任开发者签名包，不能把此机制宣传为安全执行任意代码。
- 插件需要外部依赖时，必须在 Manifest、安装验收和管理员配置中显式声明。

## Rejected Alternatives

- 插件进程内加载：崩溃、依赖冲突和凭据暴露风险高。
- 插件直连数据库：破坏模块数据所有权和升级兼容性。
- 自定义 TCP/WebSocket：增加协议和端口管理，不符合基线。
- 容器化插件/第三方市场：超出 V1 Scope，且不能替代签名与 Contract。

## Rollback / Change Rule

可在保持 JSON-RPC stdio、签名验证和最小权限的前提下调整短命/常驻生命周期。允许客户任意插件、改变 IPC、引入容器或赋予数据库/AI Key 权限属于 L3 架构与安全变更。

## References

- `docs/architecture/application-contracts-v1-candidate.md`
- `poc/poc-08-plugin-host/`
- `docs/progress/phase-0-summary.md`
