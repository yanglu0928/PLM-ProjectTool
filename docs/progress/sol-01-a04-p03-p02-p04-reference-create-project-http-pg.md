# SOL-01-A04-P03-P02-P04：PROJECT Reference 创建 ASGI/PG 组合

日期：2026-10-09；结果：`PROJECT_REFERENCE_CREATE_HTTP_PG_PASS`，限定 Windows 11 合成账户/License 与隔离 PG18.6/私有文件。不是正式发行或完整 Reference 可用结论。

```text
当前 Phase：Phase 2
当前 WBS：SOL-01-A04-P03-P02-P04
输入基线：冻结 API-01/API-04、0144/CR-SOL-007、P03-P02-P03 可选 Router
前置：PROJECT Owner PG/文件、HTTP 合同通过
涉及模块/实体：Solution 创建 HTTP 组合验证；生产实体/Schema/API 不变
API/权限：PROJECT PM/IM 创建；GLOBAL 仍不开放
验收：真实 SessionService→ASGI→Owner→PG/文件、幂等/跨项目/撤权/CSRF/License/篡改
风险：仅合成许可和用户；正式目标服务账户信任源、UI、GET/List、GLOBAL确认待
```

复用前项隔离 PG18.6、真实 PROJECT Session/成员、DocumentVersion/Evidence 和私有源文件夹具，显式将 Router 装入单独 ASGI 应用。项目经理 POST 返回 201、`REFERENCE_ONLY`/`DRAFT`、ETag/Location/Trace，重放返回原结果，同 Key 异载荷 409；跨项目与暂停成员重放 404，错误 CSRF 403，源文件字节篡改 503，许可拒绝 403。既有 GLOBAL 文件/解析节点/确认撤回回归、Alembic drift 与 PROJECT 内部权限回归在同库通过，脚本退出 0。默认应用和 GLOBAL 路由继续关闭。

首次补强篡改断言时预期 404，而实际为 503 来源不可用；此映射与当前冻结通用错误合同一致，收紧为 503 后完整脚本重新退出 0。未对生产代码或 Schema 作偏差修改。正式 License 公钥/服务账户密钥、真实登录/人工脱敏确认、Windows显式组合、GET/List/UI、20并发和 Gate3/发行仍未验。TraceLink：API-01/API-04 → DEC-20261009-1112 → Router/Owner → 本项隔离 ASGI/PG/文件脚本。
