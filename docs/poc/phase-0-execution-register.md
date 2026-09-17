# Phase 0 执行登记表

## 阶段状态

|字段|值|
|---|---|
|Phase|Phase 0 技术验证|
|状态|IN_PROGRESS|
|启动日期|2026-09-17|
|正式开发 Gate|BLOCKED|
|完成条件|全部 P0 PoC PASS，或失败项具有用户确认的替代方案|

## PoC 登记

|PoC|对应 WBS|验证主题|状态|开始日期|完成日期|结论|证据|
|---|---|---|---|---|---|---|---|
|POC-01|P0.01/P0.02/P0.03/P0.04|Python 3.13 双平台依赖及离线安装|IN_PROGRESS|2026-09-17|-|Windows 11 在线/离线预检 PASS；待两个目标环境验证|`poc/poc-01-python-313-dependencies/`|
|POC-02|P0.05/P0.06/P0.07/P0.08|PostgreSQL 18 + pgvector|NOT_STARTED|-|-|-|-|
|POC-03|P0.09/P0.10/P0.12|PLM RAG|NOT_STARTED|-|-|-|-|
|POC-04|P0.11|AI Gateway / DeepSeek|NOT_STARTED|-|-|-|-|
|POC-05|P0.04/P0.12|Document + OCR|NOT_STARTED|-|-|-|-|
|POC-06|P0.16/P0.17|Word / PPT|NOT_STARTED|-|-|-|-|
|POC-07|P1|VSDX|DEFERRED_P1|-|-|不阻塞 Phase 0|-|
|POC-08|P0.13|Plugin Host|NOT_STARTED|-|-|-|-|
|POC-09|P0.14/P0.15|License|NOT_STARTED|-|-|-|-|

## 状态定义

- `NOT_STARTED`：尚未开始。
- `IN_PROGRESS`：已有执行活动，但未满足完整验收条件。
- `BLOCKED`：当前缺少必要环境、输入或决策。
- `PASS`：全部必需产物和验收项通过。
- `FAIL`：已形成完整失败分析，尚无获批替代方案。
- `DEFERRED_P1`：正式降级为 P1，不阻塞 Phase 0。

## 变更记录

|日期|变更|
|---|---|
|2026-09-17|建立 Phase 0 登记表并启动 POC-01。|
|2026-09-17|完成 Windows 11 / Python 3.13.15 在线与 wheelhouse 离线预检；POC-01 保持 IN_PROGRESS。|
