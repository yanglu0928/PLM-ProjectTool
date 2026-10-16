# SUR-01-A06-A05-P02 Windows 11 Edge 验收

`serve.py`创建隔离PostgreSQL 18事实库、四类Survey来源、Project Template、同Project Evidence和一次性项目负责人凭据，并启动构建后的Vue与Windows生产`platform-write` FastAPI同源组合。

`run-edge-browser.mjs`使用本机Microsoft Edge一次性profile完成登录、进入项目/调研/固定问题卡片，依次点击Handover、Capability、Template、MANUAL来源；Handover Evidence再经Viewer定位。脚本核对四个location 200、一个Viewer 200、受权原文链接、人工维护提示、无内部row identity和无UI告警，并保存三张截图。

浏览器PASS后向服务stdin发送`VERIFY`，服务确认Survey/Version零写入并清理数据库凭据、临时数据库、profile和文件。登录审计属于认证边界的预期写入，不计入来源定位的只读断言。全部数据均为隔离合成内容，无外网调用。
