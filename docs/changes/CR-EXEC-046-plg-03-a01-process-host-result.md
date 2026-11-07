# CR-EXEC-046：PLG-03-A01 JSON-RPC 子进程 Host 执行结果

- 日期：2026-11-07
- WBS：PLG-03-A01 Process Host
- 决定：按已授权持续执行；限定为独立传输层，不改变冻结 API、Schema、Migration、Publisher trust 或 Output worker。
- 结果：`PASS_SCOPE_LIMITED`，限合成子进程与 GitHub Hosted Windows Server 2025 D 盘。

## 实施内容

新增 `apps/backend/src/plm_assistant/modules/plugin/application/process_host.py` 及 `apps/backend/tests/unit/test_plugin_process_host.py`。Host 使用无 shell 的显式执行路径，环境采用 allowlist，限制请求/响应/诊断大小及执行时间，接受一个 JSON-RPC 2.0 请求和一条匹配 ID 的响应；对重复 JSON 成员、错误 ID、远端错误、非有限数字、敏感凭据字段和越界输出失败关闭，并清理其拥有的临时工作目录与子进程树。没有接入 Output 或 Worker，也没有安装/执行真实或客户插件。

## 验收证据

GitHub Hosted workflow run [42315760138](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42315760138)，Windows Server 2025 hosted runner：

- 后端全量 4,094 项测试通过，其中新增 Host 单测 7 项通过；Plugin ceremony 5 项通过；wheel 构建成功。
- 前后端构建、PG18 sidecar/父包 smoke、P25、P40、A17、A34、P24、P39、A50 成功。
- 17 jobs 中 16 success、1 failure；唯一失败为 SUR-07-A08 的 `initdb.exe` 返回 3221225781。受控 TEMP 环境只读探测同码失败，替代环境未应用。该原因尚未查明；依 CR-EXEC-039 停止重复 TEMP/TMP 假设。
- 全部本项测试使用 synthetic child 和 Hosted D 盘临时目录，无客户数据、对外 AI 请求、真实插件执行、数据库/文件业务写入或本机代码运行。

## 限制与后续

本结果不证明 Windows 11 实机兼容，不建立插件 Publisher 信任，不等同于操作系统级沙箱，不授权接入生产 Output。真实插件仍须经过现有安装、签名、兼容性与 Operation capability 检查，并在 trust 未建立时保持拒绝。下一项 PLG-03-A02 先核对应用层衔接与 fail-closed 证据边界。
