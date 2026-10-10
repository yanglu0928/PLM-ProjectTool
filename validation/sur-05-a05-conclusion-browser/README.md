# SUR-05-A05 Windows 11 Edge 验收

`serve.py` 复用已拥有的隔离 Survey/Assignment 浏览器 fixture，并仅为当前一次性数据库增加一个
ACTIVE CUSTOMER_MANAGER 评审人。`run-edge-browser.mjs` 使用本机 Microsoft Edge 一次性 profile，
经构建后 Vue、Windows 生产 FastAPI 与 PostgreSQL 18 完成 HND-03 待办、CLOSED Round、VALIDATED
Responses、SurveyConclusion CREATE/GET/VALIDATE/SUBMIT_REVIEW、Evidence Viewer 及待办深链定位。

浏览器只处理隔离合成数据，不访问外网。服务退出时删除数据库、凭据、临时文件与浏览器 profile；
截图写入 Git 忽略的本机 `artifacts/sur-05-a05-conclusion-browser/`。
