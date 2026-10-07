# REQ-01-A11-A05 Windows 11 Edge / PostgreSQL 18

`serve.py` 基于已有隔离Survey浏览器fixture，增加一条无版本Requirement与有效客户评审人；使用Windows
生产写组合、临时Credential/Vault、本机PostgreSQL 18与构建后Vue。`run-edge-browser.mjs`启动一次性真实
Microsoft Edge profile，执行Requirement读取、结构化Draft创建、校验、送审、Evidence点击定位、断网
清旧/恢复以及Session撤销后的直接页门禁。

仅处理隔离合成数据，不访问外网。服务退出时清理临时数据库、凭据、文件与浏览器profile；截图写入
Git忽略的`artifacts/req-01-a11-a05-windows-browser/`。
