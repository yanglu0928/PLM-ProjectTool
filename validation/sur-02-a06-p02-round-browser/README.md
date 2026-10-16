# SUR-02-A06-P02 Windows 11 Edge 验收

`serve.py` 复用来源定位浏览器 fixture，并在隔离库中把合成 Survey Version 明确提升为 APPROVED/current approved；随后提供隔离 PostgreSQL 18、一次性项目负责人凭据、构建后 Vue 与 Windows 生产 FastAPI 同源组合。`run-edge-browser.mjs` 使用本机 Microsoft Edge 一次性 profile 验证 Round 列表/详情、CREATE、PATCH、OPEN、CLOSE 不完整失败关闭及第二轮 CANCEL，并保存三张截图。

浏览器只处理隔离合成数据，不访问外网。服务退出时删除数据库、凭据、临时文件与浏览器 profile。
