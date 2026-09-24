# POC-08 验收矩阵

|ID|验收项|Windows 11|Windows Server 2025|Debian 13|证据要求|
|---|---|---|---|---|---|
|P08-A01|Python 3.13 / x86-64 环境|PASS|PASS|DEFERRED_BY_USER|脱敏环境 JSON|
|P08-A02|Manifest 必填字段与入口边界|PASS|PASS|DEFERRED_BY_USER|单元测试|
|P08-A03|入口文件 SHA-256 完整性|PASS|PASS|DEFERRED_BY_USER|篡改拒绝测试|
|P08-A04|JSON-RPC 2.0 stdio 正常调用|PASS|PASS|DEFERRED_BY_USER|响应结构断言|
|P08-A05|插件 crash 隔离|PASS|PASS|DEFERRED_BY_USER|FastAPI 继续健康|
|P08-A06|插件 timeout 终止|PASS|PASS|DEFERRED_BY_USER|超时错误与进程清理|
|P08-A07|非法 JSON 失败关闭|PASS|PASS|DEFERRED_BY_USER|`PLUGIN_INVALID_RESPONSE`|
|P08-A08|不兼容 Plugin API 版本拒绝|PASS|PASS|DEFERRED_BY_USER|启动前拒绝|
|P08-A09|环境隔离|PASS|PASS|DEFERRED_BY_USER|插件不可见 DB / AI Key|
|P08-A10|独立升级|PASS|PASS|DEFERRED_BY_USER|v1 → v1.1 不改宿主|
|P08-A11|启用/禁用控制|PASS|PASS|DEFERRED_BY_USER|禁用时启动前拒绝|
|P08-A12|隐私与仓库安全|PASS|PASS|DEFERRED_BY_USER|无 Secret、客户数据和运行日志|

## 门槛

- crash、timeout、invalid JSON 不得导致 FastAPI 进程崩溃。
- 不兼容版本、不支持 OS、越界入口或 Hash 不匹配必须在启动前拒绝。
- 插件子进程不得继承数据库连接字符串、DeepSeek/API Key 或其他业务 Secret。
- 升级插件不得需要修改宿主实现。
