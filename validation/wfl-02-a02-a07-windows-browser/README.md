# WFL-02-A02-A07 Windows Edge 验收

`serve.py`创建独立PostgreSQL 18事实库、两个当前Handover PASS记录和一次性项目负责人凭据，
再启动构建后的Vue与Windows生产`platform-write` FastAPI同源组合。

运行服务后，把READY行中的origin传给`run-edge-browser.mjs`；浏览器脚本使用本机Microsoft
Edge和一次性profile完成登录、打开流程、填写理由、显式确认推进、观察首次回执及独立刷新。
浏览器PASS后向服务stdin发送`VERIFY`，服务核对唯一Transition、双Gate、Audit和持久回执，
最后清理数据库凭据、临时数据库、profile及文件。全部数据和凭据均为隔离合成内容，无外网调用。
