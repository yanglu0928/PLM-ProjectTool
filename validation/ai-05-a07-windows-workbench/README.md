# AI-05-A07 Windows 11 AI 工作台浏览器验收

本项复用 `../ai-05-a06-p04-windows-browser/serve.py` 提供的隔离 PostgreSQL 18、生产 FastAPI 和实际 Vite 构建资产，只把浏览器验收扩展至创建后的完整只读工作台。

执行 `run-edge-browser.mjs` 时追加 `--workbench`：

```powershell
node validation/ai-05-a06-p04-windows-browser/run-edge-browser.mjs `
  http://127.0.0.1:<port> <project-id> <evidence-directory> --workbench
```

验收链为登录、项目、AI 工作台、新建、Preview、逐次授权、创建、AI Task 详情、空 Invocation 历史、既有 Job 详情、浏览器返回及工作台列表回显。校验浏览器实际收到 Task、Invocation、Job 与列表四类 `200` 响应；不启动 Worker、不调用模型厂商，也不把排队状态冒充 AI 执行成功。

服务进程收到 `VERIFY` 后还会核对数据库只有一个授权、一个 `QUEUED` AI Task、一个 `PENDING` Job、零 Invocation，并清理临时数据库、角色、Vault、文件和进程。
