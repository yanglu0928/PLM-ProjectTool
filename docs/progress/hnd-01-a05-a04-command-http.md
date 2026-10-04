# HND-01-A05-A04：Handover Analysis 五个普通写 HTTP

日期：2026-10-05。结论：`HND_01_A05_A04_COMMAND_HTTP_PASS`。下一项：`HND-01-A05-A05` 业务原子 `HND_VERSION_SUBMIT_REVIEW`。

## 实现边界

新增可选 `handover_command_router`，精确覆盖 Analysis CREATE/PATCH/ARCHIVE 与 Version CREATE/VALIDATE，直接调用 A03 及既有 A03-P01～P03 Owner，不复制业务授权、License、项目隔离、幂等、Audit 或固定来源逻辑。默认 app 和当前 Windows 组合未注入时继续 404。

传输层只接受精确 DTO、canonical UUID、可信 Origin、当前 Session/CSRF、幂等键和强 ETag；拒绝重复 JSON 键、未知字段、query、超 2 MiB 正文和非标准常量。响应仅是固定身份、状态、摘要、指纹、计数和安全错误投影。

## 偏差、兼容与回滚

无冻结 URL/Operation/角色语义破坏，无 Migration、依赖、配置、Secret、网络或客户数据外发。打包复验发现原 `handover/api` 缺少 `__init__.py`，导致源码测试可用但 wheel 丢失整个 API 目录；已补包标记并同时验证新命令与已有 Action 读取可从 wheel 导入。这是发行完整性修复，不改 HTTP 语义。

回滚可停止注入可选 Router 恢复 404；已由 Owner 写入的合法历史不删除。

## 客观验证

- 新增合同 3 项通过：默认关闭、五命令成功形状、安全/严格 JSON/错误投影。
- Windows 11 / Python 3.13 后端全量 2690 项通过，3 项环境条件跳过。
- wheel 重建后可导入 `handover.api.commands` 与 `handover.api.read_actions`；SHA-256 `d72a5e078ed0caa7226af75580b46f2d218942c374bf7fd61c2700c2f2292da9`。

未完成：A05业务原子送审、A06五读 HTTP/cursor、A07 Windows真实组合与 HTTP/PG；Server 2025、Debian 13、Gate 3 和发行仍按总状态跟踪。
