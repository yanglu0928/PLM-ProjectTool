# WBS 1.02 FastAPI App Factory Validation

状态：`WINDOWS_11 / PYTHON_3_13 / NO_DATABASE / NO_EXTERNAL_CALLS`

验证 app factory 的实例隔离、生命周期、最小健康面、失败关闭 readiness、公开路由范围与依赖版本。

运行前安装 `apps/backend/pyproject.toml` 的生产和 test 依赖，并让 `apps/backend/src` 位于 Python import path；随后执行：

```powershell
python -m unittest discover -s apps/backend/tests -v
python validation/wbs-1.02-fastapi-app-factory/verify.py --write
```

证据写入 `evidence/windows-11/result.json`。
