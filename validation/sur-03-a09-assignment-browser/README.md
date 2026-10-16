# SUR-03-A09 Windows 11 Edge 验收

`serve.py` 复用已拥有的隔离 Survey 浏览器 fixture，并把合成定义提升为当前批准版本；一次性专用 Evidence cursor key 仅用于这个隔离验收进程，保证生产组合实际挂载友好证据选择器需要的受权列表。`run-edge-browser.mjs` 使用本机 Microsoft Edge 一次性 profile，经构建后 Vue、Windows 生产 FastAPI 与 PostgreSQL 18 完成 OPEN Round、部门级 Assignment、四道固定问题答复、SUBMIT、VALIDATE 及 Round CLOSE。

浏览器只处理隔离合成数据，不访问外网。服务退出时删除数据库、凭据、临时文件与浏览器 profile；截图写入 Git 忽略的本机 `artifacts/sur-03-a09-assignment-browser/`。
