# API-05 Contract Lint

状态：`VALIDATION_ONLY / API_CONTRACT_CANDIDATE_INPUT / NOT_FASTAPI_IMPLEMENTATION`

该工作区从 API-01～API-04 Markdown 候选中提取并验证：

- 22 个 Owner、65 个 Root 及 DIRECT/NESTED/READ_ONLY/INTERNAL 暴露分类；
- Operation ID、Method/Path 变体、Role、S/L/C/I/M/E/A 控制和来源；
- 统一错误码、SSE event type、受控枚举和 20 个 Schema Query ID 映射；
- CSRF、If-Match、Idempotency、ProjectId、逐次外发授权与无通用 DELETE 边界；
- API Root 目录与 SC-04 Schema Manifest 的一致性。

运行：

```powershell
python validation/api-05-contract-lint/contract_lint.py --write
python -m unittest discover -s validation/api-05-contract-lint/tests -v
```

输出：

- `generated/api-contract-manifest-v1.json`：OpenAPI/实现阶段的机器输入目录，不是可部署 OpenAPI Schema。
- `evidence/windows-11/result.json`：本地静态 Contract 验证结果。

本工作区不连接数据库、客户资料或外部服务，不生成 FastAPI/Pydantic/ORM/Migration，也不改变 Gate 2 状态。
