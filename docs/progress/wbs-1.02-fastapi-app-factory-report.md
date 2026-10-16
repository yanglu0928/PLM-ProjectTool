# WBS 1.02 FastAPI App Factory 执行报告

## 结果

`PASS / PYTHON_3.13.14 / FASTAPI_0.141.1 / WINDOWS_11 / NO_DATABASE / NO_EXTERNAL_CALLS`

|字段|结果|
|---|---|
|Phase|Phase 1：架构冻结与基础工程|
|WBS|`1.02 FastAPI app factory`|
|前置|Gate 2、WBS 1.01 PASS|
|模块|`platform`|
|实体/数据库|无；Migration 不适用|
|业务 API|无|
|非业务健康面|`GET /health/live`、`GET /health/ready`|
|权限|健康面匿名最小读取；其他路径不存在|
|外部调用|0|
|下一 WBS|`1.03 Vue app shell`|

## Changed

- 建立 Python 3.13 `pyproject.toml`，固定 FastAPI/Uvicorn 及 test 依赖。
- 建立 `plm_assistant.entrypoints.api:create_app` 工厂和隔离 lifespan。
- 创建首个 `platform` 模块四层目录，只实现 Health Application/API。
- Readiness 支持同步/异步探针并对 False、异常、未启动状态失败关闭。
- 禁用 Swagger、ReDoc 和外部 OpenAPI；未注册任何 `/api/v1` 业务路由。
- 登记 `DEC-20260924-061`。

## Tests

|类型|覆盖|结果|
|---|---|---|
|Unit|工厂实例隔离、安全默认、启动前失败关闭|3/3 PASS|
|API/Contract|live/ready、同步/异步探针、503 最小响应|5/5 PASS|
|Permission/Surface|仅两个健康路径；docs/root/business prefix 404|2/2 PASS|
|Integration|lifespan start/stop、实例状态隔离|2/2 PASS|
|合计|Python unittest|12/12 PASS|
|Packaging|`pyproject.toml` 无网络构建 wheel|PASS|
|Runtime smoke|Uvicorn `--factory` 启动；live/ready 实际 HTTP 请求|2/2 PASS|

Windows 11 证据还记录 Python/FastAPI/Starlette/Pydantic/Uvicorn/HTTPX2 实际版本、公开路由数及 200/503 状态。测试未连接 PostgreSQL、文件库、客户资料或外部服务。

## Known Issues / Boundary

- Readiness 当前只验证进程 lifespan；数据库、文件存储和配置探针在各自 WBS 实现后注入。
- 正式统一错误 Envelope、TraceId、JSON 日志和 Config/Secret 尚未实现，分别由 1.06、1.08、1.07、1.09 完成。
- 本结果只证明 Windows 11 当前环境；Windows Server 2025 与 Debian 13 发行验证状态不变。
