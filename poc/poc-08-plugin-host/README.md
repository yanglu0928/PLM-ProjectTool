# POC-08 Plugin Host

## Status

`PASS_WITH_EXCEPTION / WINDOWS11_PASS / SERVER2025_PASS / DEBIAN13_DEFERRED_BY_USER`

## Environment

- 目标：Windows 11、Windows Server 2025、Debian 13，x86-64。
- Python：3.13.x。
- IPC：独立 Python 子进程 + JSON-RPC 2.0 over stdin/stdout。

## Input

仅使用仓库内合成插件：正常回显、崩溃、超时、非法 JSON、不兼容 API 版本、环境隔离与独立升级。不读取客户资料、数据库、AI Key 或外部网络。

## Steps

1. 加载 Manifest，检查必填字段、版本、OS、入口边界与 SHA-256。
2. 通过统一 `PluginService` 启动独立子进程，发送单条 JSON-RPC 请求并验证响应。
3. 对 crash、timeout、invalid JSON 和远程错误进行失败关闭处理。
4. 通过 FastAPI 测试端点验证插件失败后主应用仍可健康响应。
5. 在不改动宿主代码的前提下将同一插件从 v1.0.0 切换到 v1.1.0。

## Result

Windows 11 与 Windows Server 2025 全部通过。两端均证明 crash、timeout 和 invalid JSON 不会导致 FastAPI 宿主崩溃；不兼容 API 版本、篡改入口文件和已禁用插件均在启动前拒绝；数据库和 AI Key 环境变量未传入插件子进程；同一插件从 1.0.0 切换至 1.1.0 不需修改宿主代码。

## Metrics

- Windows 11：13/13 单元与集成测试 PASS；10/10 验收场景 PASS；20/20 并发调用 PASS。
- Windows Server 2025：完全离线依赖安装与包 Hash PASS；13/13 测试、10/10 场景和 20/20 并发调用 PASS。
- 超时阈值样例：200 ms；两端均返回 `PLUGIN_TIMEOUT` 并在失败后通过 `/health`。
- 敏感环境变量可见数：0。

## Logs

- 脱敏汇总保存在 `evidence/<platform>/`。
- 完整运行结果保存到 Git 忽略的 `artifacts/poc-08/`。

## Known Issues

- Debian 13 依据 `EXC-P0-005` 暂缓，仍不得从 Windows 结果外推。
- 本 PoC 不实现插件容器、第三方插件市场或客户 SDK。
- Manifest `signature` 在本 PoC 仅以入口文件 SHA-256 验证包完整性，不声称具备开发者身份信任；正式发布签名算法尚待 Architecture/Release 阶段冻结。

## Conclusion

Python 3.13 独立子进程 + JSON-RPC 2.0 over stdio 在 Windows 11 和 Windows Server 2025 上可行，能满足崩溃/超时/协议异常隔离、Manifest 兼容性检查、启停与独立升级 PoC 要求。

## PASS / FAIL

`PASS_WITH_EXCEPTION`：Windows 11 `PASS`；Windows Server 2025 `PASS`；Debian 13 `DEFERRED_BY_USER / 未验证`。

## Alternative

如果当前 IPC 路径无法通过 crash 隔离门槛，保留失败证据并触发 L3，不自行改为微服务、容器或自定义 TCP。
